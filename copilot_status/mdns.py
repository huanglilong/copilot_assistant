"""mDNS broadcaster - registers copilot.local:8585 via Zeroconf.

On macOS, also uses dns-sd to register the host address so that
copilot.local resolves to the local IP from other devices.
"""

import logging
import socket
import subprocess
import sys
from zeroconf import Zeroconf, ServiceInfo

logger = logging.getLogger(__name__)


class MDNSBroadcaster:
    """Broadcast copilot.local via mDNS/DNS-SD."""

    def __init__(self, host="copilot", port=8585):
        self.host = host
        self.port = port
        self.zeroconf = None
        self.service_info = None
        self._dns_sd_proc = None

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

        # On macOS, also register the host address via dns-sd so that
        # <host>.local resolves from other devices on the network.
        if sys.platform == "darwin":
            self._register_host_macos(local_ip)

    def _register_host_macos(self, local_ip):
        """Register host name via macOS dns-sd for .local resolution."""
        try:
            self._dns_sd_proc = subprocess.Popen(
                [
                    "dns-sd",
                    "-R",
                    self.host,
                    "_http._tcp",
                    ".",
                    str(self.port),
                    f"path=/",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("macOS dns-sd host registered: %s.local -> %s", self.host, local_ip)
        except FileNotFoundError:
            logger.warning("dns-sd not found, host .local resolution may not work")
        except Exception as e:
            logger.warning("dns-sd registration failed: %s", e)

    def stop(self):
        """Stop mDNS broadcast."""
        if self._dns_sd_proc:
            self._dns_sd_proc.terminate()
            try:
                self._dns_sd_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._dns_sd_proc.kill()
            self._dns_sd_proc = None
            logger.info("dns-sd process stopped")

        if self.zeroconf and self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
            logger.info("mDNS unregistered")
