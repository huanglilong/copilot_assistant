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
    try:
        username = (
            os.environ.get("SUDO_USER")
            or os.environ.get("USER")
            or os.getlogin()
            or "unknown"
        )
    except OSError:
        username = os.environ.get("USER") or "unknown"
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
        # Include PID in name to avoid conflicts with stale registrations.
        self.service_info = ServiceInfo(
            type_="_http._tcp.local.",
            name=f"Copilot CLI Status (PID {os.getpid()})._http._tcp.local.",
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
        """Register host name via Linux avahi for .local resolution.

        Tries avahi-publish-address for A/AAAA record registration
        (required for hostname resolution in browsers), and falls back
        to avahi-publish-service for DNS-SD discovery only.
        """
        procs = []
        host_resolved = False

        # Best-effort: register an A record so <host>.local resolves.
        # Some avahi configurations may not support publish-address.
        try:
            proc_addr = subprocess.Popen(
                ["avahi-publish-address", "-a", "-f", "-R", self.host, local_ip],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            # Give it a moment to register, then verify
            import time
            time.sleep(0.5)
            if proc_addr.poll() is None:
                logger.info("Linux avahi address registered: %s.local -> %s", self.host, local_ip)
                host_resolved = True
            else:
                stderr = proc_addr.stderr.read().decode(errors="replace").strip()
                logger.debug("avahi-publish-address exited quickly: %s", stderr or "unknown error")
                proc_addr = None
        except FileNotFoundError:
            pass  # handled below
        except Exception as e:
            logger.debug("avahi address registration failed: %s", e)

        # Always publish the HTTP service for DNS-SD discovery
        try:
            proc_svc = subprocess.Popen(
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
            procs.append(proc_svc)
            logger.info("Linux avahi service registered: %s._http._tcp -> %s:%d",
                        self.host, local_ip, self.port)
        except FileNotFoundError:
            pass  # handled below
        except Exception as e:
            logger.warning("avahi service registration failed: %s", e)

        if not host_resolved:
            # Check if nsswitch.conf uses mdns4_minimal which doesn't support
            # multi-label .local names (e.g. copilot.user.host.local)
            self._check_nsswitch_mdns()
            logger.info(
                "Host .local resolution not available; use http://%s:%d from other devices",
                local_ip, self.port,
            )

        if not procs:
            logger.warning(
                "avahi-publish not found. Install with: "
                "sudo apt install avahi-utils  (Debian/Ubuntu)  |  "
                "sudo dnf install avahi-tools  (Fedora)"
            )
            return

        self._helper_proc = procs[0]
        self._avahi_procs = procs

    def _check_nsswitch_mdns(self):
        """Check if nsswitch.conf uses mdns4_minimal which doesn't support
        multi-label .local hostnames, and log a helpful warning."""
        try:
            with open("/etc/nsswitch.conf", "r") as f:
                for line in f:
                    if line.strip().startswith("hosts:"):
                        if "mdns4_minimal" in line and "mdns4" not in line.replace("mdns4_minimal", ""):
                            logger.warning(
                                "nsswitch.conf uses 'mdns4_minimal' which does NOT support "
                                "multi-label .local hostnames (e.g. %s.local). "
                                "To fix, run: sudo sed -i 's/mdns4_minimal [NOTFOUND=return]/mdns4/' /etc/nsswitch.conf",
                                self.host,
                            )
                        break
        except Exception:
            pass

    def stop(self):
        """Stop mDNS broadcast."""
        procs = getattr(self, '_avahi_procs', None) or []
        if self._helper_proc:
            procs.append(self._helper_proc)
        for proc in procs:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except Exception:
                pass
        self._helper_proc = None
        self._avahi_procs = None
        if procs:
            logger.info("mDNS helper process(es) stopped")

        if self.zeroconf and self.service_info:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
            logger.info("mDNS unregistered")
