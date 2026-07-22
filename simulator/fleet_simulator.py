"""
Fleet Simulator — spawns multiple OBD-II simulators as subprocesses.

Each vehicle gets a different health profile so you can see the full range
of dashboard states simultaneously.

Usage:
    python simulator/fleet_simulator.py --vehicles 5 --interval 10
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | FLEET-SIM | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fleet_simulator")

# Cycles through these profiles for a realistic fleet mix
FLEET_PROFILES = [
    "healthy",
    "healthy",
    "degrading",
    "intermittent_fault",
    "critical",
    "healthy",
    "degrading",
    "healthy",
    "intermittent_fault",
    "healthy",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fleet OBD-II Simulator")
    parser.add_argument(
        "--vehicles",
        type=int,
        default=5,
        help="Number of vehicles to simulate (default: 5, max: 10)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between readings per vehicle",
    )
    parser.add_argument("--broker", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()

    if args.vehicles < 1 or args.vehicles > 10:
        log.error("Vehicle count must be between 1 and 10")
        sys.exit(1)

    processes = []
    profiles = FLEET_PROFILES[: args.vehicles]

    try:
        for i, profile in enumerate(profiles):
            vehicle_id = f"VH-FLEET-{i + 1:03d}"
            cmd = [
                sys.executable,
                str(__file__.replace("fleet_simulator", "obd_simulator")),
                "--vehicle-id",
                vehicle_id,
                "--interval",
                str(args.interval),
                "--profile",
                profile,
                "--broker",
                args.broker,
                "--port",
                str(args.port),
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(proc)
            log.info("Spawned %s [profile=%s, pid=%d]", vehicle_id, profile, proc.pid)

        log.info("Fleet running — %d vehicles. Press Ctrl+C to stop.", len(processes))

        # Wait for all processes
        while processes:
            time.sleep(1)
            processes = [p for p in processes if p.poll() is None]

    except KeyboardInterrupt:
        log.info("Stopping fleet...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        # Give them a moment, then kill if needed
        time.sleep(2)
        for proc in processes:
            if proc.poll() is None:
                proc.kill()
        log.info("Fleet stopped.")


if __name__ == "__main__":
    main()
