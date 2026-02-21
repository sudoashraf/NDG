"""Parsers for Extreme Networks ExtremeXOS (EXOS) output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``.

    ExtremeXOS ``show version`` example::

        Switch      : 800611-00-06 1846G-50082 Rev 6.0 BootROM: 1.0.2.6    IMG: 31.7.1.4
        XN-VSP-4900-48P             HW:04           ...
        SysName  : dist-sw-03
        ...
        System MAC : aa:bb:cc:dd:ee:ff

    Or::

        ExtremeXOS version 31.7.1.4 by release-manager ...
        ...
        Switch     : Summit X460-48t
    """
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    # Hostname / SysName
    m = re.search(r"SysName\s*:\s*(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"System Name\s*:\s*(\S+)", output, re.IGNORECASE)
    if m:
        info["hostname"] = m.group(1)

    # ExtremeXOS version
    m = re.search(r"ExtremeXOS\s+version\s+(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"IMG:\s*(\S+)", output)
    if m:
        info["os_version"] = m.group(1)

    # Model / Switch type
    m = re.search(r"Switch\s*:\s*(.+?)(?:\n|$)", output)
    if m:
        model_str = m.group(1).strip()
        # Try to extract a clean model name
        m2 = re.search(r"(Summit\s+\S+|X\d+\S*|VSP-\S+|ExtremeSwitching\s+\S+)", model_str, re.IGNORECASE)
        if m2:
            info["model"] = m2.group(1)
        else:
            info["model"] = model_str.split()[0] if model_str else ""

    # Fallback model from "System Type" line
    if not info["model"]:
        m = re.search(r"System Type\s*:\s*(\S+)", output, re.IGNORECASE)
        if m:
            info["model"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show vlan`` or ``show ports information``.

    ``show ipconfig``::

        Interface   IP Address      Subnet Mask     VLAN Name    Status
        ---------   ----------      -----------     ---------    ------
        Default     10.0.0.1        255.255.255.0   Default      Active

    ``show ports`` typical lines::

        Port   Type   Admin  Link  Speed  Duplex
        1      ENET   E      A     1G     FULL
    """
    interfaces: list[dict[str, str]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("-") or line.startswith("="):
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        name = parts[0]
        # Skip headers
        if name.lower() in ("port", "interface", "vlan", ""):
            continue

        # Check for IP address in the line
        ip = ""
        for p in parts[1:]:
            if re.match(r"\d+\.\d+\.\d+\.\d+", p):
                ip = p
                break

        # Check for status keywords
        status = "unknown"
        for p in parts:
            low = p.lower()
            if low in ("active", "enabled", "up", "a", "e", "r"):
                status = "up"
                break
            elif low in ("inactive", "disabled", "down", "d"):
                status = "down"
                break

        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": status,
            "protocol": "",
        })

    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors detailed``.

    ExtremeXOS ``show lldp neighbors detailed``::

        LLDP Port 1 detected 1 neighbor
          Neighbor: 00:aa:bb:cc:dd:ee, TTL 120 (expires in 95 seconds)
           - System Name: "core-rtr-01"
           - Port ID (Interface Name): "Gi0/1"
           - Management Address: 10.0.0.1
           - System Description: "Cisco IOS ..."
    """
    neighbors: list[dict[str, Any]] = []

    # Split by "LLDP Port" blocks
    blocks = re.split(r"(?=LLDP Port\s+)", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        # Local port
        m = re.search(r"LLDP Port\s+(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)

        m = re.search(r"System Name:\s*\"?(\S+?)\"?(?:\s|$)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Port ID.*?:\s*\"?(\S+?)\"?(?:\s|$)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Management Address:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"System Description:\s*\"?(.+?)\"?\s*$", block, re.MULTILINE)
        if m:
            neighbor["remote_platform"] = m.group(1).strip()

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)

    return neighbors


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """ExtremeXOS supports CDP in limited form — parse ``show cdp neighbors``.

    ``show cdp neighbors detail``::

        CDP Port 1 Neighbor 00:aa:bb:cc:dd:ee
          Device ID: core-rtr-01
          Platform: Cisco ISR4451-X
          Interface: GigabitEthernet0/1
          IP Address: 10.0.0.1
    """
    neighbors: list[dict[str, Any]] = []

    blocks = re.split(r"(?=CDP Port\s+)", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"CDP Port\s+(\S+)", block)
        if m:
            neighbor["local_interface"] = m.group(1)
        m = re.search(r"Device ID:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"Interface:\s*(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"Platform:\s*(.+?)(?:\n|$)", block)
        if m:
            neighbor["remote_platform"] = m.group(1).strip()
        m = re.search(r"IP Address:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)

    return neighbors
