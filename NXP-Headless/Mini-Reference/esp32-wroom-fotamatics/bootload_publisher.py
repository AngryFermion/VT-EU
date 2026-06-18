#!/usr/bin/env python3
"""
FOTA Serial Load Command Publisher
Publishes serial load commands to trigger FOTA transmission via serial
"""

import sys
import time
import json
from datetime import datetime
import paho.mqtt.client as mqtt

# MQTT Configuration (matching your setup)
MQTT_BROKER = "broker.emqx.io" #"test.mosquitto.org"
MQTT_PORT = 1883 #1884
MQTT_USERNAME = "rw"
MQTT_PASSWORD = "readwrite"

# MQTT Topic Configuration (using new directional structure)
MQTT_BASE_TOPIC = "SmartWheelsNS"
DEVICE_ID = "ABCD"  # Device ID (fixed for now)

# Build MQTT topics with device ID
TOPIC_SERVER_FOTA_BOOTLOAD = f"{MQTT_BASE_TOPIC}/server/{DEVICE_ID}/fota/bootload"
TOPIC_DEVICE_FOTA_PROGRESS = f"{MQTT_BASE_TOPIC}/device/{DEVICE_ID}/fota/progress"

# Configuration
WAIT_FOR_PROGRESS = True        # Wait and display progress messages
PROGRESS_TIMEOUT = 120          # Seconds to wait for progress updates

# Global variables
connected = False
progress_received = False
transmission_done = False
last_progress_time = 0.0

def on_connect(client, userdata, flags, reason_code, properties=None):
    """Callback for MQTT connection - compatible with both API versions"""
    global connected

    if reason_code == 0:
        connected = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")

        # Subscribe to progress topic if monitoring is enabled
        if WAIT_FOR_PROGRESS:
            client.subscribe(TOPIC_DEVICE_FOTA_PROGRESS, qos=0)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Subscribed to progress topic: {TOPIC_DEVICE_FOTA_PROGRESS}")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Failed to connect to MQTT broker, return code {reason_code}")

TERMINAL_STATUSES = {
    "transmission_complete", "transmission_failed",
    "error_no_file", "error_transmission_busy",
    "bootload_complete", "bootload_failed",
}

