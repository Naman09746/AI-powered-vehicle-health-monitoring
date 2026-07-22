"""
MQTT subscriber for real-time vehicle sensor ingestion.

Listens on ``vehicle/{vehicle_id}/sensors`` topics, validates incoming
readings via the preprocessing pipeline, persists them to the database,
and runs the alert engine.

Can run as a standalone process or be imported and embedded.

Usage:
    python ingest/mqtt_subscriber.py --broker localhost --port 1883
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime

# Ensure the project root is on sys.path for imports
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core.logger import get_logger
from core.preprocessing import preprocess_single_reading

log = get_logger("mqtt_subscriber")

_RUNNING = True


def _signal_handler(signum, frame):
    global _RUNNING
    log.info("Shutdown signal received — stopping subscriber...")
    _RUNNING = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def on_connect(client, userdata, flags, rc) -> None:
    """Callback when the MQTT client connects to the broker."""
    if rc == 0:
        log.info("Connected to MQTT broker (rc=%s)", rc)
        # Subscribe to all vehicle sensor topics
        client.subscribe("vehicle/+/sensors", qos=1)
        log.info("Subscribed to vehicle/+/sensors")
    else:
        log.error("Connection failed (rc=%s)", rc)


def on_message(client, userdata, msg) -> None:
    """Callback when a sensor reading arrives via MQTT."""
    import core.db as database
    from core.alerts import check_and_generate_alerts

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        log.warning("Invalid JSON payload on %s: %s", msg.topic, exc)
        return

    vehicle_id_display = msg.topic.split("/")[1] if "/" in msg.topic else "unknown"
    log.debug("Received reading from %s", vehicle_id_display)

    # ── Validate and clean the single reading ──
    cleaned, errors = preprocess_single_reading(payload)
    if errors:
        log.warning("Validation errors for %s: %s", vehicle_id_display, errors)
        return

    # ── Resolve the vehicle in our DB ──
    session = database.get_session()
    try:
        vehicle = (
            session.query(database.Vehicle)
            .filter_by(vehicle_id_display=vehicle_id_display)
            .first()
        )
        if not vehicle:
            log.info("Vehicle %s not found in DB — skipping", vehicle_id_display)
            return
        vehicle_id = vehicle.id
        user_id = vehicle.user_id
    finally:
        session.close()

    try:
        # ── Persist the reading ──
        upload_id = database.get_or_create_default_upload(vehicle_id, user_id)

        reading = database.SensorReading(
            upload_id=upload_id,
            vehicle_id=vehicle_id,
            user_id=user_id,
            timestamp=datetime.fromisoformat(cleaned["timestamp"])
            if isinstance(cleaned.get("timestamp"), str)
            else datetime.utcnow(),
            **{
                col: cleaned.get(col)
                for col in [
                    "engine_temp",
                    "oil_pressure",
                    "coolant_temp",
                    "engine_rpm",
                    "vibration",
                    "fuel_consumption",
                    "battery_voltage",
                    "tire_pressure",
                    "speed",
                    "engine_load",
                ]
            },
        )
        # Note: using get_db() context manager would be cleaner
        session = database.get_session()
        try:
            session.add(reading)
            session.commit()
            log.info(
                "Stored reading for %s (row id=%s)", vehicle_id_display, reading.id
            )
        except Exception:
            session.rollback()
            log.exception("Failed to store reading for %s", vehicle_id_display)
            return
        finally:
            session.close()

        # ── Run alert engine ──
        alerts = check_and_generate_alerts(
            cleaned,
            vehicle_id,
            user_id,
            failure_prob=None,
        )
        if alerts:
            log.info("Generated %d alert(s) for %s", len(alerts), vehicle_id_display)
    except Exception:
        log.exception("Error processing reading for %s", vehicle_id_display)


def main() -> None:
    parser = argparse.ArgumentParser(description="MQTT Sensor Ingestion Subscriber")
    parser.add_argument("--broker", default=os.getenv("MQTT_BROKER", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    parser.add_argument("--client-id", default="vhm-ingest-1")
    args = parser.parse_args()

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        log.error("paho-mqtt is not installed. Run: pip install paho-mqtt")
        sys.exit(1)

    client = mqtt.Client(client_id=args.client_id, protocol=mqtt.MQTTv311)
    client.on_connect = on_connect
    client.on_message = on_message

    log.info("Connecting to MQTT broker at %s:%s ...", args.broker, args.port)
    try:
        client.connect(args.broker, args.port, keepalive=60)
    except Exception as exc:
        log.error("Failed to connect to broker: %s", exc)
        sys.exit(1)

    client.loop_start()

    try:
        while _RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        log.info("Subscriber disconnected.")


if __name__ == "__main__":
    main()
