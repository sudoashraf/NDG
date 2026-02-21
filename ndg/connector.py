"""SSH connector — wraps Netmiko to talk to routers, switches, firewalls."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException

log = logging.getLogger(__name__)


@dataclass
class DeviceCredentials:
    """Holds SSH credentials for a single device."""

    host: str
    username: str
    password: str
    device_type: str = "autodetect"          # Netmiko device_type string
    port: int = 22
    secret: str = ""                          # enable password (if needed)
    timeout: int = 30
    extras: dict[str, Any] = field(default_factory=dict)


class SSHConnector:
    """Manage an SSH session to a single network device via Netmiko.

    Usage
    -----
    >>> creds = DeviceCredentials(host="10.0.0.1", username="admin", password="secret")
    >>> with SSHConnector(creds) as ssh:
    ...     output = ssh.send("show version")
    """

    def __init__(self, credentials: DeviceCredentials) -> None:
        self.credentials = credentials
        self._connection = None

    # -- context-manager interface -------------------------------------------
    def __enter__(self) -> "SSHConnector":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    # -- public API ----------------------------------------------------------
    def connect(self) -> None:
        """Open the SSH connection."""
        creds = self.credentials
        params: dict[str, Any] = {
            "device_type": creds.device_type,
            "host": creds.host,
            "username": creds.username,
            "password": creds.password,
            "port": creds.port,
            "timeout": creds.timeout,
            "secret": creds.secret,
            **creds.extras,
        }
        try:
            log.info("Connecting to %s (%s) …", creds.host, creds.device_type)
            self._connection = ConnectHandler(**params)
            # Enter enable mode if a secret is supplied
            if creds.secret:
                self._connection.enable()
            log.info("Connected to %s", creds.host)
        except NetmikoAuthenticationException:
            log.error("Authentication failed for %s", creds.host)
            raise
        except NetmikoTimeoutException:
            log.error("Timeout connecting to %s", creds.host)
            raise
        except Exception:
            log.exception("Unexpected error connecting to %s", creds.host)
            raise

    def disconnect(self) -> None:
        """Close the SSH connection gracefully."""
        if self._connection:
            self._connection.disconnect()
            log.info("Disconnected from %s", self.credentials.host)
            self._connection = None

    def send(self, command: str, **kwargs: Any) -> str:
        """Send a CLI command and return the output string."""
        if not self._connection:
            raise RuntimeError("Not connected — call connect() first or use as context manager.")
        log.debug(">> %s : %s", self.credentials.host, command)
        output: str = self._connection.send_command(command, **kwargs)
        return output

    def send_config(self, commands: list[str], **kwargs: Any) -> str:
        """Send configuration commands."""
        if not self._connection:
            raise RuntimeError("Not connected.")
        return self._connection.send_config_set(commands, **kwargs)

    @property
    def is_connected(self) -> bool:
        return self._connection is not None and self._connection.is_alive()
