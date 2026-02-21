"""Collector — connect to a device, gather facts, and return structured data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ndg.connector import DeviceCredentials, SSHConnector
from ndg.platforms import get_commands, get_parser

log = logging.getLogger(__name__)


def collect_device_info(credentials: DeviceCredentials) -> dict[str, Any]:
    """SSH into one device and return a dict of baseline facts.

    Returns
    -------
    dict with keys: host, hostname, model, os_version, device_type,
                    interfaces, collected_at
    """
    cmds = get_commands(credentials.device_type)
    parser = get_parser(credentials.device_type)

    result: dict[str, Any] = {
        "host": credentials.host,
        "device_type": credentials.device_type,
        "hostname": "",
        "model": "",
        "os_version": "",
        "interfaces": [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
    }

    try:
        with SSHConnector(credentials) as ssh:
            # ── Version / facts ──────────────────────────────────────
            try:
                raw_version = ssh.send(cmds["version"])
                facts = parser.parse_version(raw_version)
                result.update(facts)
            except Exception as exc:
                log.warning("Failed to get version from %s: %s", credentials.host, exc)
                result["errors"].append(f"version: {exc}")

            # ── Interfaces ───────────────────────────────────────────
            try:
                raw_intf = ssh.send(cmds["interfaces"])
                result["interfaces"] = parser.parse_interfaces(raw_intf)
            except Exception as exc:
                log.warning("Failed to get interfaces from %s: %s", credentials.host, exc)
                result["errors"].append(f"interfaces: {exc}")

    except Exception as exc:
        log.error("Could not connect to %s: %s", credentials.host, exc)
        result["errors"].append(f"connection: {exc}")

    return result


def collect_neighbors(credentials: DeviceCredentials) -> dict[str, Any]:
    """SSH into one device and return CDP + LLDP neighbor data.

    Returns
    -------
    dict with keys: host, hostname, cdp_neighbors, lldp_neighbors, collected_at
    """
    cmds = get_commands(credentials.device_type)
    parser = get_parser(credentials.device_type)

    result: dict[str, Any] = {
        "host": credentials.host,
        "device_type": credentials.device_type,
        "hostname": "",
        "cdp_neighbors": [],
        "lldp_neighbors": [],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "errors": [],
    }

    try:
        with SSHConnector(credentials) as ssh:
            # hostname from version
            try:
                raw_version = ssh.send(cmds["version"])
                facts = parser.parse_version(raw_version)
                result["hostname"] = facts.get("hostname", "")
            except Exception:
                pass

            # ── CDP ──────────────────────────────────────────────────
            cdp_cmd = cmds.get("cdp_neighbors", "")
            if cdp_cmd:
                try:
                    raw_cdp = ssh.send(cdp_cmd)
                    result["cdp_neighbors"] = parser.parse_cdp_neighbors_detail(raw_cdp)
                except Exception as exc:
                    log.warning("CDP query failed on %s: %s", credentials.host, exc)
                    result["errors"].append(f"cdp: {exc}")

            # ── LLDP ─────────────────────────────────────────────────
            lldp_cmd = cmds.get("lldp_neighbors", "")
            if lldp_cmd:
                try:
                    raw_lldp = ssh.send(lldp_cmd)
                    result["lldp_neighbors"] = parser.parse_lldp_neighbors_detail(raw_lldp)
                except Exception as exc:
                    log.warning("LLDP query failed on %s: %s", credentials.host, exc)
                    result["errors"].append(f"lldp: {exc}")

    except Exception as exc:
        log.error("Could not connect to %s: %s", credentials.host, exc)
        result["errors"].append(f"connection: {exc}")

    return result
