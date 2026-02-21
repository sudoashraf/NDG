"""Parsers for Juniper JunOS output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    # Hostname
    m = re.search(r"Hostname:\s*(\S+)", output)
    if m:
        info["hostname"] = m.group(1)

    # Model  (e.g. "Model: mx240", "Model: ex4300-48t")
    m = re.search(r"Model:\s*(\S+)", output)
    if m:
        info["model"] = m.group(1)

    # Junos version  (e.g. "Junos: 21.4R3-S5.4" or "JUNOS Base OS boot [21.2R3-S3.5]")
    m = re.search(r"Junos:\s*(\S+)", output)
    if not m:
        m = re.search(r"JUNOS.*?\[(\S+?)\]", output)
    if not m:
        m = re.search(r"Junos.*?Release\s+(\S+)", output, re.IGNORECASE)
    if m:
        info["os_version"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show interfaces terse`` into a list of interface dicts.

    Typical line format::

        ge-0/0/0                up    up
        ge-0/0/0.0              up    up   inet     10.0.0.1/24
    """
    interfaces: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        if name.lower() in ("interface", ""):
            continue
        # Skip header line
        if "admin" in name.lower() and "link" in line.lower():
            continue

        admin_status = parts[1] if len(parts) > 1 else "unknown"
        link_status = parts[2] if len(parts) > 2 else "unknown"

        # Look for an IP address in remaining fields
        ip = ""
        for p in parts[3:]:
            if re.match(r"\d+\.\d+\.\d+\.\d+", p):
                ip = p
                break

        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": admin_status,
            "protocol": link_status,
        })
    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors`` detail output.

    JunOS ``show lldp neighbors`` shows a table; ``show lldp neighbors detail``
    shows per-interface blocks separated by blank lines.
    """
    neighbors: list[dict[str, Any]] = []

    # Try block-based parsing (detail output)
    blocks = re.split(r"\n\s*\n", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"System [Nn]ame\s*:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Local Interface\s*:\s*(\S+)", block)
        if not m:
            m = re.search(r"Local Port\s*:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
        m = re.search(r"(?:Port ID|Remote Port)\s*:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Management Address.*?:\s*(\d+\.\d+\.\d+\.\d+)", block, re.DOTALL)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"System Description\s*:\s*(.+?)(?:\n\n|\Z)", block, re.DOTALL)
        if m:
            neighbor["remote_platform"] = m.group(1).strip().split("\n")[0]

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)

    # Fallback: table-based parsing (brief output)
    if not neighbors:
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4 and re.match(r"[gxae]", parts[0], re.IGNORECASE):
                neighbor = {
                    "local_interface": parts[0],
                    "remote_device": parts[-2] if len(parts) >= 5 else parts[-1],
                    "remote_interface": parts[-1] if len(parts) >= 5 else "",
                }
                if neighbor["remote_device"]:
                    neighbors.append(neighbor)

    return neighbors


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """JunOS doesn't run CDP natively — return empty list."""
    return []
