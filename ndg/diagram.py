"""Diagram generators — render a Topology into Graphviz DOT and Mermaid."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ndg.topology import Topology

log = logging.getLogger(__name__)

# ─── Icon hints for device types ────────────────────────────────────────────
_SHAPE_MAP: dict[str, str] = {
    "cisco_ios":      "box3d",
    "cisco_xe":       "box3d",
    "cisco_nxos":     "box3d",
    "arista_eos":     "box3d",
    "paloalto_panos": "octagon",
    "juniper_junos":  "box3d",
    "juniper":        "box3d",
    "fortinet":       "octagon",
    "fortinet_ssh":   "octagon",
    "sonic_ssh":      "box3d",
    "linux":          "box3d",
    "extreme_exos":   "box3d",
    "extreme":        "box3d",
    "extreme_nos":    "box3d",
    "":               "ellipse",
}

_MERMAID_ICON: dict[str, str] = {
    "cisco_ios":      "🔀",
    "cisco_xe":       "🔀",
    "cisco_nxos":     "🔀",
    "arista_eos":     "🔀",
    "paloalto_panos": "🛡️",
    "juniper_junos":  "🔀",
    "juniper":        "🔀",
    "fortinet":       "🛡️",
    "fortinet_ssh":   "🛡️",
    "sonic_ssh":      "🔀",
    "linux":          "🔀",
    "extreme_exos":   "🔀",
    "extreme":        "🔀",
    "extreme_nos":    "🔀",
    "":               "💻",
}


# ─── GRAPHVIZ ───────────────────────────────────────────────────────────────

def _gv_safe(text: str) -> str:
    """Escape a string for Graphviz labels."""
    return text.replace('"', '\\"').replace("\n", "\\n")


def generate_graphviz_dot(topo: Topology) -> str:
    """Return a Graphviz DOT source string for the topology."""
    lines: list[str] = [
        "graph network_topology {",
        '    graph [layout=neato, overlap=false, splines=true, bgcolor="#f8f9fa"];',
        '    node  [style=filled, fillcolor="#dce6f1", fontname="Helvetica", fontsize=10];',
        '    edge  [fontname="Helvetica", fontsize=8, color="#555555"];',
        "",
    ]

    # Nodes
    for nid, node in topo.nodes.items():
        shape = _SHAPE_MAP.get(node.device_type, "ellipse")
        label = _gv_safe(node.label())
        lines.append(f'    "{nid}" [label="{label}", shape={shape}];')

    lines.append("")

    # Edges
    for edge in topo.edges:
        label_parts: list[str] = []
        if edge.source_intf:
            label_parts.append(edge.source_intf)
        if edge.target_intf:
            label_parts.append(edge.target_intf)
        elabel = " ↔ ".join(label_parts) if label_parts else ""
        lines.append(
            f'    "{edge.source}" -- "{edge.target}" [label="{_gv_safe(elabel)}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def render_graphviz(
    topo: Topology,
    output_path: Path,
    fmt: str = "png",
) -> Path:
    """Render the topology to an image file using the ``graphviz`` package.

    Requires the ``graphviz`` Python package **and** the ``dot`` binary.
    Returns the path of the generated file.
    """
    try:
        import graphviz  # type: ignore[import-untyped]
    except ImportError:
        log.error("Install the 'graphviz' Python package:  pip install graphviz")
        raise

    dot_src = generate_graphviz_dot(topo)
    src = graphviz.Source(dot_src)
    rendered = src.render(
        filename=str(output_path.with_suffix("")),
        format=fmt,
        cleanup=True,
    )
    log.info("Graphviz diagram saved to %s", rendered)
    return Path(rendered)


# ─── MERMAID ────────────────────────────────────────────────────────────────

def _mermaid_id(name: str) -> str:
    """Create a Mermaid-safe node ID."""
    return name.replace("-", "_").replace(".", "_").replace("/", "_")


def generate_mermaid(topo: Topology) -> str:
    """Return Mermaid graph syntax for the topology."""
    lines: list[str] = ["graph TD"]

    # Nodes
    for nid, node in topo.nodes.items():
        mid = _mermaid_id(nid)
        icon = _MERMAID_ICON.get(node.device_type, "💻")
        label = f"{icon} {node.hostname or nid}"
        if node.model:
            label += f"<br/>{node.model}"
        if node.os_version:
            label += f"<br/>{node.os_version}"
        lines.append(f'    {mid}["{label}"]')

    lines.append("")

    # Edges
    for edge in topo.edges:
        src = _mermaid_id(edge.source)
        tgt = _mermaid_id(edge.target)
        label_parts: list[str] = []
        if edge.source_intf:
            label_parts.append(edge.source_intf)
        if edge.target_intf:
            label_parts.append(edge.target_intf)
        if label_parts:
            elabel = " ↔ ".join(label_parts)
            lines.append(f"    {src} -- \"{elabel}\" --- {tgt}")
        else:
            lines.append(f"    {src} --- {tgt}")

    # Styling
    lines.append("")
    lines.append("    %% Styling")
    lines.append("    classDef router fill:#dce6f1,stroke:#333,stroke-width:1px;")
    lines.append("    classDef firewall fill:#f9d6d5,stroke:#333,stroke-width:1px;")

    routers: list[str] = []
    firewalls: list[str] = []
    for nid, node in topo.nodes.items():
        mid = _mermaid_id(nid)
        if "paloalto" in node.device_type or "fortinet" in node.device_type:
            firewalls.append(mid)
        else:
            routers.append(mid)
    if routers:
        lines.append(f"    class {','.join(routers)} router;")
    if firewalls:
        lines.append(f"    class {','.join(firewalls)} firewall;")

    return "\n".join(lines)


def save_mermaid(topo: Topology, output_path: Path) -> Path:
    """Write Mermaid diagram source to a ``.mmd`` file."""
    mmd = generate_mermaid(topo)
    output_path = output_path.with_suffix(".mmd")
    output_path.write_text(mmd, encoding="utf-8")
    log.info("Mermaid diagram saved to %s", output_path)
    return output_path
