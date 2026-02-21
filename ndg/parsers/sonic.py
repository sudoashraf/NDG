"""Parsers for SONiC (Software for Open Networking in the Cloud) output."""

from __future__ import annotations

import re
from typing import Any


def parse_version(output: str) -> dict[str, str]:
    """Extract hostname, model, and OS version from ``show version``.

    SONiC ``show version`` example::

        SONiC Software Version: SONiC.4.1.0-Enterprise_Base
        Distribution: Debian 11.7
        Kernel: 5.10.0-23-2-amd64
        ...
        Platform: x86_64-dellemc_z9332f_d1508-r0
        HwSKU: DellEMC-Z9332f-O32
        ASIC: broadcom
        ...
        Docker images:
        ...
        Hostname: spine-01
    """
    info: dict[str, str] = {"hostname": "", "model": "", "os_version": ""}

    m = re.search(r"Hostname:\s*(\S+)", output, re.IGNORECASE)
    if m:
        info["hostname"] = m.group(1)

    m = re.search(r"SONiC Software Version:\s*(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"Software Version:\s*(\S+)", output, re.IGNORECASE)
    if m:
        info["os_version"] = m.group(1)

    m = re.search(r"HwSKU:\s*(\S+)", output, re.IGNORECASE)
    if not m:
        m = re.search(r"Platform:\s*(\S+)", output, re.IGNORECASE)
    if m:
        info["model"] = m.group(1)

    return info


def parse_interfaces(output: str) -> list[dict[str, str]]:
    """Parse ``show ip interface`` or ``show interfaces status``.

    ``show ip interface``::

        Interface    Master    IPv4 address/mask    Admin/Oper    BGP Neighbor    Neighbor IP
        -----------  --------  -------------------  ------------  --------------  -------------
        Ethernet0              10.0.0.1/31          up/up         ARISTA01T2      10.0.0.0
        Loopback0              10.1.0.32/32         up/up         N/A             N/A

    ``show interfaces status``::

        Interface    Lanes    Speed    MTU    FEC    Alias    Vlan    Oper    Admin    Type    Asym PFC
        -----------  -------  -------  -----  -----  -------  ------  ------  -------  ------  ----------
        Ethernet0    25,26    50G      9100   N/A    Eth1/1   routed  up      up       QSFP28  N/A
    """
    interfaces: list[dict[str, str]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue

        name = parts[0]
        # Skip header rows
        if name.lower() in ("interface", ""):
            continue
        if not re.match(r"(Ethernet|Loopback|Vlan|PortChannel|Management)\d*", name, re.IGNORECASE):
            continue

        # Try to find IP address
        ip = ""
        for p in parts[1:]:
            if re.match(r"\d+\.\d+\.\d+\.\d+", p):
                ip = p
                break

        # Try to find status
        status = "unknown"
        for p in parts[1:]:
            if p.lower() in ("up", "down", "up/up", "up/down", "down/down"):
                status = p
                break

        interfaces.append({
            "name": name,
            "ip_address": ip,
            "status": status,
            "protocol": "",
        })

    return interfaces


def parse_lldp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """Parse ``show lldp neighbors``.

    SONiC ``show lldp neighbors``::

        Interface    Neighbor    Neighbor-Port    Neighbor-Port-ID
        -----------  ----------  ---------------  ------------------
        Ethernet0    spine-01    Ethernet4        Ethernet4

    SONiC ``show lldp neighbors detail`` (lldpctl style)::

        -------------------------------------------------------------------------------
        LLDP neighbors:
        -------------------------------------------------------------------------------
        Interface:    Ethernet0, via: LLDP
          Chassis:
            ChassisID:    mac aa:bb:cc:dd:ee:ff
            SysName:      spine-01
            MgmtIP:       10.0.0.1
          Port:
            PortID:       ifname Ethernet4
            PortDescr:    Ethernet4
    """
    neighbors: list[dict[str, Any]] = []

    # Try lldpctl-style blocks first
    blocks = re.split(r"(?=Interface:\s+\S+)", output)
    for block in blocks:
        if not block.strip():
            continue
        neighbor: dict[str, Any] = {}

        m = re.search(r"Interface:\s+(\S+)", block)
        if m:
            local_intf = m.group(1).rstrip(",")
            neighbor["local_interface"] = local_intf

        m = re.search(r"SysName:\s*(\S+)", block)
        if m:
            neighbor["remote_device"] = m.group(1)
        m = re.search(r"PortID:\s*(?:ifname\s+)?(\S+)", block)
        if m:
            neighbor["remote_interface"] = m.group(1)
        m = re.search(r"MgmtIP:\s*(\d+\.\d+\.\d+\.\d+)", block)
        if m:
            neighbor["remote_mgmt_ip"] = m.group(1)
        m = re.search(r"SysDescr:\s*(.+?)(?:\n\s*\n|\Z)", block, re.DOTALL)
        if m:
            neighbor["remote_platform"] = m.group(1).strip().split("\n")[0]

        if neighbor.get("remote_device"):
            neighbors.append(neighbor)

    # Fallback: table-based brief output
    if not neighbors:
        for line in output.splitlines():
            line = line.strip()
            if not line or line.startswith("-"):
                continue
            parts = line.split()
            if len(parts) >= 3 and re.match(r"Ethernet|PortChannel", parts[0], re.IGNORECASE):
                neighbor = {
                    "local_interface": parts[0],
                    "remote_device": parts[1],
                    "remote_interface": parts[2] if len(parts) > 2 else "",
                }
                neighbors.append(neighbor)

    return neighbors


def parse_cdp_neighbors_detail(output: str) -> list[dict[str, Any]]:
    """SONiC does not support CDP — return empty list."""
    return []
