"""Parsers for Cisco IOS / IOS-XE output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    # Hostname
    m = re.search(r"(\S+)\s+uptime is", output)
    if m:
        info["hostname"] = m.group(1)

    # IOS version string  (e.g. "15.7(3)M6" or "17.03.04")
    m = re.search(r"Cisco IOS.*?Version\s+([\S]+)", output, re.IGNORECASE)
    if m:
        info["os_version"] = m.group(1).rstrip(",")

    # Model / platform
    m = re.search(r"[Cc]isco\s+([\w\-/]+)\s+.*?processor", output)
    if not m:
        m = re.search(r"Model [Nn]umber\s*:\s*(\S+)", output)
    if m:
        info["model"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show ip interface brief`` into a list of interface dicts."""
    interfaces: list[dict[str, str]] = []
    for line in output.splitlines():
        # Skip header / blank lines
        parts = line.split()
        if len(parts) < 6:
            continue
        name = parts[0]
        if name.lower() in ("interface", ""):
            continue
        interfaces.append({
            "name": name,
            "ip_address": parts[1] if parts[1] != "unassigned" else "",
            "status": parts[4],
            "protocol": parts[5],
        })
    return interfaces


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show cdp neighbors detail`` into neighbor records."""
    neighbors: list[dict[str, Any]] = []
    # Split on the separator line
    blocks = re.split(r"-{10,}", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"Device ID:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"IP address:\s*(\S+)", block)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"Platform:\s*(.+?),", block)
        if m:
            neighbor["remote_platform"] = m.group(1).strip()
        m = re.search(r"Interface:\s*(\S+),\s*Port ID.*?:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
            neighbor["remote_interface"] = m.group(2)
        m = re.search(r"Version\s*:\s*\n(.+?)(?:\n\n|\Z)", block, re.DOTALL)
        if m:
            neighbor["remote_os_version"] = m.group(1).strip()

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors detail`` into neighbor records."""
    neighbors: list[dict[str, Any]] = []
    blocks = re.split(r"-{10,}", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"System Name:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Management Addresses?.*?IP:\s*(\S+)", block, re.DOTALL)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"System Description:\s*\n(.+?)(?:\n\n|\Z)", block, re.DOTALL)
        if m:
            neighbor["remote_platform"] = m.group(1).strip()
        m = re.search(r"Local Intf:\s*(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
        m = re.search(r"Port id:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)
    return neighbors
