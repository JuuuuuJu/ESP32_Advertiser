# ESP32 BLE Sender - UART Controlled

This project provides a Python module, `lps_ctrl.py`, which implements a system to control an ESP32 via UART (USB Serial) from a PC. The ESP32 acts as a sender to broadcast Bluetooth Low Energy (BLE) command packets using a non-blocking scheduler, allowing for interleaved broadcasting of multiple commands.

## Installation

It is recommended to create a virtual environment in the `lps-ctrl` directory (where `pyproject.toml` is located) and install the required packages.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## API Documentation

### Class: `ESP32BTSender`

```python
__init__(port, baud_rate=921600, timeout=10)
```

* **port** (Required): Serial port name (e.g., `'COM3'` on Windows or `'/dev/ttyS3'` on Linux).
* **baud_rate**: Default is `921600`. Must match the setting in `main.c` of the `adv_esp` project.
* **timeout**: Default is `10` seconds.

### Method: `send_burst`

Sends a command packet to the ESP32. The ESP32 adds the command to its internal scheduler and returns immediately.

```python3
send_burst(cmd_input, delay_sec, prep_led_sec, target_ids, data)
```

#### Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| **cmd_input** | `str` | Command type (see list below). |
| **delay_sec** | `float` | Expected execution time in seconds. Must be at least 1 second. |
| **prep_led_sec** | `float` | Duration for the preparation LED (seconds). |
| **target_ids** | `list[int]` | List of target device IDs (e.g., [0, 2, 5]). Empty list [] means Broadcast to All. |
| **data** | `list[int]` | Additional data, must contain 3 integers `[d0, d1, d2]`. |

#### Supported Commands and Data Mapping

Current supported `cmd_input` and corresponding `data` usage:

| Command | Map Code | Description | Data Parameters |
| --- | --- | --- | --- |
| **PLAY** | 0x01 | Start | `[0, 0, 0]` |
| **PAUSE** | 0x02 | Pause | `[0, 0, 0]` |
| **RESET** | 0x03 | Reset | `[0, 0, 0]` |
| **RELEASE** | 0x04 | Enter `UNLOAD` state | `[0, 0, 0]` |
| **LOAD** | 0x05 | Enter `READY` state | `[0, 0, 0]` |
| **TEST** | 0x06 | Change LED color | `[R, G, B]` (0-255), `[0, 0, 0]` for playing the pattern |
| **CANCEL** | 0x07 | Cancel specific cmd id | `[cmd_id, 0, 0]` |

**Note**: The `command_id` is included in the return value of `send_burst`. It is guaranteed that adjacent commands will have different IDs. If too many commands are sent instantly (>16 pending), new commands may fail to add. To CANCEL a specific command, retrieve its ID from the response and send a CANCEL command with that ID.

#### Return Value (`send_burst`)

Includes `command_id` and detailed message:

```json
{
    "from": "Host_PC",
    "topic": "command",
    "statusCode": status_code,
    "payload": {
        "target_id": target_ids,
        "command": cmd,
        "command_id": cmd_id,
        "message": message
    }
}
```

* statusCode: 
    * **`0`**: Success (Received ACK and DONE signal)
    * **`-1`**: Failure (Connection error, timeout, or ESP32 returned NAK)

### Method: `trigger_check`

Sends a `CHECK` command to the ESP32. The ESP32 will broadcast a check signal and then switch to scanning mode. This function returns immediately, allowing you to send other commands while the scan runs in the background.

```python
trigger_check(target_ids=[])
```

#### Return Value

Returns the scan report:

```json
{
    "from": "Host_PC",
    "topic": "check_trigger",
    "statusCode": 0,
    "payload": {
        "payload": {
            "target_id": "[...]",
            "command": "command",
            "command_id": "command_id",
            "message": "Check started (ID: X)"
        }
    }
}
```
### Method: `get_latest_report`

Retrieves the results of the scan. Any devices found during the scan window (triggered by trigger_check or passively collected during other commands) are returned here.

```python
get_latest_report()
```

#### Return Value

Returns the scan report:

