"""Reproducible edge-cloud network generation."""

from __future__ import annotations

import random
from typing import Sequence

from models import CloudServer, EdgeServer, MobileDevice, Task


DEFAULT_RANDOM_SEED = 42


def generate_edge_network(num_nodes: int, seed: int = DEFAULT_RANDOM_SEED) -> tuple[list[MobileDevice], list[EdgeServer], CloudServer]:
    """Generate mobile devices, three edge servers, and one cloud server.

    Args:
        num_nodes: Number of mobile devices to create.
        seed: Fixed seed for reproducible experiments.

    Raises:
        ValueError: If num_nodes is not positive.
    """
    if num_nodes <= 0:
        raise ValueError("Num Nodes must be greater than zero.")

    rng = random.Random(seed)
    devices = [_create_device(device_id=i + 1, rng=rng) for i in range(num_nodes)]
    edge_servers = [
        EdgeServer(server_id=1, cpu_ghz=18.0, max_queue=max(12, num_nodes // 3)),
        EdgeServer(server_id=2, cpu_ghz=20.0, max_queue=max(12, num_nodes // 3)),
        EdgeServer(server_id=3, cpu_ghz=22.0, max_queue=max(12, num_nodes // 3)),
    ]
    cloud_server = CloudServer(cpu_ghz=80.0, network_delay_ms=75.0)
    return devices, edge_servers, cloud_server


def clone_network(
    devices: Sequence[MobileDevice],
    edge_servers: Sequence[EdgeServer],
    cloud_server: CloudServer,
) -> tuple[list[MobileDevice], list[EdgeServer], CloudServer]:
    """Create fresh server state while keeping generated mobile tasks intact."""
    cloned_edges = [
        EdgeServer(server_id=edge.server_id, cpu_ghz=edge.cpu_ghz, max_queue=edge.max_queue)
        for edge in edge_servers
    ]
    cloned_cloud = CloudServer(cpu_ghz=cloud_server.cpu_ghz, network_delay_ms=cloud_server.network_delay_ms)
    return list(devices), cloned_edges, cloned_cloud


def _create_device(device_id: int, rng: random.Random) -> MobileDevice:
    size_kb = rng.uniform(300.0, 5000.0)
    cpu_cycles = rng.uniform(0.4, 8.0) * 1_000_000_000
    payload = _build_payload(size_kb=size_kb, rng=rng)
    task = Task(
        task_id=device_id,
        size_kb=size_kb,
        cpu_cycles=cpu_cycles,
        deadline_ms=rng.uniform(80.0, 750.0),
        bandwidth_mbps=rng.uniform(5.0, 35.0),
        network_delay_ms=rng.uniform(8.0, 90.0),
        payload=payload,
    )
    return MobileDevice(
        device_id=device_id,
        cpu_ghz=rng.uniform(1.0, 3.2),
        battery_level_mah=rng.uniform(1200.0, 5000.0),
        task=task,
    )


def _build_payload(size_kb: float, rng: random.Random) -> bytes:
    """Build a moderately compressible representative payload sample."""
    target_bytes = max(1024, min(16 * 1024, int(size_kb * 1024)))
    patterns = [b"sensor-temperature,", b"location-edge-node,", b"video-frame-metadata,"]
    pattern = rng.choice(patterns)
    structured_len = int(target_bytes * 0.78)
    noise_len = target_bytes - structured_len
    structured = (pattern * ((structured_len // len(pattern)) + 1))[:structured_len]
    noise = rng.randbytes(noise_len)
    return structured + noise
