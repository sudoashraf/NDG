"""NDG CLI — command-line interface for the Network Diagram Generator."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from ndg import __version__
from ndg.collector import collect_device_info, collect_neighbors
from ndg.diagram import generate_graphviz_dot, generate_mermaid, render_graphviz, save_mermaid
from ndg.inventory import load_inventory
from ndg.storage import load_json, save_json
from ndg.topology import build_topology

console = Console()
log = logging.getLogger("ndg")


# ─── CLI Argument Parser ───────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ndg",
        description="Network Diagram / Topology Generator — collect device facts, "
                    "discover neighbors, and build visual network diagrams.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"ndg {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="Increase verbosity (-v INFO, -vv DEBUG).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── collect ─────────────────────────────────────────────────────────
    p_collect = sub.add_parser(
        "collect",
        help="SSH into devices and collect baseline facts (hostname, model, OS, interfaces).",
    )
    p_collect.add_argument(
        "-i", "--inventory", required=True, type=Path,
        help="Path to the YAML inventory file.",
    )
    p_collect.add_argument(
        "-o", "--output", default=Path("output/device_facts.json"), type=Path,
        help="Output JSON file for device facts.",
    )

    # ── neighbors ───────────────────────────────────────────────────────
    p_nbr = sub.add_parser(
        "neighbors",
        help="Query CDP/LLDP neighbor data from devices.",
    )
    p_nbr.add_argument(
        "-i", "--inventory", required=True, type=Path,
        help="Path to the YAML inventory file.",
    )
    p_nbr.add_argument(
        "-o", "--output", default=Path("output/neighbors.json"), type=Path,
        help="Output JSON file for neighbor data.",
    )

    # ── diagram ─────────────────────────────────────────────────────────
    p_dia = sub.add_parser(
        "diagram",
        help="Build topology and render diagrams from collected data.",
    )
    p_dia.add_argument(
        "--facts", default=Path("output/device_facts.json"), type=Path,
        help="Device facts JSON (from 'collect').",
    )
    p_dia.add_argument(
        "--neighbors", default=Path("output/neighbors.json"), type=Path,
        help="Neighbor data JSON (from 'neighbors').",
    )
    p_dia.add_argument(
        "-o", "--output-dir", default=Path("output"), type=Path,
        help="Directory for generated diagrams.",
    )
    p_dia.add_argument(
        "-f", "--format", nargs="+", default=["mermaid", "dot"],
        choices=["mermaid", "dot", "png", "svg", "pdf"],
        help="Output format(s). 'dot' writes raw DOT source; png/svg/pdf require graphviz binary.",
    )

    # ── show ────────────────────────────────────────────────────────────
    p_show = sub.add_parser(
        "show",
        help="Display collected data in a rich table.",
    )
    p_show.add_argument(
        "what", choices=["facts", "neighbors", "topology"],
        help="What to display.",
    )
    p_show.add_argument(
        "--facts", default=Path("output/device_facts.json"), type=Path,
    )
    p_show.add_argument(
        "--neighbors", default=Path("output/neighbors.json"), type=Path,
    )

    # ── demo ────────────────────────────────────────────────────────────
    sub.add_parser(
        "demo",
        help="Run with built-in sample data (no real devices required).",
    )

    return parser


# ─── Command Handlers ──────────────────────────────────────────────────────

def _cmd_collect(args: argparse.Namespace) -> None:
    creds_list = load_inventory(args.inventory)
    if not creds_list:
        console.print("[yellow]No devices in inventory.[/yellow]")
        return

    results: list[dict[str, Any]] = []
    for creds in creds_list:
        console.print(f"[cyan]Collecting facts from {creds.host} …[/cyan]")
        info = collect_device_info(creds)
        results.append(info)
        if info["errors"]:
            console.print(f"  [yellow]⚠ Errors: {info['errors']}[/yellow]")
        else:
            console.print(f"  [green]✓ {info['hostname']} — {info['model']} — {info['os_version']}[/green]")

    save_json(results, args.output)
    console.print(f"\n[bold green]Saved {len(results)} device fact(s) → {args.output}[/bold green]")


def _cmd_neighbors(args: argparse.Namespace) -> None:
    creds_list = load_inventory(args.inventory)
    if not creds_list:
        console.print("[yellow]No devices in inventory.[/yellow]")
        return

    results: list[dict[str, Any]] = []
    for creds in creds_list:
        console.print(f"[cyan]Querying neighbors on {creds.host} …[/cyan]")
        nbrs = collect_neighbors(creds)
        results.append(nbrs)
        total = len(nbrs.get("cdp_neighbors", [])) + len(nbrs.get("lldp_neighbors", []))
        console.print(f"  [green]✓ Found {total} neighbor(s)[/green]")

    save_json(results, args.output)
    console.print(f"\n[bold green]Saved neighbor data → {args.output}[/bold green]")


def _cmd_diagram(args: argparse.Namespace) -> None:
    facts = load_json(args.facts)
    nbrs = load_json(args.neighbors) if args.neighbors.exists() else []

    topo = build_topology(facts, nbrs)
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    for fmt in args.format:
        if fmt == "mermaid":
            p = save_mermaid(topo, out_dir / "topology.mmd")
            console.print(f"[green]Mermaid diagram → {p}[/green]")
            # Also print to terminal for quick preview
            console.print("\n[bold]Mermaid source:[/bold]")
            console.print(generate_mermaid(topo))
        elif fmt == "dot":
            dot_src = generate_graphviz_dot(topo)
            dot_path = out_dir / "topology.dot"
            dot_path.write_text(dot_src, encoding="utf-8")
            console.print(f"[green]Graphviz DOT → {dot_path}[/green]")
        else:
            # png, svg, pdf — needs graphviz binary
            try:
                p = render_graphviz(topo, out_dir / "topology", fmt=fmt)
                console.print(f"[green]Graphviz {fmt.upper()} → {p}[/green]")
            except Exception as exc:
                console.print(f"[red]Failed to render {fmt}: {exc}[/red]")


def _cmd_show(args: argparse.Namespace) -> None:
    if args.what == "facts":
        data = load_json(args.facts)
        table = Table(title="Device Facts", show_lines=True)
        table.add_column("Host", style="cyan")
        table.add_column("Hostname", style="bold")
        table.add_column("Model")
        table.add_column("OS Version")
        table.add_column("Type")
        table.add_column("Interfaces", justify="right")
        for d in data:
            table.add_row(
                d.get("host", ""),
                d.get("hostname", ""),
                d.get("model", ""),
                d.get("os_version", ""),
                d.get("device_type", ""),
                str(len(d.get("interfaces", []))),
            )
        console.print(table)

    elif args.what == "neighbors":
        data = load_json(args.neighbors)
        table = Table(title="Neighbor Data", show_lines=True)
        table.add_column("Host", style="cyan")
        table.add_column("Hostname", style="bold")
        table.add_column("Protocol")
        table.add_column("Local Intf")
        table.add_column("Remote Device")
        table.add_column("Remote Intf")
        for nd in data:
            host = nd.get("host", "")
            hostname = nd.get("hostname", "")
            for nbr in nd.get("cdp_neighbors", []):
                table.add_row(
                    host, hostname, "CDP",
                    nbr.get("local_interface", ""),
                    nbr.get("remote_device", ""),
                    nbr.get("remote_interface", ""),
                )
            for nbr in nd.get("lldp_neighbors", []):
                table.add_row(
                    host, hostname, "LLDP",
                    nbr.get("local_interface", ""),
                    nbr.get("remote_device", ""),
                    nbr.get("remote_interface", ""),
                )
        console.print(table)

    elif args.what == "topology":
        facts = load_json(args.facts)
        nbrs = load_json(args.neighbors) if args.neighbors.exists() else []
        topo = build_topology(facts, nbrs)

        table = Table(title="Topology Nodes", show_lines=True)
        table.add_column("ID", style="cyan")
        table.add_column("Hostname", style="bold")
        table.add_column("Model")
        table.add_column("OS Version")
        table.add_column("Mgmt IP")
        for nid, n in topo.nodes.items():
            table.add_row(nid, n.hostname, n.model, n.os_version, n.mgmt_ip)
        console.print(table)

        etable = Table(title="Topology Edges", show_lines=True)
        etable.add_column("Source", style="cyan")
        etable.add_column("Src Intf")
        etable.add_column("Target", style="green")
        etable.add_column("Tgt Intf")
        for e in topo.edges:
            etable.add_row(e.source, e.source_intf, e.target, e.target_intf)
        console.print(etable)


def _cmd_demo(_args: argparse.Namespace) -> None:
    """Run a full pipeline with realistic sample data — no SSH needed."""
    console.print("[bold cyan]━━━ NDG Demo Mode ━━━[/bold cyan]\n")

    # Simulated device facts
    sample_facts = [
        {
            "host": "10.0.0.1",
            "device_type": "cisco_ios",
            "hostname": "core-rtr-01",
            "model": "ISR4451-X",
            "os_version": "17.03.04",
            "interfaces": [
                {"name": "GigabitEthernet0/0", "ip_address": "10.0.0.1", "status": "up", "protocol": "up"},
                {"name": "GigabitEthernet0/1", "ip_address": "10.1.0.1", "status": "up", "protocol": "up"},
                {"name": "GigabitEthernet0/2", "ip_address": "10.2.0.1", "status": "up", "protocol": "up"},
                {"name": "Loopback0", "ip_address": "1.1.1.1", "status": "up", "protocol": "up"},
            ],
            "collected_at": "2026-02-21T12:00:00+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.2",
            "device_type": "cisco_nxos",
            "hostname": "dist-sw-01",
            "model": "Nexus9300",
            "os_version": "10.3(2)",
            "interfaces": [
                {"name": "Ethernet1/1", "ip_address": "10.1.0.2", "status": "up", "protocol": ""},
                {"name": "Ethernet1/2", "ip_address": "10.3.0.1", "status": "up", "protocol": ""},
                {"name": "Vlan10", "ip_address": "192.168.10.1", "status": "up", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:05+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.3",
            "device_type": "cisco_nxos",
            "hostname": "dist-sw-02",
            "model": "Nexus9300",
            "os_version": "10.3(2)",
            "interfaces": [
                {"name": "Ethernet1/1", "ip_address": "10.2.0.2", "status": "up", "protocol": ""},
                {"name": "Ethernet1/2", "ip_address": "10.4.0.1", "status": "up", "protocol": ""},
                {"name": "Vlan20", "ip_address": "192.168.20.1", "status": "up", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:10+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.4",
            "device_type": "arista_eos",
            "hostname": "access-sw-01",
            "model": "DCS-7050TX",
            "os_version": "4.28.3M",
            "interfaces": [
                {"name": "Ethernet1", "ip_address": "10.3.0.2", "status": "up", "protocol": "up"},
                {"name": "Ethernet2", "ip_address": "", "status": "up", "protocol": "up"},
                {"name": "Management1", "ip_address": "10.0.0.4", "status": "up", "protocol": "up"},
            ],
            "collected_at": "2026-02-21T12:00:15+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.5",
            "device_type": "paloalto_panos",
            "hostname": "edge-fw-01",
            "model": "PA-3260",
            "os_version": "10.2.5",
            "interfaces": [
                {"name": "ethernet1/1", "ip_address": "203.0.113.1/24", "status": "up", "protocol": ""},
                {"name": "ethernet1/2", "ip_address": "10.5.0.1/24", "status": "up", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:20+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.6",
            "device_type": "juniper_junos",
            "hostname": "border-rtr-01",
            "model": "MX240",
            "os_version": "21.4R3-S5.4",
            "interfaces": [
                {"name": "ge-0/0/0", "ip_address": "10.6.0.1/30", "status": "up", "protocol": "up"},
                {"name": "ge-0/0/1", "ip_address": "10.7.0.1/30", "status": "up", "protocol": "up"},
                {"name": "lo0", "ip_address": "6.6.6.6/32", "status": "up", "protocol": "up"},
            ],
            "collected_at": "2026-02-21T12:00:25+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.7",
            "device_type": "fortinet",
            "hostname": "branch-fw-01",
            "model": "FortiGate-600E",
            "os_version": "v7.2.5",
            "interfaces": [
                {"name": "port1", "ip_address": "10.7.0.2", "status": "up", "protocol": ""},
                {"name": "port2", "ip_address": "192.168.100.1", "status": "up", "protocol": ""},
                {"name": "port3", "ip_address": "", "status": "down", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:30+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.8",
            "device_type": "sonic_ssh",
            "hostname": "spine-sw-01",
            "model": "DellEMC-Z9332f-O32",
            "os_version": "SONiC.4.1.0",
            "interfaces": [
                {"name": "Ethernet0", "ip_address": "10.8.0.1/31", "status": "up", "protocol": ""},
                {"name": "Ethernet4", "ip_address": "10.8.0.3/31", "status": "up", "protocol": ""},
                {"name": "Loopback0", "ip_address": "10.1.0.32/32", "status": "up", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:35+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.9",
            "device_type": "extreme_exos",
            "hostname": "campus-sw-01",
            "model": "X460-48t",
            "os_version": "31.7.1.4",
            "interfaces": [
                {"name": "1", "ip_address": "10.9.0.1", "status": "up", "protocol": ""},
                {"name": "2", "ip_address": "", "status": "up", "protocol": ""},
                {"name": "mgmt", "ip_address": "10.0.0.9", "status": "up", "protocol": ""},
            ],
            "collected_at": "2026-02-21T12:00:40+00:00",
            "errors": [],
        },
    ]

    # Simulated neighbor data
    sample_neighbors = [
        {
            "host": "10.0.0.1",
            "device_type": "cisco_ios",
            "hostname": "core-rtr-01",
            "cdp_neighbors": [
                {
                    "remote_device": "dist-sw-01",
                    "remote_mgmt_ip": "10.0.0.2",
                    "remote_platform": "Nexus9300",
                    "local_interface": "GigabitEthernet0/1",
                    "remote_interface": "Ethernet1/1",
                },
                {
                    "remote_device": "dist-sw-02",
                    "remote_mgmt_ip": "10.0.0.3",
                    "remote_platform": "Nexus9300",
                    "local_interface": "GigabitEthernet0/2",
                    "remote_interface": "Ethernet1/1",
                },
            ],
            "lldp_neighbors": [
                {
                    "remote_device": "edge-fw-01",
                    "remote_mgmt_ip": "10.0.0.5",
                    "local_interface": "GigabitEthernet0/0",
                    "remote_interface": "ethernet1/2",
                },
            ],
            "collected_at": "2026-02-21T12:01:00+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.2",
            "device_type": "cisco_nxos",
            "hostname": "dist-sw-01",
            "cdp_neighbors": [
                {
                    "remote_device": "core-rtr-01",
                    "remote_mgmt_ip": "10.0.0.1",
                    "remote_platform": "ISR4451-X",
                    "local_interface": "Ethernet1/1",
                    "remote_interface": "GigabitEthernet0/1",
                },
                {
                    "remote_device": "access-sw-01",
                    "remote_mgmt_ip": "10.0.0.4",
                    "remote_platform": "DCS-7050TX",
                    "local_interface": "Ethernet1/2",
                    "remote_interface": "Ethernet1",
                },
            ],
            "lldp_neighbors": [],
            "collected_at": "2026-02-21T12:01:05+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.3",
            "device_type": "cisco_nxos",
            "hostname": "dist-sw-02",
            "cdp_neighbors": [
                {
                    "remote_device": "core-rtr-01",
                    "remote_mgmt_ip": "10.0.0.1",
                    "remote_platform": "ISR4451-X",
                    "local_interface": "Ethernet1/1",
                    "remote_interface": "GigabitEthernet0/2",
                },
            ],
            "lldp_neighbors": [],
            "collected_at": "2026-02-21T12:01:10+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.6",
            "device_type": "juniper_junos",
            "hostname": "border-rtr-01",
            "cdp_neighbors": [],
            "lldp_neighbors": [
                {
                    "remote_device": "core-rtr-01",
                    "remote_mgmt_ip": "10.0.0.1",
                    "local_interface": "ge-0/0/0",
                    "remote_interface": "GigabitEthernet0/3",
                },
                {
                    "remote_device": "branch-fw-01",
                    "remote_mgmt_ip": "10.0.0.7",
                    "local_interface": "ge-0/0/1",
                    "remote_interface": "port1",
                },
            ],
            "collected_at": "2026-02-21T12:01:15+00:00",
            "errors": [],
        },
        {
            "host": "10.0.0.8",
            "device_type": "sonic_ssh",
            "hostname": "spine-sw-01",
            "cdp_neighbors": [],
            "lldp_neighbors": [
                {
                    "remote_device": "dist-sw-02",
                    "remote_mgmt_ip": "10.0.0.3",
                    "local_interface": "Ethernet0",
                    "remote_interface": "Ethernet1/2",
                },
                {
                    "remote_device": "campus-sw-01",
                    "remote_mgmt_ip": "10.0.0.9",
                    "local_interface": "Ethernet4",
                    "remote_interface": "1",
                },
            ],
            "collected_at": "2026-02-21T12:01:20+00:00",
            "errors": [],
        },
    ]

    # Save sample data
    out = Path("output")
    out.mkdir(exist_ok=True)
    save_json(sample_facts, out / "device_facts.json")
    save_json(sample_neighbors, out / "neighbors.json")

    # Show facts table
    _show_facts_table(sample_facts)

    # Show neighbors table
    _show_neighbors_table(sample_neighbors)

    # Build topology
    console.print("\n[bold cyan]Building topology …[/bold cyan]")
    topo = build_topology(sample_facts, sample_neighbors)
    save_json(topo.to_dict(), out / "topology.json")

    # Render diagrams
    console.print("\n[bold cyan]Generating diagrams …[/bold cyan]")

    # Mermaid
    mmd_path = save_mermaid(topo, out / "topology.mmd")
    console.print(f"[green]✓ Mermaid → {mmd_path}[/green]")
    console.print("\n[bold]Mermaid source (paste into https://mermaid.live):[/bold]")
    console.print(generate_mermaid(topo))

    # Graphviz DOT
    dot_src = generate_graphviz_dot(topo)
    dot_path = out / "topology.dot"
    dot_path.write_text(dot_src, encoding="utf-8")
    console.print(f"\n[green]✓ Graphviz DOT → {dot_path}[/green]")

    # Try rendering PNG
    try:
        png_path = render_graphviz(topo, out / "topology", fmt="png")
        console.print(f"[green]✓ Graphviz PNG → {png_path}[/green]")
    except Exception:
        console.print("[yellow]⚠ Graphviz binary not found — skipping PNG render.[/yellow]")
        console.print("  Install with: [bold]sudo apt install graphviz[/bold] or [bold]brew install graphviz[/bold]")

    console.print("\n[bold green]Demo complete! Check the output/ directory.[/bold green]")


def _show_facts_table(facts: list[dict]) -> None:
    table = Table(title="Collected Device Facts", show_lines=True)
    table.add_column("Host", style="cyan")
    table.add_column("Hostname", style="bold")
    table.add_column("Model")
    table.add_column("OS Version")
    table.add_column("Type")
    table.add_column("Interfaces", justify="right")
    for d in facts:
        table.add_row(
            d.get("host", ""),
            d.get("hostname", ""),
            d.get("model", ""),
            d.get("os_version", ""),
            d.get("device_type", ""),
            str(len(d.get("interfaces", []))),
        )
    console.print(table)


def _show_neighbors_table(nbrs: list[dict]) -> None:
    table = Table(title="Neighbor Data", show_lines=True)
    table.add_column("Host", style="cyan")
    table.add_column("Hostname", style="bold")
    table.add_column("Proto")
    table.add_column("Local Intf")
    table.add_column("Remote Device", style="green")
    table.add_column("Remote Intf")
    for nd in nbrs:
        host = nd.get("host", "")
        hostname = nd.get("hostname", "")
        for nbr in nd.get("cdp_neighbors", []):
            table.add_row(
                host, hostname, "CDP",
                nbr.get("local_interface", ""),
                nbr.get("remote_device", ""),
                nbr.get("remote_interface", ""),
            )
        for nbr in nd.get("lldp_neighbors", []):
            table.add_row(
                host, hostname, "LLDP",
                nbr.get("local_interface", ""),
                nbr.get("remote_device", ""),
                nbr.get("remote_interface", ""),
            )
    console.print(table)


# ─── Entry Point ───────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Logging setup
    level = logging.WARNING
    if args.verbose >= 2:
        level = logging.DEBUG
    elif args.verbose >= 1:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )

    dispatch = {
        "collect":   _cmd_collect,
        "neighbors": _cmd_neighbors,
        "diagram":   _cmd_diagram,
        "show":      _cmd_show,
        "demo":      _cmd_demo,
    }
    handler = dispatch.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
