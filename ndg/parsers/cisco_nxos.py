"""Parsers for Cisco NX-OS (Nexus) output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    m = re.search(r"Device name:\s*(\S+)", output)
    if m:
        info["hostname"] = m.group(1)

    m = re.search(r"NXOS.*?version\s+(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"system:\s+version\s+(\S+)", output, re.IGNORECASE)
    if m:
        info["os_version"] = m.group(1)

    m = re.search(r"Hardware\n\s+cisco\s+(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"cisco\s+(Nexus[\w\s]+?)\s+Chassis", output, re.IGNORECASE)
    if m:
        info["model"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show ip interface brief`` for NX-OS."""
    interfaces: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0]
        if name.lower() in ("interface", "ip", ""):
            continue
        ip = parts[1] if re.match(r"\d+\.\d+\.\d+\.\d+", parts[1]) else ""
        status = parts[2] if len(parts) > 2 else "unknown"
        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": status,
            "protocol": "",
        })
    return interfaces


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse NX-OS ``show cdp neighbors detail``."""
    neighbors: list[dict[str, Any]] = []
    blocks = re.split(r"-{10,}", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"Device ID:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"(?:IPv4 Address|Mgmt address):\s*(\S+)", block, re.IGNORECASE)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"Platform:\s*(.+?)(?:,|\n)", block)
        if m:
            neighbor["remote_platform"] = m.group(1).strip()
        m = re.search(r"Interface:\s*(\S+),\s*Port ID.*?:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
            neighbor["remote_interface"] = m.group(2)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse NX-OS ``show lldp neighbors detail``."""
    neighbors: list[dict[str, Any]] = []
    blocks = re.split(r"-{10,}", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"System Name:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Management Address.*?:\s*(\d+\.\d+\.\d+\.\d+)", block, re.DOTALL)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"Port id:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Local Port id:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors
