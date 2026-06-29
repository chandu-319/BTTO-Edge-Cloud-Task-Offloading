"""Matplotlib graph generation for simulation comparisons."""

from __future__ import annotations

import matplotlib.pyplot as plt

from models import ExperimentResult, SimulationResults


def plot_served_mobile_devices(results: SimulationResults) -> None:
    """Plot served mobile devices for existing and proposed algorithms."""
    _ensure_comparison(results)
    plt.figure("Served Mobile Devices")
    plt.plot(_experiment_numbers(results.existing), [item.served_devices for item in results.existing], marker="o", label="Existing")
    plt.plot(_experiment_numbers(results.proposed), [item.served_devices for item in results.proposed], marker="s", label="Proposed BTTO")
    _finish_plot("Number of Experiments vs Number of Served Mobile Devices", "Experiment", "Served Mobile Devices")


def plot_energy_consumption(results: SimulationResults) -> None:
    """Plot total energy consumption."""
    _ensure_comparison(results)
    plt.figure("Energy Consumption")
    plt.plot(_experiment_numbers(results.existing), [item.total_energy_j for item in results.existing], marker="o", label="Existing")
    plt.plot(_experiment_numbers(results.proposed), [item.total_energy_j for item in results.proposed], marker="s", label="Proposed BTTO")
    _finish_plot("Number of Experiments vs Energy Consumption", "Experiment", "Energy Consumption (J)")


def plot_battery_consumption(results: SimulationResults) -> None:
    """Plot battery consumption in mAh."""
    _ensure_comparison(results)
    plt.figure("Battery Consumption")
    plt.plot(_experiment_numbers(results.existing), [item.battery_used_mah for item in results.existing], marker="o", label="Existing")
    plt.plot(_experiment_numbers(results.proposed), [item.battery_used_mah for item in results.proposed], marker="s", label="Proposed BTTO")
    _finish_plot("Number of Experiments vs Battery Consumption", "Experiment", "Battery Consumption (mAh)")


def plot_extension_energy(results: SimulationResults) -> None:
    """Plot proposed energy before and after zlib compression."""
    if not results.extension_before_energy or not results.extension_after_energy:
        raise ValueError("Run the proposed BTTO simulation before plotting extension energy.")
    experiments = list(range(1, len(results.extension_before_energy) + 1))
    plt.figure("Extension Energy")
    plt.plot(experiments, results.extension_before_energy, marker="o", label="Before Compression")
    plt.plot(experiments, results.extension_after_energy, marker="s", label="After Compression")
    _finish_plot("Extension Energy Graph: Before vs After Compression", "Experiment", "Energy Consumption (J)")


def _experiment_numbers(results: list[ExperimentResult]) -> list[int]:
    """Return X-axis values based only on the number of stored results."""
    return list(range(1, len(results) + 1))


def _finish_plot(title: str, xlabel: str, ylabel: str) -> None:
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True, linestyle="--", alpha=0.45)
    plt.legend()
    plt.tight_layout()
    plt.show()


def _ensure_comparison(results: SimulationResults) -> None:
    if not results.existing or not results.proposed:
        raise ValueError("Run both existing and proposed simulations before plotting this comparison.")
