"""Existing greedy task offloading strategy."""

from __future__ import annotations

from time import perf_counter

from models import CloudServer, EdgeServer, ExperimentResult, MobileDevice, OffloadDecision
from security import sha256_digest, verify_payload

CPU_GHZ_TO_CYCLES_PER_MS = 1_000_000.0
LOCAL_ENERGY_COEFF = 2.8e-10
EDGE_COMPUTE_ENERGY_COEFF = 4.0e-11
CLOUD_COMPUTE_ENERGY_COEFF = 2.0e-11
TX_ENERGY_PER_MB = 0.42
BATTERY_VOLTAGE = 3.7
MAH_TO_COULOMB = 3.6


def run_existing_algorithm(
    devices: list[MobileDevice],
    edge_servers: list[EdgeServer],
    cloud_server: CloudServer,
    experiment_no: int,
) -> ExperimentResult:
    """Run a greedy policy that tries edge first, then cloud."""
    start = perf_counter()
    decisions: list[OffloadDecision] = []

    for device in devices:
        edge = min(edge_servers, key=lambda item: (item.current_load, -item.available_cpu()))
        cpu_required = _cpu_required_ghz(device)
        if edge.can_accept(cpu_required):
            decision = execute_on_edge(device, edge)
        else:
            decision = execute_on_cloud(device, cloud_server)
        decisions.append(decision)

    return build_experiment_result(
        experiment_no=experiment_no,
        algorithm="Existing Greedy",
        total_devices=len(devices),
        decisions=decisions,
        execution_time_s=perf_counter() - start,
    )


def execute_locally(device: MobileDevice) -> OffloadDecision:
    """Execute a task on the mobile device."""
    task = device.task
    execution_delay = task.cpu_cycles / (device.cpu_ghz * CPU_GHZ_TO_CYCLES_PER_MS)
    computation_energy = task.cpu_cycles * LOCAL_ENERGY_COEFF
    total_energy = computation_energy
    return OffloadDecision(
        device_id=device.device_id,
        target="Local",
        success=execution_delay <= task.deadline_ms,
        delay_ms=execution_delay,
        energy_j=total_energy,
        battery_used_mah=joules_to_mah(total_energy),
        transmission_delay_ms=0.0,
        execution_delay_ms=execution_delay,
        queue_delay_ms=0.0,
        communication_energy_j=0.0,
        computation_energy_j=computation_energy,
        integrity_verified=True,
    )


def execute_on_edge(device: MobileDevice, edge_server: EdgeServer, payload_size_kb: float | None = None) -> OffloadDecision:
    """Execute a task on an edge server."""
    task = device.task
    size_kb = payload_size_kb if payload_size_kb is not None else task.size_kb
    transmission_delay = calculate_transmission_delay_ms(size_kb, task.bandwidth_mbps, task.network_delay_ms)
    queue_delay = edge_server.queue_delay_ms()
    execution_delay = task.cpu_cycles / (edge_server.cpu_ghz * CPU_GHZ_TO_CYCLES_PER_MS)
    communication_energy = calculate_communication_energy_j(size_kb)
    computation_energy = task.cpu_cycles * EDGE_COMPUTE_ENERGY_COEFF
    total_delay = transmission_delay + queue_delay + execution_delay
    total_energy = communication_energy + computation_energy
    edge_server.allocate(_cpu_required_ghz(device))
    original_hash = sha256_digest(task.payload)
    return OffloadDecision(
        device_id=device.device_id,
        target=f"Edge-{edge_server.server_id}",
        success=total_delay <= task.deadline_ms,
        delay_ms=total_delay,
        energy_j=total_energy,
        battery_used_mah=joules_to_mah(total_energy),
        transmission_delay_ms=transmission_delay,
        execution_delay_ms=execution_delay,
        queue_delay_ms=queue_delay,
        communication_energy_j=communication_energy,
        computation_energy_j=computation_energy,
        integrity_verified=verify_payload(original_hash, task.payload),
        compressed_size_kb=size_kb if payload_size_kb is not None else None,
    )


