"""Experiment orchestration for the edge-cloud offloading application."""

from __future__ import annotations

from dataclasses import dataclass

from btto import run_btto_algorithm
from existing import run_existing_algorithm
from models import CloudServer, EdgeServer, ExperimentResult, MobileDevice, SimulationResults
from network import DEFAULT_RANDOM_SEED, clone_network, generate_edge_network

DEFAULT_EXPERIMENTS = 10


@dataclass(slots=True)
class SummaryMetrics:
    """Human-readable aggregate metrics for the GUI."""

    algorithm: str
    avg_delay_ms: float
    avg_energy_j: float
    served_devices: float
    battery_used_mah: float
    success_rate: float
    execution_time_s: float


class OffloadSimulation:
    """Manage generated networks, algorithm execution, and stored results."""

    def __init__(self, iterations: int = DEFAULT_EXPERIMENTS, base_seed: int = DEFAULT_RANDOM_SEED) -> None:
        self.iterations = self._validate_iterations(iterations)
        self.base_seed = base_seed
        self.num_nodes = 0
        self.devices: list[MobileDevice] = []
        self.edge_servers: list[EdgeServer] = []
        self.cloud_server: CloudServer | None = None
        self.results = SimulationResults()
        self.btto_initialized = False

    def generate_network(self, num_nodes: int) -> str:
        """Generate and store the initial edge-cloud network."""
        self.num_nodes = num_nodes
        self.devices, self.edge_servers, self.cloud_server = generate_edge_network(num_nodes, self.base_seed)
        self.results = SimulationResults()
        self.btto_initialized = False
        return (
            f"Generated network with {len(self.devices)} mobile devices, "
            f"{len(self.edge_servers)} edge servers, and 1 cloud server."
        )

    def initialize_btto(self) -> str:
        """Mark BTTO as initialized after a network has been generated."""
        self._ensure_network()
        self.btto_initialized = True
        return (
            "BTTO initialized with binary decisions using deadline, edge load, "
            "available CPU, network delay, and estimated energy."
        )

    def run_existing(self, iterations: int | None = None) -> list[ExperimentResult]:
        """Run the greedy baseline for the configured number of experiments."""
        self._ensure_network()
        experiment_count = self._resolve_iterations(iterations)
        self.results.existing.clear()
        for experiment_no in range(1, experiment_count + 1):
            devices, edges, cloud = generate_edge_network(self.num_nodes, self.base_seed + experiment_no)
            result = run_existing_algorithm(devices, edges, cloud, experiment_no)
            self.results.existing.append(result)
        return self.results.existing

    def run_existing_experiment(self) -> ExperimentResult:
        """Append one greedy-baseline result for the next experiment number."""
        self._ensure_network()
        experiment_no = len(self.results.existing) + 1
        devices, edges, cloud = generate_edge_network(self.num_nodes, self.base_seed + experiment_no)
        result = run_existing_algorithm(devices, edges, cloud, experiment_no)
        self.results.existing.append(result)
        return result

    def run_proposed(self, iterations: int | None = None) -> list[ExperimentResult]:
        """Run proposed BTTO with zlib compression extension enabled."""
        self._ensure_network()
        if not self.btto_initialized:
            self.initialize_btto()

        experiment_count = self._resolve_iterations(iterations)
        self.results.proposed.clear()
        self.results.extension_before_energy.clear()
        self.results.extension_after_energy.clear()
        for experiment_no in range(1, experiment_count + 1):
            devices, edges, cloud = generate_edge_network(self.num_nodes, self.base_seed + experiment_no)
            result, before, after = run_btto_algorithm(
                devices=devices,
                edge_servers=edges,
                cloud_server=cloud,
                experiment_no=experiment_no,
                use_compression=True,
            )
            self.results.proposed.append(result)
            self.results.extension_before_energy.append(before)
            self.results.extension_after_energy.append(after)

        return self.results.proposed

    def run_proposed_experiment(self) -> ExperimentResult:
        """Append one proposed-BTTO result for the next experiment number."""
        self._ensure_network()
        if not self.btto_initialized:
            self.initialize_btto()

        experiment_no = len(self.results.proposed) + 1
        devices, edges, cloud = generate_edge_network(self.num_nodes, self.base_seed + experiment_no)
        result, before, after = run_btto_algorithm(
            devices=devices,
            edge_servers=edges,
            cloud_server=cloud,
            experiment_no=experiment_no,
            use_compression=True,
        )
        self.results.proposed.append(result)
        self.results.extension_before_energy.append(before)
        self.results.extension_after_energy.append(after)
        return result

    def run_all(self, iterations: int | None = None) -> SimulationResults:
        """Run both algorithms so all comparison graphs can be generated."""
        experiment_count = self._resolve_iterations(iterations)
        self.run_existing(experiment_count)
        self.run_proposed(experiment_count)
        return self.results

    def get_summary(self, algorithm: str) -> SummaryMetrics | None:
        """Return average metrics for an algorithm name."""
        source = self.results.proposed if algorithm.lower().startswith("proposed") else self.results.existing
        if not source:
            return None
        count = len(source)
        return SummaryMetrics(
            algorithm=algorithm,
            avg_delay_ms=sum(item.avg_delay_ms for item in source) / count,
            avg_energy_j=sum(item.avg_energy_j for item in source) / count,
            served_devices=sum(item.served_devices for item in source) / count,
            battery_used_mah=sum(item.battery_used_mah for item in source) / count,
            success_rate=sum(item.success_rate for item in source) / count,
            execution_time_s=sum(item.execution_time_s for item in source) / count,
        )

    def latest_result_lines(self, results: list[ExperimentResult]) -> list[str]:
        """Format experiment results for the scrolling log area."""
        lines: list[str] = []
        for result in results:
            lines.append(
                f"Experiment {result.experiment_no:02d} | {result.algorithm} | "
                f"Served MD: {result.served_devices}/{result.total_devices} | "
                f"Avg Delay: {result.avg_delay_ms:.2f} ms | "
                f"Avg Energy: {result.avg_energy_j:.4f} J | "
                f"Battery: {result.battery_used_mah:.4f} mAh | "
                f"Success: {result.success_rate:.2f}% | "
                f"Time: {result.execution_time_s:.4f} s"
            )
        return lines

    def _ensure_network(self) -> None:
        if self.num_nodes <= 0 or self.cloud_server is None:
            raise RuntimeError("Please generate the edge network first.")

    def set_iterations(self, iterations: int) -> None:
        """Update the number of experiments used by future simulation runs."""
        self.iterations = self._validate_iterations(iterations)

    def _resolve_iterations(self, iterations: int | None) -> int:
        if iterations is None:
            return self.iterations
        self.set_iterations(iterations)
        return self.iterations

    @staticmethod
    def _validate_iterations(iterations: int) -> int:
        if iterations <= 0:
            raise ValueError("Number of experiments must be greater than zero.")
        return iterations

    def get_initial_network_snapshot(self) -> tuple[list[MobileDevice], list[EdgeServer], CloudServer]:
        """Return a fresh copy of the initially generated network state."""
        self._ensure_network()
        assert self.cloud_server is not None
        return clone_network(self.devices, self.edge_servers, self.cloud_server)
