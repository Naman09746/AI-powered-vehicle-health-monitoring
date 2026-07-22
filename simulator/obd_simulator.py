"""
OBD-II Dongle Simulator for Vehicle Health Monitor.

Publishes realistic sensor readings via MQTT to topic::

    vehicle/{vehicle_id}/sensors

Usage:
    python simulator/obd_simulator.py --vehicle-id VH-2026-001 --interval 5

Press Ctrl+C to stop cleanly.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time

from scripts.generate_data import generate_realistic_row

# Configure minimal logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | OBD-SIM | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("obd_simulator")

_RUNNING = True


def _signal_handler(signum, frame):
    global _RUNNING
    log.info("Shutdown signal received — stopping simulator...")
    _RUNNING = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def publish_reading(mqtt_client, vehicle_id: str, reading: dict) -> None:
    """Publish a single sensor reading as JSON."""
    topic = f"vehicle/{vehicle_id}/sensors"
    payload = json.dumps(reading, default=str)
    result = mqtt_client.publish(topic, payload, qos=1)
    if result.rc != 0:
        log.warning("Publish failed (rc=%s) for %s", result.rc, topic)
    else:
        log.info(
            "Published %s → %s (%d bytes)",
            topic,
            reading.get("vehicle_profile", "?"),
            len(payload),
        )


def get_http_token(api_url: str, username: str, password: str) -> str | None:
    import urllib.request
    import json
    
    url = f"{api_url}/auth/login"
    data = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("token")
    except Exception as e:
        log.error("Failed to authenticate with API: %s", e)
        return None


def resolve_vehicle_id(api_url: str, token: str, display_id: str) -> int | None:
    import urllib.request
    import json
    
    url = f"{api_url}/vehicles"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            vehicles = json.loads(response.read().decode("utf-8"))
            for v in vehicles:
                db_display = str(v.get("vehicle_id_display", "")).strip().lower()
                if db_display == display_id.strip().lower():
                    return v.get("id")
            if display_id.isdigit():
                return int(display_id)
    except Exception as e:
        log.error("Failed to list vehicles for resolution: %s", e)
    return None


def publish_reading_http(api_url: str, token: str, vehicle_id: int, reading: dict) -> bool:
    import urllib.request
    import json
    from datetime import datetime
    
    url = f"{api_url}/vehicles/{vehicle_id}/readings"
    
    ts = reading.get("timestamp")
    if isinstance(ts, (int, float)):
        ts_str = datetime.utcfromtimestamp(ts).isoformat()
    else:
        ts_str = datetime.utcnow().isoformat()
        
    payload = {
        "timestamp": ts_str,
        "engine_temp": float(reading.get("engine_temp", 0)),
        "oil_pressure": float(reading.get("oil_pressure", 0)),
        "coolant_temp": float(reading.get("coolant_temp", 0)),
        "engine_rpm": float(reading.get("engine_rpm", 0)),
        "vibration": float(reading.get("vibration", 0)),
        "fuel_consumption": float(reading.get("fuel_consumption", 0)),
        "battery_voltage": float(reading.get("battery_voltage", 0)),
        "tire_pressure": float(reading.get("tire_pressure", 0)),
        "speed": float(reading.get("speed", 0)),
        "engine_load": float(reading.get("engine_load", 0)),
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            log.info("HTTP Ingest Success → %s (alerts: %d)", reading.get("vehicle_profile", "?"), res_data.get("alerts_generated", 0))
            return True
    except Exception as e:
        log.error("Failed to post telemetry to API: %s", e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="OBD-II Dongle Simulator")
    parser.add_argument(
        "--vehicle-id",
        default="VH-SIM-001",
        help="Display vehicle ID (e.g. VH-2026-001)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between readings (default: 5)",
    )
    parser.add_argument(
        "--profile",
        default="dynamic",
        choices=["healthy", "degrading", "critical", "intermittent_fault", "dynamic"],
        help="Vehicle health profile (default: dynamic)",
    )
    parser.add_argument(
        "--broker",
        default="localhost",
        help="MQTT broker hostname (default: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=1883, help="MQTT broker port (default: 1883)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Number of readings to send (0 = unlimited)",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Force HTTP API ingestion mode instead of MQTT",
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Username for API authentication",
    )
    parser.add_argument(
        "--password",
        default="admin123",
        help="Password for API authentication",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000/api/v1",
        help="Base URL for the REST API (default: http://localhost:8000/api/v1)",
    )
    args = parser.parse_args()

    use_http = args.http
    client = None
    token = None
    resolved_id = None

    if not use_http:
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client(client_id=f"obd-sim-{args.vehicle_id}", protocol=mqtt.MQTTv311)
            client.connect(args.broker, args.port, keepalive=60)
            client.loop_start()
            log.info("Connected to MQTT broker at %s:%s", args.broker, args.port)
        except Exception as exc:
            log.warning("Could not connect to MQTT broker (%s) — falling back to HTTP Ingestion API", exc)
            use_http = True

    if use_http:
        log.info("Authenticating with API at %s using username '%s'...", args.api_url, args.username)
        token = get_http_token(args.api_url, args.username, args.password)
        if not token:
            log.error("Authentication failed. Cannot run HTTP simulation.")
            sys.exit(1)
        log.info("Authenticated successfully. Resolving vehicle Display ID '%s'...", args.vehicle_id)
        resolved_id = resolve_vehicle_id(args.api_url, token, args.vehicle_id)
        if resolved_id is None:
            log.error("Could not resolve vehicle Display ID '%s' in database. Please register the vehicle on the web app first.", args.vehicle_id)
            sys.exit(1)
        log.info("Vehicle display ID '%s' resolved to Database ID %d", args.vehicle_id, resolved_id)

    tick = 0
    try:
        while _RUNNING:
            current_profile = args.profile
            if args.profile == "dynamic":
                if tick < 15:
                    current_profile = "healthy"
                elif tick < 40:
                    current_profile = "degrading"
                else:
                    current_profile = "critical"

            reading = generate_realistic_row(
                vehicle_profile=current_profile,
                tick=tick,
            )
            reading["vehicle_id_display"] = args.vehicle_id
            reading["profile"] = current_profile
            
            if use_http:
                publish_reading_http(args.api_url, token, resolved_id, reading)
            else:
                publish_reading(client, args.vehicle_id, reading)
                
            tick += 1

            if args.count and tick >= args.count:
                log.info("Reached target count of %d readings. Stopping.", args.count)
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if client:
            client.loop_stop()
            client.disconnect()
            log.info("Simulator disconnected. Published %d readings.", tick)
        else:
            log.info("HTTP Simulator stopped. Published %d readings.", tick)


if __name__ == "__main__":
    main()

