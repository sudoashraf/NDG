"""Platform registry — maps Netmiko device_type strings to the right parser module."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

# Mapping: netmiko device_type  →  parser module dotted path
_PARSER_MAP: dict[str, str] = {
    # Cisco IOS / IOS-XE
    "cisco_ios":        "ndg.parsers.cisco_ios",
    "cisco_xe":         "ndg.parsers.cisco_ios",
    "cisco_ios_telnet": "ndg.parsers.cisco_ios",
    # Cisco NX-OS
    "cisco_nxos":       "ndg.parsers.cisco_nxos",
    "cisco_nxos_ssh":   "ndg.parsers.cisco_nxos",
    # Arista EOS
    "arista_eos":       "ndg.parsers.arista_eos",
    # Palo Alto PAN-OS
    "paloalto_panos":   "ndg.parsers.paloalto_panos",
    # Juniper JunOS
    "juniper_junos":    "ndg.parsers.juniper_junos",
    "juniper":          "ndg.parsers.juniper_junos",
    # Fortinet FortiOS
    "fortinet":         "ndg.parsers.fortinet_fortios",
    "fortinet_ssh":     "ndg.parsers.fortinet_fortios",
    # SONiC
    "sonic_ssh":        "ndg.parsers.sonic",
    "linux":            "ndg.parsers.sonic",           # SONiC runs on Linux
    # Extreme Networks ExtremeXOS
    "extreme_exos":     "ndg.parsers.extreme_exos",
    "extreme":          "ndg.parsers.extreme_exos",
    "extreme_nos":      "ndg.parsers.extreme_exos",
}

# Commands per platform: (version_cmd, interface_cmd, cdp_cmd, lldp_cmd)
_COMMAND_MAP: dict[str, dict[str, str]] = {
    "cisco_ios": {
        "version":       "show version",
        "interfaces":    "show ip interface brief",
        "cdp_neighbors": "show cdp neighbors detail",
        "lldp_neighbors": "show lldp neighbors detail",
    },
    "cisco_xe": {
        "version":       "show version",
        "interfaces":    "show ip interface brief",
        "cdp_neighbors": "show cdp neighbors detail",
        "lldp_neighbors": "show lldp neighbors detail",
    },
    "cisco_nxos": {
        "version":       "show version",
        "interfaces":    "show ip interface brief vrf all",
        "cdp_neighbors": "show cdp neighbors detail",
        "lldp_neighbors": "show lldp neighbors detail",
    },
    "arista_eos": {
        "version":       "show version",
        "interfaces":    "show ip interface brief",
        "cdp_neighbors": "show cdp neighbors detail",
        "lldp_neighbors": "show lldp neighbors detail",
    },
    "paloalto_panos": {
        "version":       "show system info",
        "interfaces":    "show interface all",
        "cdp_neighbors": "",                          # PAN-OS has no CDP
        "lldp_neighbors": "show lldp neighbors all",
    },
    "juniper_junos": {
        "version":       "show version",
        "interfaces":    "show interfaces terse",
        "cdp_neighbors": "",                          # JunOS has no native CDP
        "lldp_neighbors": "show lldp neighbors",
    },
    "fortinet": {
        "version":       "get system status",
        "interfaces":    "get system interface physical",
        "cdp_neighbors": "",                          # FortiOS has no CDP
        "lldp_neighbors": "execute lldp info remote-device",
    },
    "sonic_ssh": {
        "version":       "show version",
        "interfaces":    "show ip interface",
        "cdp_neighbors": "",                          # SONiC has no CDP
        "lldp_neighbors": "show lldp neighbors",
    },
    "extreme_exos": {
        "version":       "show version",
        "interfaces":    "show ipconfig",
        "cdp_neighbors": "show cdp neighbors detail",
        "lldp_neighbors": "show lldp neighbors detailed",
    },
}


def get_parser(device_type: str) -> ModuleType:
    """Return the parser module for *device_type*."""
    mod_path = _PARSER_MAP.get(device_type)
    if not mod_path:
        raise ValueError(
            f"Unsupported device_type '{device_type}'. "
            f"Supported: {sorted(_PARSER_MAP.keys())}"
        )
    return import_module(mod_path)


def get_commands(device_type: str) -> dict[str, str]:
    """Return the CLI command map for *device_type*."""
    key = device_type
    # Normalize aliases that share the same command set
    if key in ("cisco_ios_telnet",):
        key = "cisco_ios"
    if key in ("cisco_nxos_ssh",):
        key = "cisco_nxos"
    if key in ("juniper",):
        key = "juniper_junos"
    if key in ("fortinet_ssh",):
        key = "fortinet"
    if key in ("linux",):
        key = "sonic_ssh"
    if key in ("extreme", "extreme_nos"):
        key = "extreme_exos"
    cmds = _COMMAND_MAP.get(key)
    if not cmds:
        raise ValueError(
            f"No command set for device_type '{device_type}'. "
            f"Supported: {sorted(_COMMAND_MAP.keys())}"
        )
    return cmds


def supported_platforms() -> list[str]:
    """Return the list of supported Netmiko device types."""
    return sorted(_PARSER_MAP.keys())
