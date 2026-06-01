"""BLE client that listens for category-select notifications from the ESP32.

The ESP32 firmware exposes a characteristic with PROPERTY_NOTIFY whose value is
a JSON payload like {"category":"scientist"}. Each button press triggers one
notify; we forward valid categories to the server's event queue when the
mirror is in the category_select state.
"""

import asyncio
import json
import time

import server


DEVICE_NAME = "ESP32 Selector"
ADDRESS = "8E6AA1FA-3B99-4A4D-BC3E-ADFB34EC55D6"
CHAR_UUID = "abcd1234-ab12-ab12-ab12-abcdef123456"
VALID = {"scientist", "engineer", "entrepreneur"}

SCAN_TIMEOUT_S = 10.0
RESCAN_BACKOFF_S = 5.0
DISCONNECT_BACKOFF_S = 2.0


def run() -> None:
    """Daemon-thread entrypoint: spins up an asyncio loop and runs _main()."""
    try:
        asyncio.run(_main())
    except Exception as exc:
        server.write_perf_log("ble_thread_crash", error=str(exc))
        print(f"ble_client: thread exiting due to {exc}")


async def _main() -> None:
    try:
        from bleak import BleakClient, BleakScanner
        from bleak.exc import BleakError
    except ImportError:
        print("ble_client: bleak unavailable, BLE disabled")
        server.write_perf_log("ble_disabled", reason="bleak_not_installed")
        return

    server.write_perf_log("ble_started")

    while True:
        try:
            device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=SCAN_TIMEOUT_S)
            if device is None:
                server.write_perf_log("ble_scan_no_device", device_name=DEVICE_NAME)
                await asyncio.sleep(RESCAN_BACKOFF_S)
                continue

            server.write_perf_log("ble_device_found", address=str(device.address))

            async with BleakClient(device) as client:
                server.write_perf_log("ble_connected", address=str(device.address))

                def _on_notify(_handle, data: bytearray) -> None:
                    _handle_payload(bytes(data))

                await client.start_notify(CHAR_UUID, _on_notify)
                server.write_perf_log("ble_notify_started", char=CHAR_UUID)

                while client.is_connected:
                    await asyncio.sleep(1.0)

                server.write_perf_log("ble_disconnected", address=str(device.address))

        except BleakError as exc:
            server.write_perf_log("ble_error", error=str(exc))
            print(f"ble_client: BleakError {exc}")
            await asyncio.sleep(DISCONNECT_BACKOFF_S)
        except Exception as exc:
            server.write_perf_log("ble_loop_exception", error=str(exc))
            print(f"ble_client: unexpected error {exc}")
            await asyncio.sleep(DISCONNECT_BACKOFF_S)


def _handle_payload(data: bytes) -> None:
    try:
        text = data.decode("utf-8").strip()
        obj = json.loads(text)
        cat = obj.get("category")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as exc:
        server.write_perf_log("ble_parse_error", error=str(exc), raw=repr(data[:64]))
        return

    if cat not in VALID:
        return

    state, _ = server.get_state_snapshot()
    if state != "category_select":
        server.write_perf_log("ble_ignored_wrong_state", category=cat, state=state)
        return

    server.set_selected_category(cat)
    server.enqueue_event(
        {"type": "category_selected", "category": cat},
        source="ble_client",
    )