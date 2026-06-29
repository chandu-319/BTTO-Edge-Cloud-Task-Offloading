"""Binary Tree Based Task Offloading (BTTO) implementation."""

from __future__ import annotations

from time import perf_counter

from compression import compress_payload, compression_ratio, decompress_payload
from existing import (
    build_experiment_result,
    calculate_communication_energy_j,
    calculate_transmission_delay_ms,
    estimate_cloud_energy,
    estimate_edge_energy,
    estimate_local_energy,
    execute_locally,
    execute_on_cloud,
    execute_on_edge,
)
from models import CloudServer, EdgeServer, ExperimentResult, MobileDevice, OffloadDecision
from security import sha256_digest, verify_payload


def run_btto_algorithm(
    devices: list[MobileDevice],
    edge_servers: list[EdgeServer],
    cloud_server: CloudServer,
    experiment_no: int,
    use_compression: bool = False,
) -> tuple[ExperimentResult, float, float]:
    """Run the proposed binary-tree task offloading policy.

    Returns the experiment result plus total energy before and after the optional
    compression extension.
    """
    start = perf_counter()
    decisions: list[OffloadDecision] = []
    energy_before_compression = 0.0
    energy_after_compression = 0.0

    for device in devices:
        target, edge = choose_btto_target(device, edge_servers, cloud_server)
        before_energy = _estimate_target_energy(device, target, edge)
        energy_before_compression += before_energy

        compressed_size_kb: float | None = None
        if use_compression and target in {"edge", "cloud"}:
            compressed = compress_payload(device.task.payload)
            decompressed = decompress_payload(compressed)
            if verify_payload(sha256_digest(device.task.payload), decompressed):
                compressed_size_kb = device.task.size_kb * compression_ratio(device.task.payload, compressed)

        if target == "local":
            decision = execute_locally(device)
        elif target == "edge" and edge is not None:
            decision = execute_on_edge(device, edge, payload_size_kb=compressed_size_kb)
        else:
            decision = execute_on_cloud(device, cloud_server, payload_size_kb=compressed_size_kb)

        decisions.append(decision)
        energy_after_compression += decision.energy_j

    result = build_experiment_result(
        experiment_no=experiment_no,
        algorithm="Proposed BTTO",
        total_devices=len(devices),
        decisions=decisions,
        execution_time_s=perf_counter() - start,
    )
    return result, energy_before_compression, energy_after_compression


def choose_btto_target(
    device: MobileDevice,
    edge_servers: list[EdgeServer],
    cloud_server: CloudServer,
) -> tuple[str, EdgeServer | None]:
    """Binary decision tree for local, edge, or cloud execution.

    Tree summary:
        1. If local execution meets a relaxed deadline and saves energy, run local.
        2. Otherwise inspect the least-loaded feasible edge server.
        3. If edge delay and energy are acceptable, use edge.
        4. If cloud can meet the deadline better than edge, use cloud.
        5. Fallback to the least-energy option.
    """
    task = device.task
    local_delay = task.cpu_cycles / (device.cpu_ghz * 1_000_000.0)
    local_energy = estimate_local_energy(device)

    best_edge = min(edge_servers, key=lambda item: (item.current_load / item.max_queue, -item.available_cpu()))
    edge_load_ratio = best_edge.current_load / max(best_edge.max_queue, 1)
    cpu_required = max(0.05, min(1.2, (task.cpu_cycles / 1_000_000_000) / 8.0))
    edge_has_capacity = best_edge.can_accept(cpu_required)
    edge_delay = _estimate_edge_delay(device, best_edge)
    edge_energy = estimate_edge_energy(device, best_edge)
    cloud_delay = _estimate_cloud_delay(device, cloud_server)
    cloud_energy = estimate_cloud_energy(device)

    if local_delay <= task.deadline_ms * 0.75 and local_energy <= min(edge_energy, cloud_energy) * 1.05:
        return "local", None

    if task.deadline_ms < 180.0:
        if edge_has_capacity and edge_load_ratio < 0.9 and edge_delay <= task.deadline_ms:
            return "edge", best_edge
        return "local" if local_delay <= cloud_delay else "cloud", None

    if edge_has_capacity:
        if task.network_delay_ms <= 60.0 and edge_load_ratio < 0.85:
            if edge_delay <= task.deadline_ms and edge_energy <= local_energy:
                return "edge", best_edge
        if edge_energy < cloud_energy and edge_delay <= task.deadline_ms * 1.15:
            return "edge", best_edge

    if cloud_delay <= task.deadline_ms and cloud_energy <= local_energy * 0.8:
        return "cloud", None

    options = [
        ("local", None, local_energy, local_delay),
        ("cloud", None, cloud_energy, cloud_delay),
    ]
    if edge_has_capacity:
        options.append(("edge", best_edge, edge_energy, edge_delay))
    feasible = [option for option in options if option[3] <= task.deadline_ms]
    selected = min(feasible or options, key=lambda option: (option[2], option[3]))
    return selected[0], selected[1]


def _estimate_edge_delay(device: MobileDevice, edge_server: EdgeServer) -> float:
    task = device.task
    return (
        calculate_transmission_delay_ms(task.size_kb, task.bandwidth_mbps, task.network_delay_ms)
        + edge_server.queue_delay_ms()
        + task.cpu_cycles / (edge_server.cpu_ghz * 1_000_000.0)
    )


def _estimate_cloud_delay(device: MobileDevice, cloud_server: CloudServer) -> float:
    task = device.task
    return (
        calculate_transmission_delay_ms(
            task.size_kb,
            task.bandwidth_mbps,
            task.network_delay_ms + cloud_server.network_delay_ms,
        )
        + cloud_server.queue_delay_ms()
        + task.cpu_cycles / (cloud_server.cpu_ghz * 1_000_000.0)
    )


def _estimate_target_energy(device: MobileDevice, target: str, edge_server: EdgeServer | None) -> float:
    if target == "local":
        return estimate_local_energy(device)
    if target == "edge" and edge_server is not None:
        return estimate_edge_energy(device, edge_server)
    return estimate_cloud_energy(device)


def estimate_compressed_communication_energy(original_size_kb: float, compressed_size_kb: float) -> tuple[float, float]:
    """Return communication energy before and after compression."""
    return calculate_communication_energy_j(original_size_kb), calculate_communication_energy_j(compressed_size_kb)