```json
{
    "from": "Host_PC",
    "topic": "check_report",
    "statusCode": 0,
    "payload": {
        "scan_duration_sec": 2,
        "found_count": 1,
        "found_devices": [
            {
                "target_id": 1,          // Receiver ID
                "cmd_id": 1,             // The command currently locked by the receiver
                "cmd_type": 1,           // Command Type (e.g., 1=PLAY)
                "target_delay": 5398880, // Remaining time (us)
                "state": "UNLOADED"      // Current Player State
            }
        ]
    }
}
```

## Execution Behavior & Constraints

### 1. The "Radio Blind Spot" (Hardware Blocking)

While the Python `trigger_check()` function returns immediately (**Non-blocking**), the ESP32 hardware **cannot broadcast and scan at the same time**.

* **Behavior**: When `trigger_check()` is called, the ESP32 switches to **Observer Mode** for exactly 2 seconds.
* **Constraint**: During these 2 seconds, the ESP32 **stops broadcasting** standard commands (PLAY, LOAD, etc.) to listen for ACKs.
* **Implication**: If you call `send_burst(...)` immediately after `trigger_check()`, the command is successfully accepted by the Python library and sent to the ESP32, **BUT** the ESP32 will queue it and wait until the scan finishes before broadcasting it.
* *Example*: `CHECK` -> (0.1s later) `PLAY`. The `PLAY` signal will actually be transmitted 2 seconds later.

### 2. Command Queue Limit

The ESP32 maintains a strictly timed queue for upcoming commands.

* **Limit**: Maximum **16 pending commands**.
* **Behavior**: If you send more than 16 commands instantly (e.g., inside a fast `for` loop without delays), the ESP32 will return a `Queue full` error, and the command will be dropped.
* **Best Practice**: Ensure your script schedules commands reasonably and does not flood the queue instantly.

## Example

The following example demonstrates sending multiple commands (`LOAD`, `PLAY`, `PAUSE`) scheduled for different times, while simultaneously performing a status check (`CHECK`) without blocking the flow.

Run the following command in the `lps-ctrl` directory:
```bash
python .\examples\lps_ctrl_ex.py
```

Example Code: `lps_ctrl_ex.py`

```python
from lps_ctrl import ESP32BTSender
import json
import time
PORT = 'COM3' 
def main():    
    try:
        with ESP32BTSender(port=PORT) as sender:
            # 1. Schedule LOAD (Executes in 3s)
            response = sender.send_burst(cmd_input='LOAD', delay_sec=3.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 2. Schedule PLAY (Executes in 6s)
            response = sender.send_burst(cmd_input='PLAY', delay_sec=6.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 3. Trigger CHECK (Non-blocking)
            # ESP32 starts scanning in the background.
            response = sender.trigger_check()
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 4. Schedule PAUSE (Executes in 9s)
            # This proves the check didn't block us from sending more commands.
            response = sender.send_burst(cmd_input='PAUSE', delay_sec=9.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 5. Wait for scan to finish and get report
            time.sleep(2.5)  # (just for test in this case, in practice it is not necessary)
            report = sender.get_latest_report()
            print(json.dumps(report, indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
```

json:
```json
{
    "from": "Host_PC",
    "topic": "command",
    "statusCode": 0,
    "payload": {
        "target_id": "[]",
        "command": "LOAD",
        "command_id": "0",
        "message": "Success"
    }
}
{
    "from": "Host_PC",
    "topic": "command",
    "statusCode": 0,
    "payload": {
        "target_id": "[]",
        "command": "PLAY",
        "command_id": "1",
        "message": "Success"
    }
}
{
    "from": "Host_PC",
    "topic": "check_trigger",
    "statusCode": 0,
    "payload": {
        "target_id": "[]",
        "command": "CHECK",
        "command_id": "2",
        "message": "Check started (ID: 2)"
    }
}
{
    "from": "Host_PC",
    "topic": "command",
    "statusCode": 0,
    "payload": {
        "target_id": "[]",
        "command": "PAUSE",
        "command_id": "3",
        "message": "Success"
    }
}
{
    "from": "Host_PC",
    "topic": "check_report",
    "statusCode": 0,
    "payload": {
        "scan_duration_sec": 2,
        "found_count": 1,
        "found_devices": [
            {
                "target_id": 1,
                "cmd_id": 0,
                "cmd_type": 5,
                "target_delay": 2386503,
                "state": "UNLOADED"
            }
        ]
    }
}
```