def on_message(client, userdata, msg):
    """Callback for MQTT message reception"""
    global progress_received, transmission_done, last_progress_time

    try:
        topic = getattr(msg, 'topic', 'unknown')
        payload_bytes = getattr(msg, 'payload', b'')

        if topic == TOPIC_DEVICE_FOTA_PROGRESS:
            try:
                payload = payload_bytes.decode('utf-8', errors='replace')
            except (UnicodeDecodeError, AttributeError):
                payload = str(payload_bytes)

            if payload and payload.strip():
                try:
                    progress_data = json.loads(payload)
                    status = progress_data.get("status", "unknown")
                    percent = progress_data.get("percent", None)
                    line = progress_data.get("line", 0)

                    ts = datetime.now().strftime('%H:%M:%S')

                    if status == "progress" and percent is not None:
                        bar = "#" * (percent // 10) + "-" * (10 - percent // 10)
                        print(f"[{ts}] [{bar}] {percent}%")
                    else:
                        print(f"[{ts}] STATUS: {status}", end="")
                        if line > 0:
                            print(f" (line {line})", end="")
                        print()

                    progress_received = True
                    last_progress_time = time.time()

                    if status in TERMINAL_STATUSES:
                        print(f"[{ts}] Transmission finished: {status}")
                        transmission_done = True

                except (json.JSONDecodeError, ValueError, TypeError):
                    clean_payload = payload.strip()
                    if clean_payload:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] PROGRESS: {clean_payload}")
                        progress_received = True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] PROGRESS: Empty message received")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error processing progress message: {e}")
        try:
            topic_safe = getattr(msg, 'topic', 'N/A')
            payload_safe = str(getattr(msg, 'payload', b'N/A'))[:100]
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Raw message: topic='{topic_safe}', payload='{payload_safe}...'")
        except:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Could not safely log message details")

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    """Callback for MQTT publish - compatible with both API versions"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Command published successfully (mid: {mid})")

def publish_bootload_command(transport="serial"):
    """Publish FOTA bootload command"""
    global connected, progress_received, transmission_done, last_progress_time

    connected = False
    progress_received = False
    transmission_done = False
    last_progress_time = 0.0

    print("=" * 60)
    print("FOTA Bootload Transport Publisher")
    print("=" * 60)
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topic: {TOPIC_SERVER_FOTA_BOOTLOAD}")
    print(f"Payload: {transport}")
    print(f"Progress Monitoring: {'Enabled' if WAIT_FOR_PROGRESS else 'Disabled'}")
    print("=" * 60)

    # Setup MQTT client with maximum stability settings
    try:
        # Try VERSION2 first, fallback to older versions for compatibility
        client = mqtt.Client()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] MQTT client creation error: {e}")
        client = mqtt.Client()  # Basic fallback

    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish

    # Simplified logging without detailed error reporting to avoid protocol issues
    def on_log(client, userdata, level, buf):
        # Only log critical errors to avoid noise
        if level <= mqtt.MQTT_LOG_ERR and "Unrecognised command" not in str(buf):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] MQTT Warning: {buf}")

    client.on_log = on_log

    # Configure client options for maximum stability
    try:
        client.max_inflight_messages_set(1)  # Reduce to minimum
        client.max_queued_messages_set(10)   # Limit queue size
    except:
        pass  # Ignore if methods don't exist

    try:
        # Connect to MQTT broker
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to MQTT broker...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        # Wait for connection
        timeout = 10
        while not connected and timeout > 0:
            time.sleep(0.5)
            timeout -= 0.5

        if not connected:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Failed to connect to MQTT broker")
            return False

        # Publish the transport as payload
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Publishing '{transport}' to topic: '{TOPIC_SERVER_FOTA_BOOTLOAD}'")
        result = client.publish(TOPIC_SERVER_FOTA_BOOTLOAD, transport, qos=1)

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: Failed to publish command, error code: {result.rc}")
            return False

        # Wait for publish confirmation
        time.sleep(1)

        # Monitor progress if enabled.
        # loop_start() already runs the MQTT network loop in a background thread,
        # so we just sleep here and wait for on_message() to set our flags.
        if WAIT_FOR_PROGRESS:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Monitoring progress (timeout: {PROGRESS_TIMEOUT}s)...")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Press Ctrl+C to stop monitoring")

            start_time = time.time()

            while time.time() - start_time < PROGRESS_TIMEOUT:
                if transmission_done:
                    break

                if progress_received and last_progress_time > 0 and (time.time() - last_progress_time > 30):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No progress updates for 30 seconds, continuing to monitor...")

                time.sleep(0.5)

            if not progress_received:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] No progress messages received within timeout period")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Progress monitoring completed")

        return True

    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Interrupted by user")
        return True

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
        return False

    finally:
        try:
            client.disconnect()   # closes socket → unblocks background thread immediately
            client.loop_stop()    # joins thread (now exits fast)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Disconnected from MQTT broker")
        except Exception as cleanup_e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Error during cleanup: {cleanup_e}")

def print_help():
    """Print usage help"""
    print("FOTA Bootload Transport Publisher")
    print("\nUsage:")
    print("  python fota_serial_load_publisher.py [transport] [options]")
    print("\nTransport Types:")
    print("  serial   - Use serial interface for transmission (default)")
    print("  can      - Use CAN interface for transmission")
    print("\nOptions:")
    print("  --no-progress    - Don't monitor progress messages")
    print("  --help, -h       - Show this help message")
    print("\nExamples:")
    print("  python fota_serial_load_publisher.py")
    print("  python fota_serial_load_publisher.py serial")
    print("  python fota_serial_load_publisher.py can")
    print("  python fota_serial_load_publisher.py serial --no-progress")
    print("\nMQTT Configuration:")
    print(f"  Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  Bootload Topic: {TOPIC_SERVER_FOTA_BOOTLOAD}")
    print(f"  Progress Topic: {TOPIC_DEVICE_FOTA_PROGRESS}")

def main():
    """Main function"""
    global WAIT_FOR_PROGRESS

    transport = "serial"  # Default transport

    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print_help()
            return 0
        elif sys.argv[1] == "--no-progress":
            WAIT_FOR_PROGRESS = False
        elif sys.argv[1] not in ["serial", "can"]:
            print(f"Unknown transport: {sys.argv[1]}")
            print("Use --help for usage information")
            return 1
        else:
            transport = sys.argv[1]

    # Check for additional options
    if "--no-progress" in sys.argv:
        WAIT_FOR_PROGRESS = False

    # Publish the bootload command
    success = publish_bootload_command(transport)
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Program terminated by user")
        sys.exit(0)