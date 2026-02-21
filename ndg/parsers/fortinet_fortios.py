"""Parsers for Fortinet FortiOS (FortiGate) output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``get system status``."""
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    m = re.search(r"Hostname:\s*(\S+)", output)
    if m:
        info["hostname"] = m.group(1)

    # Version line: "Version: FortiGate-600E v7.2.5,build1517,230530 (GA.F)"
    m = re.search(r"Version:\s*(\S+)\s+(v[\d.]+)", output)
    if m:
        info["model"] = m.group(1)
        info["os_version"] = m.group(2)
    else:
        m = re.search(r"Version:\s*(\S+)", output)
        if m:
            info["model"] = m.group(1)

    # Platform line (some firmware): "Platform Full Name: FortiGate-600E"
    if not info["model"]:
        m = re.search(r"Platform.*?:\s*(\S+)", output)
        if m:
            info["model"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``get system interface physical`` or ``diagnose netlink interface list``.

    Typical block::

        == [port1]
        ...
        ip: 10.0.0.1 255.255.255.0
        status: up
    """
    interfaces: list[dict[str, str]] = []

    # Block-based: split on "== [" markers
    blocks = re.split(r"==\s*\[", output)
    for block in blocks:
        if not block.strip():
            continue
        m = re.match(r"(\S+?)\]", block)
        if not m:
            continue
        name = m.group(1)

        ip = ""
        m_ip = re.search(r"ip:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if m_ip:
            ip = m_ip.group(1)

        status = "unknown"
        m_st = re.search(r"status:\s*(\S+)", block)
        if m_st:
            status = m_st.group(1)

        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": status,
            "protocol": "",
        })

    # Fallback: line-based for simpler outputs
    if not interfaces:
        for line in output.splitlines():
            m = re.match(r"(\S+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\S+)", line)
            if m:
                interfaces.append({
                    "name": m.group(1),
                    "ip_address": m.group(2),
                    "status": m.group(3),
                    "protocol": "",
                })

    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``diagnose lldp neighbors detail <port>`` or ``execute lldp info remote-device``.

    FortiOS LLDP output (``execute lldp info remote-device``)::

        port1
          Chassis Id: 00:aa:bb:cc:dd:ee
          System Name: core-rtr-01
          Port Id: Gi0/1
          Management Address: 10.0.0.1
    """
    neighbors: list[dict[str, Any]] = []

    # Split by port name at start of line
    blocks = re.split(r"(?=^\S+\s*$)", output, flags=re.MULTILINE)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        # Local interface is the first non-indented line
        lines = block.strip().splitlines()
        if lines:
            first = lines[0].strip()
            if re.match(r"^(port|internal|wan|dmz|ssl|npu)\S*$", first, re.IGNORECASE) \
               or re.match(r"^\S+$", first):
                neighbor["local_interface"] = first

        m = re.search(r"System Name:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Port Id:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Management Address:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"System Description:\s*(.+?)(?:\n\s*\n|\Z)", block, re.DOTALL)
        if m:
            neighbor["remote_platform"] = m.group(1).strip().split("\n")[0]

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)

    return neighbors


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """FortiOS does not support CDP — return empty list."""
    return []