def execute_on_cloud(device: MobileDevice, cloud_server: CloudServer, payload_size_kb: float | None = None) -> OffloadDecision:
    """Execute a task on the cloud server."""
    task = device.task
    size_kb = payload_size_kb if payload_size_kb is not None else task.size_kb
    transmission_delay = calculate_transmission_delay_ms(
        size_kb=size_kb,
        bandwidth_mbps=task.bandwidth_mbps,
        base_delay_ms=task.network_delay_ms + cloud_server.network_delay_ms,
    )
    queue_delay = cloud_server.queue_delay_ms()
    execution_delay = task.cpu_cycles / (cloud_server.cpu_ghz * CPU_GHZ_TO_CYCLES_PER_MS)
    communication_energy = calculate_communication_energy_j(size_kb) * 1.35
    computation_energy = task.cpu_cycles * CLOUD_COMPUTE_ENERGY_COEFF
    total_delay = transmission_delay + queue_delay + execution_delay
    total_energy = communication_energy + computation_energy
    cloud_server.allocate()
    original_hash = sha256_digest(task.payload)
    return OffloadDecision(
        device_id=device.device_id,
        target="Cloud",
        success=total_delay <= task.deadline_ms,
        delay_ms=total_delay,
        energy_j=total_energy,
        battery_used_mah=joules_to_mah(total_energy),
        transmission_delay_ms=transmission_delay,
        execution_delay_ms=execution_delay,
        queue_delay_ms=queue_delay,
        communication_energy_j=communication_energy,
        computation_energy_j=computation_energy,
        integrity_verified=verify_payload(original_hash, task.payload),
        compressed_size_kb=size_kb if payload_size_kb is not None else None,
    )


def calculate_transmission_delay_ms(size_kb: float, bandwidth_mbps: float, base_delay_ms: float) -> float:
    """Calculate transmission delay in milliseconds."""
    size_megabits = (size_kb * 8.0) / 1024.0
    return (size_megabits / max(bandwidth_mbps, 0.1)) * 1000.0 + base_delay_ms


def calculate_communication_energy_j(size_kb: float) -> float:
    """Calculate mobile communication energy for a payload size."""
    return (size_kb / 1024.0) * TX_ENERGY_PER_MB


def estimate_local_energy(device: MobileDevice) -> float:
    """Estimate local compute energy."""
    return device.task.cpu_cycles * LOCAL_ENERGY_COEFF


def estimate_edge_energy(device: MobileDevice, edge_server: EdgeServer) -> float:
    """Estimate mobile energy if offloaded to edge."""
    del edge_server
    return calculate_communication_energy_j(device.task.size_kb) + device.task.cpu_cycles * EDGE_COMPUTE_ENERGY_COEFF


def estimate_cloud_energy(device: MobileDevice) -> float:
    """Estimate mobile energy if offloaded to cloud."""
    return calculate_communication_energy_j(device.task.size_kb) * 1.35 + device.task.cpu_cycles * CLOUD_COMPUTE_ENERGY_COEFF


def joules_to_mah(energy_j: float) -> float:
    """Convert energy consumption into approximate mAh battery usage."""
    return energy_j / (BATTERY_VOLTAGE * MAH_TO_COULOMB)


def build_experiment_result(
    experiment_no: int,
    algorithm: str,
    total_devices: int,
    decisions: list[OffloadDecision],
    execution_time_s: float,
) -> ExperimentResult:
    """Aggregate per-task decisions into experiment metrics."""
    served = sum(1 for decision in decisions if decision.success and decision.integrity_verified)
    total_energy = sum(decision.energy_j for decision in decisions)
    total_delay = sum(decision.delay_ms for decision in decisions)
    battery_used = sum(decision.battery_used_mah for decision in decisions)
    return ExperimentResult(
        experiment_no=experiment_no,
        algorithm=algorithm,
        served_devices=served,
        total_devices=total_devices,
        avg_delay_ms=total_delay / total_devices if total_devices else 0.0,
        total_energy_j=total_energy,
        avg_energy_j=total_energy / total_devices if total_devices else 0.0,
        battery_used_mah=battery_used,
        success_rate=(served / total_devices * 100.0) if total_devices else 0.0,
        execution_time_s=execution_time_s,
        decisions=decisions,
    )


def _cpu_required_ghz(device: MobileDevice) -> float:
    """Small CPU reservation derived from task intensity."""
    intensity = device.task.cpu_cycles / 1_000_000_000
    return max(0.05, min(1.2, intensity / 8.0))
