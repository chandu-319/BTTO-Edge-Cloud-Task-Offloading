"""Tkinter graphical interface for the BTTO edge-cloud project."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable

from graphs import (
    plot_battery_consumption,
    plot_energy_consumption,
    plot_extension_energy,
    plot_served_mobile_devices,
)
from simulation import OffloadSimulation, SummaryMetrics


class EdgeCloudApp:
    """Main Tkinter application."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BTTO Edge-Cloud Task Offloading")
        self.root.geometry("1120x720")
        self.root.minsize(980, 620)
        self.simulation = OffloadSimulation()

        self.num_nodes_var = tk.StringVar(value="50")
        self.status_var = tk.StringVar(value="Ready")
        self._build_widgets()

    def _build_widgets(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(main)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Num Nodes").pack(side=tk.LEFT, padx=(0, 8))
        node_entry = ttk.Entry(top, textvariable=self.num_nodes_var, width=12)
        node_entry.pack(side=tk.LEFT, padx=(0, 12))

        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.X, pady=10)

        buttons: list[tuple[str, Callable[[], None]]] = [
            ("Generate Edge Network", self.generate_network),
            ("Initialize BTTO Algorithm", self.initialize_btto),
            ("Run Proposed Offload Simulation", self.run_proposed),
            ("Run Existing Task Offload", self.run_existing),
            ("Energy Consumption Graph", self.show_energy_graph),
            ("Served MD Graph", self.show_served_graph),
            ("Battery Consumption Graph", self.show_battery_graph),
            ("Extension Energy Graph", self.show_extension_graph),
            ("Exit", self.root.destroy),
        ]

        for index, (text, command) in enumerate(buttons):
            button = ttk.Button(button_frame, text=text, command=command)
            button.grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)

        for column in range(3):
            button_frame.columnconfigure(column, weight=1)

        self.log_area = scrolledtext.ScrolledText(main, wrap=tk.WORD, height=25, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=(6, 8))

        footer = ttk.Frame(main)
        footer.pack(fill=tk.X)
        ttk.Label(footer, textvariable=self.status_var).pack(side=tk.LEFT)
        ttk.Button(footer, text="Clear Logs", command=self.clear_logs).pack(side=tk.RIGHT)

        self._log("BTTO Edge-Cloud Computing Simulation is ready.")
        self._log("Enter Num Nodes such as 50, 100, or 200, then generate the network.")

    def generate_network(self) -> None:
        """Handle network generation."""
        try:
            num_nodes = self._read_num_nodes()
            message = self.simulation.generate_network(num_nodes)
            self._log(message)
            self._log("Random seed fixed at 42 for reproducible task generation.")
            self.status_var.set("Network generated")
        except Exception as exc:
            self._show_error(exc)

    def initialize_btto(self) -> None:
        """Initialize BTTO."""
        try:
            self._log(self.simulation.initialize_btto())
            self.status_var.set("BTTO initialized")
        except Exception as exc:
            self._show_error(exc)

    def run_existing(self) -> None:
        """Run existing greedy algorithm in a worker thread."""
        self._run_worker("Running existing greedy offload...", self._run_existing_impl)

    def run_proposed(self) -> None:
        """Run proposed BTTO algorithm in a worker thread."""
        self._run_worker("Running proposed BTTO offload simulation...", self._run_proposed_impl)

    def show_energy_graph(self) -> None:
        try:
            self._ensure_comparison_results()
            self._plot(plot_energy_consumption)
        except Exception as exc:
            self._show_error(exc)

    def show_served_graph(self) -> None:
        try:
            self._ensure_comparison_results()
            self._plot(plot_served_mobile_devices)
        except Exception as exc:
            self._show_error(exc)

    def show_battery_graph(self) -> None:
        try:
            self._ensure_comparison_results()
            self._plot(plot_battery_consumption)
        except Exception as exc:
            self._show_error(exc)

    def show_extension_graph(self) -> None:
        try:
            if not self.simulation.results.proposed:
                raise RuntimeError("Run Proposed Offload Simulation at least once before opening this graph.")
            self._plot(plot_extension_energy)
        except Exception as exc:
            self._show_error(exc)

    def clear_logs(self) -> None:
        self.log_area.delete("1.0", tk.END)

    def _run_existing_impl(self) -> None:
        result = self.simulation.run_existing_experiment()
        self._log_lines(self.simulation.latest_result_lines([result]))
        self._log_summary(self.simulation.get_summary("Existing Greedy"))
        self._set_status(f"Existing experiment {result.experiment_no} complete")

    def _run_proposed_impl(self) -> None:
        result = self.simulation.run_proposed_experiment()
        self._log_lines(self.simulation.latest_result_lines([result]))
        self._log_summary(self.simulation.get_summary("Proposed BTTO"))
        self._log("Compression extension and SHA-256 integrity verification completed.")
        self._set_status(f"Proposed experiment {result.experiment_no} complete")

    def _run_worker(self, status: str, task: Callable[[], None]) -> None:
        self.status_var.set(status)
        self._log(status)

        def wrapper() -> None:
            try:
                task()
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._show_error(error))

        threading.Thread(target=wrapper, daemon=True).start()

    def _plot(self, plotter: Callable[[object], None]) -> None:
        try:
            plotter(self.simulation.results)
        except Exception as exc:
            self._show_error(exc)

    def _ensure_comparison_results(self) -> None:
        if not self.simulation.results.existing or not self.simulation.results.proposed:
            raise RuntimeError(
                "Run Existing Task Offload and Proposed Offload Simulation at least once before opening comparison graphs."
            )

    def _read_num_nodes(self) -> int:
        value = int(self.num_nodes_var.get().strip())
        if value <= 0:
            raise ValueError("Num Nodes must be a positive integer.")
        return value

    def _log_summary(self, summary: SummaryMetrics | None) -> None:
        if summary is None:
            return
        self._log(
            f"{summary.algorithm} Average Results -> "
            f"Avg Delay: {summary.avg_delay_ms:.2f} ms, "
            f"Avg Energy: {summary.avg_energy_j:.4f} J, "
            f"Served MD: {summary.served_devices:.2f}, "
            f"Battery Usage: {summary.battery_used_mah:.4f} mAh, "
            f"Success Rate: {summary.success_rate:.2f}%, "
            f"Execution Time: {summary.execution_time_s:.4f} s"
        )

    def _log_lines(self, lines: list[str]) -> None:
        for line in lines:
            self._log(line)

    def _log(self, message: str) -> None:
        def append() -> None:
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END)

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.root.after(0, append)

    def _set_status(self, message: str) -> None:
        if threading.current_thread() is threading.main_thread():
            self.status_var.set(message)
        else:
            self.root.after(0, lambda: self.status_var.set(message))

    def _show_error(self, exc: Exception) -> None:
        message = str(exc)
        self.status_var.set("Error")
        self._log(f"ERROR: {message}")
        messagebox.showerror("BTTO Simulation Error", message)


def run_app() -> None:
    """Start the Tkinter event loop."""
    root = tk.Tk()
    app = EdgeCloudApp(root)
    root.mainloop()
