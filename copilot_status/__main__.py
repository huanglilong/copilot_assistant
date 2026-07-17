"""Copilot CLI Status Monitor - main entry point.

Starts an HTTP server on port 8585 and broadcasts via mDNS as copilot.local.
Other devices on the same network can visit http://copilot.local:8585 to view
the real-time status of GitHub Copilot CLI sessions.
"""

import argparse
import atexit
import logging
import signal
import sys

from copilot_status.mdns import MDNSBroadcaster
from copilot_status.server import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_PORT = 8585
DEFAULT_HOST = "copilot"


def main():
    parser = argparse.ArgumentParser(description="Copilot CLI Status Monitor")
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help=f"HTTP server port (default: {DEFAULT_PORT})")
    parser.add_argument("-m", "--mdns-host", type=str, default=DEFAULT_HOST, help=f"mDNS hostname (default: {DEFAULT_HOST}, accessible as {DEFAULT_HOST}.local)")
    parser.add_argument("--no-mdns", action="store_true", help="Disable mDNS broadcast")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    broadcaster = None

    if not args.no_mdns:
        broadcaster = MDNSBroadcaster(host=args.mdns_host, port=args.port)
        try:
            broadcaster.start()
        except Exception as e:
            logger.warning("mDNS broadcast failed (non-fatal): %s", e)
            logger.info("You can still access the status page at http://localhost:%d", args.port)

        def cleanup():
            if broadcaster:
                broadcaster.stop()

        atexit.register(cleanup)

        def signal_handler(sig, frame):
            logger.info("Shutting down...")
            cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Starting Copilot CLI Status Monitor on port %d", args.port)
    if not args.no_mdns:
        logger.info("Access from other devices: http://%s.local:%d", args.mdns_host, args.port)
    logger.info("Access locally: http://localhost:%d", args.port)

    # Use dual-stack (IPv4+IPv6) so .local hostname works from all devices.
    # macOS Safari and mobile browsers may try IPv6 first for .local names.
    app.run(host="::", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
