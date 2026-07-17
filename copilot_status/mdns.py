"""mDNS broadcaster - registers copilot.<user>.<hostname>.local:8585 via Zeroconf.

Uses dns-sd on macOS and avahi-publish on Linux for host .local resolution.
"""

import logging
import os
import platform
import socket
import subprocess
import sys
from zeroconf import Zeroconf, ServiceInfo

logger = logging.getLogger(__name__)


def build_mdns_host():
    """Build default mDNS hostname: copilot.<username>.<hostname>.

    Examples:
      copilot.llhuang.hll-mac-air
      copilot.john.ubuntu-server
    """
    # Prefer SUDO_USER when running under sudo, fallback to USER env var,
    # then os.getlogin(), then "unknown"
    username = (
        os.environ.get("SUDO_USER")
        or os.environ.get("USER")
        or os.getlogin()
        or "unknown"
    )
    username = username.replace(" ", "-").lower()
    hostname = socket.gethostname().replace(".local", "").replace(" ", "-").lower()
    return f"copilot.{username}.{hostname}"


class MDNSBroadcaster:
    """Broadcast copilot.<user>.<hostname>.local via mDNS/DNS-SD."""

    def __init__(self, host=None, port=8585):
        self.host = host or build_mdns_host()
        self.port = port
        self.zeroconf = None
        self.service_info = None
        self._helper_proc = None

    def _get_local_ip(self):
        """Get the local IP address for mDNS registration."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def start(self):
        """Start mDNS broadcast."""
        local_ip = self._get_local_ip()
        logger.info("Local IP: %s", local_ip)

        self.zeroconf = Zeroconf()

        # Register _http._tcp service (discoverable in browsers via Bonjour/mDNS)
        self.service_info = ServiceInfo(
            type_="_http._tcp.local.",
            name="Copilot CLI Status._http._tcp.local.",
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties={
                "path": "/",
            },
            server=f"{self.host}.local.",
        )

        self.zeroconf.register_service(self.service_info)
        logger.info(
            "mDNS service registered: Copilot CLI Status._http._tcp.local. -> %s:%d",
            local_ip, self.port,
        )

        # Register the host address via system mDNS tools so that
        # <host>.local resolves from other devices on the network.
        if sys.platform == "darwin":
            self._register_host_dns_sd(local_ip)
        elif sys.platform.startswith("linux"):
            self._register_host_avahi(local_ip)
        else:
            logger.info(
                "No native mDNS helper for %s, .local resolution may not work",
                sys.platform,
            )

    def _register_host_dns_sd(self, local_ip):
        """Register host name via macOS dns-sd for .local resolution."""
        try:
            self._helper_proc = subprocess.Popen(
                [
                    "dns-sd",
                    "-R",
                    self.host,
                    "_http._tcp",
                    ".",
                    str(self.port),
                    "path=/",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("macOS dns-sd registered: %s.local -> %s", self.host, local_ip)
        except FileNotFoundError:
            logger.warning("dns-sd not found, host .local resolution may not work")
        except Exception as e:
            logger.warning("dns-sd registration failed: %s", e)

    def _register_host_avahi(self, local_ip):
        """Register host name via Linux avahi-publish for .local resolution."""
        try:
            self._helper_proc = subprocess.Popen(
                [
                    "avahi-publish-service",
                    self.host,
                    "_http._tcp",
                    str(self.port),
                    "path=/",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Linux avahi registered: %s.local -> %s", self.host, local_ip)
        except FileNotFoundError:
            logger.warning(
                "avahi-publish-service not found. Install with: "
                "sudo apt install avahi-utils  (Debian/Ubuntu)  |  "
                "sudo dnf install avahi-tools  (Fedora)"
            )
        except Exception as e:
            logger.warning("avahi registration failed: %s", e)

    def stop(self):
        """Stop mDNS broadcast."""
        if self._helper_proc:
            self._helper_proc.terminate()
            try:
                self._helper_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._helper_proc.kill()
            self._helper_proc = None
            logger.info("mDNS helper process stopped")

        if self.zeroconf and self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
            logger.info("mDNS unregistered")
