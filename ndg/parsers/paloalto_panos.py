"""Parsers for Palo Alto PAN-OS firewall output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show system info``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    m = re.search(r"hostname:\s*(\S+)", output)
    if m:
        info["hostname"] = m.group(1)

    m = re.search(r"model:\s*(\S+)", output)
    if m:
        info["model"] = m.group(1)

    m = re.search(r"sw-version:\s*(\S+)", output)
    if m:
        info["os_version"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show interface all`` (simplified)."""
    interfaces: list[dict[str, str]] = []
    for line in output.splitlines():
        # Lines typically: "ethernet1/1  10.0.0.1/24  up"
        m = re.match(r"(\S+)\s+(\d+\.\d+\.\d+\.\d+(?:/\d+)?)\s+(\S+)", line)
        if m:
            interfaces.append({
                "name": m.group(1),
                "ip_address": m.group(2),
                "status": m.group(3),
                "protocol": "",
            })
        elif re.match(r"(ethernet|ae|loopback|tunnel|vlan)\S*", line, re.IGNORECASE):
            parts = line.split()
            interfaces.append({
                "name": parts[0],
                "ip_address": "",
                "status": parts[1] if len(parts) > 1 else "unknown",
                "protocol": "",
            })
    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors all``."""
    neighbors: list[dict[str, Any]] = []
    blocks = re.split(r"(?=Local Interface:)", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"Local Interface:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
        m = re.search(r"Remote System Name:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Remote Port ID:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Remote Management Address.*?:\s*(\d+\.\d+\.\d+\.\d+)", block, re.DOTALL)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """PAN-OS doesn't use CDP — return empty list."""
    return []
