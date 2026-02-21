"""Topology builder — merge per-device neighbor data into a unified graph model."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Node:
    """A device (router / switch / firewall) in the topology."""

    id: str           # canonical unique key (hostname or IP)
    hostname: str
    device_type: str = ""
    model: str = ""
    os_version: str = ""
    mgmt_ip: str = ""

    def label(self) -> str:
        parts = [self.hostname or self.id]
        if self.model:
            parts.append(self.model)
        if self.os_version:
            parts.append(self.os_version)
        return "\n".join(parts)


@dataclass(frozen=True)
class Edge:
    """A link between two devices."""

    source: str            # node id
    target: str            # node id
    source_intf: str = ""
    target_intf: str = ""

    @property
    def key(self) -> tuple[str, str]:
        """Return a normalised pair so A–B == B–A."""
        return tuple(sorted((self.source, self.target)))  # type: ignore[return-value]


@dataclass
class Topology:
    """Unified network graph built from collected device + neighbor data."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    _seen_edges: set[tuple[str, str]] = field(default_factory=set, repr=False)

    # -- helpers -------------------------------------------------------------
    def _canonicalise(self, name: str) -> str:
        """Lowercase, strip domain suffix for consistent matching."""
        return name.split(".")[0].lower().strip()

    # -- building API --------------------------------------------------------
    def add_node(self, node: Node) -> None:
        cid = self._canonicalise(node.id)
        if cid not in self.nodes:
            self.nodes[cid] = node
            log.debug("Added node %s", cid)

    def add_edge(self, edge: Edge) -> None:
        key = tuple(sorted((
            self._canonicalise(edge.source),
            self._canonicalise(edge.target),
        )))
        if key in self._seen_edges:
            return  # deduplicate
        self._seen_edges.add(key)
        self.edges.append(Edge(
            source=self._canonicalise(edge.source),
            target=self._canonicalise(edge.target),
            source_intf=edge.source_intf,
            target_intf=edge.target_intf,
        ))
        log.debug("Added edge %s <-> %s", key[0], key[1])

    # -- serialisation -------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {
                nid: {
                    "hostname": n.hostname,
                    "device_type": n.device_type,
                    "model": n.model,
                    "os_version": n.os_version,
                    "mgmt_ip": n.mgmt_ip,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "source_intf": e.source_intf,
                    "target_intf": e.target_intf,
                }
                for e in self.edges
            ],
        }


def build_topology(
    device_facts: list[dict[str, Any]],
    neighbor_data: list[dict[str, Any]],
) -> Topology:
    """Merge device-facts and neighbor-data into a :class:`Topology`.

    Parameters
    ----------
    device_facts
        List of dicts returned by :func:`collector.collect_device_info`.
    neighbor_data
        List of dicts returned by :func:`collector.collect_neighbors`.
    """
    topo = Topology()

    # ── 1.  Add every inventoried device as a node ─────────────────────
    _host_to_hostname: dict[str, str] = {}
    for facts in device_facts:
        hostname = facts.get("hostname") or facts.get("host", "")
        node = Node(
            id=hostname or facts.get("host", "unknown"),
            hostname=hostname,
            device_type=facts.get("device_type", ""),
            model=facts.get("model", ""),
            os_version=facts.get("os_version", ""),
            mgmt_ip=facts.get("host", ""),
        )
        topo.add_node(node)
        _host_to_hostname[facts.get("host", "")] = hostname

    # ── 2.  Walk neighbor records and add edges + remote nodes ─────────
    for nd in neighbor_data:
        local_hostname = nd.get("hostname") or _host_to_hostname.get(nd.get("host", ""), nd.get("host", ""))

        for nbr in nd.get("cdp_neighbors", []) + nd.get("lldp_neighbors", []):
            remote_name = nbr.get("remote_device", "")
            if not remote_name:
                continue

            # Ensure remote device exists as a node
            remote_node = Node(
                id=remote_name,
                hostname=remote_name,
                device_type="",
                model=nbr.get("remote_platform", ""),
                os_version=nbr.get("remote_os_version", ""),
                mgmt_ip=nbr.get("remote_mgmt_ip", ""),
            )
            topo.add_node(remote_node)

            topo.add_edge(Edge(
                source=local_hostname,
                target=remote_name,
                source_intf=nbr.get("local_interface", ""),
                target_intf=nbr.get("remote_interface", ""),
            ))

    log.info("Topology: %d nodes, %d edges", len(topo.nodes), len(topo.edges))
    return topo
