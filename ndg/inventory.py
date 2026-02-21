"""Inventory loader — read the YAML device inventory file."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from ndg.connector import DeviceCredentials

log = logging.getLogger(__name__)


def load_inventory(path: str | Path) -> list[DeviceCredentials]:
    """Parse an inventory YAML file and return a list of DeviceCredentials.

    Expected YAML structure
    -----------------------
    ```yaml
    defaults:
      username: admin
      password: secret
      device_type: cisco_ios

    devices:
      - host: 10.0.0.1
        hostname: core-rtr-01        # optional friendly name
      - host: 10.0.0.2
        device_type: cisco_nxos
        username: nxadmin
        password: nxpass
    ```
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Inventory file not found: {path}")

    with open(path, encoding="utf-8") as fh:
        data: dict[str, Any] = yaml.safe_load(fh)

    defaults: dict[str, Any] = data.get("defaults", {})
    devices_raw: list[dict[str, Any]] = data.get("devices", [])

    if not devices_raw:
        log.warning("Inventory is empty — no devices defined.")
        return []

    credentials: list[DeviceCredentials] = []
    for dev in devices_raw:
        creds = DeviceCredentials(
            host=dev["host"],
            username=dev.get("username", defaults.get("username", "")),
            password=dev.get("password", defaults.get("password", "")),
            device_type=dev.get("device_type", defaults.get("device_type", "cisco_ios")),
            port=int(dev.get("port", defaults.get("port", 22))),
            secret=dev.get("secret", defaults.get("secret", "")),
            timeout=int(dev.get("timeout", defaults.get("timeout", 30))),
        )
        credentials.append(creds)
        log.debug("Loaded device %s (%s)", creds.host, creds.device_type)

    log.info("Loaded %d devices from %s", len(credentials), path)
    return credentials
