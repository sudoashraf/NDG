"""Parsers for Arista EOS output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    m = re.search(r"Arista\s+([\w\-]+)", output)
    if m:
        info["model"] = m.group(1)

    m = re.search(r"Software image version:\s*(\S+)", output)
    if m:
        info["os_version"] = m.group(1)

    m = re.search(r"Hostname:\s*(\S+)", output)
    if m:
        info["hostname"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show ip interface brief``."""
    interfaces: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        if name.lower() in ("interface", ""):
            continue
        ip = parts[1] if re.match(r"\d+\.\d+\.\d+\.\d+", parts[1]) else ""
        status = parts[2] if len(parts) > 2 else "unknown"
        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": status,
            "protocol": parts[3] if len(parts) > 3 else "",
        })
    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors detail``."""
    neighbors: list[dict[str, Any]] = []
    blocks = re.split(r"Interface\s+", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        # local intf is the token right after the split
        m = re.match(r"(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1).rstrip(",")

        m = re.search(r"System Name:\s*\"?(\S+?)\"?$", block, re.MULTILINE)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Management Address.*?:\s*(\d+\.\d+\.\d+\.\d+)", block, re.DOTALL)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"Port ID\s*:\s*\"?(\S+?)\"?$", block, re.MULTILINE)
        if m:
            neighbor["remote_interface"] = m.group(1)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors


# Arista typically uses LLDP; provide a stub for CDP
def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Arista CDP is rare — fall back to empty list."""
    return []
