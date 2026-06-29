"""Domain models for the Edge-Cloud task offloading simulation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Task:
    """A generated mobile task with delay and compute requirements."""

    task_id: int
    size_kb: float
    cpu_cycles: float
    deadline_ms: float
    bandwidth_mbps: float
    network_delay_ms: float
    payload: bytes

    @property
    def size_mb(self) -> float:
        """Return task size in megabytes."""
        return self.size_kb / 1024.0


@dataclass(slots=True)
class MobileDevice:
    """Mobile device that owns one offloadable task."""

    device_id: int
    cpu_ghz: float
    battery_level_mah: float
    task: Task


@dataclass(slots=True)
class EdgeServer:
    """Edge server with bounded CPU and task queue capacity."""

    server_id: int
    cpu_ghz: float
    max_queue: int
    current_load: int = 0
    used_cpu_ghz: float = 0.0

    def available_cpu(self) -> float:
        """Return available CPU capacity in GHz."""
        return max(self.cpu_ghz - self.used_cpu_ghz, 0.0)

    def queue_delay_ms(self) -> float:
        """Estimate queue delay from current load."""
        return self.current_load * 8.0

    def can_accept(self, cpu_required_ghz: float) -> bool:
        """Return whether the edge server can accept another task."""
        return self.current_load < self.max_queue and self.available_cpu() >= cpu_required_ghz

    def allocate(self, cpu_required_ghz: float) -> None:
        """Reserve a small amount of CPU and queue space for a task."""
        self.current_load += 1
        self.used_cpu_ghz = min(self.cpu_ghz, self.used_cpu_ghz + cpu_required_ghz)


@dataclass(slots=True)
class CloudServer:
    """Cloud server model."""

    cpu_ghz: float
    network_delay_ms: float
    current_load: int = 0

    def queue_delay_ms(self) -> float:
        """Estimate cloud queue delay."""
        return self.current_load * 12.0

    def allocate(self) -> None:
        """Record one task allocation."""
        self.current_load += 1


@dataclass(slots=True)
class OffloadDecision:
    """Detailed result of executing one task using an offloading policy."""

    device_id: int
    target: str
    success: bool
    delay_ms: float
    energy_j: float
    battery_used_mah: float
    transmission_delay_ms: float
    execution_delay_ms: float
    queue_delay_ms: float
    communication_energy_j: float
    computation_energy_j: float
    integrity_verified: bool
    compressed_size_kb: float | None = None


@dataclass(slots=True)
class ExperimentResult:
    """Aggregated metrics for one experiment and one algorithm."""

    experiment_no: int
    algorithm: str
    served_devices: int
    total_devices: int
    avg_delay_ms: float
    total_energy_j: float
    avg_energy_j: float
    battery_used_mah: float
    success_rate: float
    execution_time_s: float
    decisions: list[OffloadDecision] = field(default_factory=list)


@dataclass(slots=True)
class SimulationResults:
    """Container for all graphable simulation outputs."""

    existing: list[ExperimentResult] = field(default_factory=list)
    proposed: list[ExperimentResult] = field(default_factory=list)
    extension_before_energy: list[float] = field(default_factory=list)
    extension_after_energy: list[float] = field(default_factory=list)
