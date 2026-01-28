# ESP32 BLE Sender - UART Controlled

This project provides a Python module, `lps_ctrl.py`, which implements a system to control an ESP32 via UART (USB Serial) from a PC. The ESP32 acts as a sender to broadcast Bluetooth Low Energy (BLE) command packets.

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

Sends a command packet burst to the ESP32 and waits for the execution result.

```python
send_burst(cmd_input, delay_sec, prep_led_sec, target_ids, data, retries=3)
```

#### Parameters

| Parameter | Type | Description |
| --- | --- | --- |
| **cmd_input** | `str` | Command type (see list below). |
| **delay_sec** | `float` | Expected arrival/execution time in seconds. Must be at least 1 second. |
| **prep_led_sec** | `float` | Duration for the preparation LED (seconds). |
| **target_ids** | `list[int]` | List of target device IDs (e.g., [0, 2, 5]). |
| **data** | `list[int]` | Additional data, must contain 3 integers `[d0, d1, d2]`. |
| **retries** | `int` | Number of automatic retries if no ACK is received from ESP32. Default is `3`. |

#### Supported Commands and Data Mapping

Current supported `cmd_input` and corresponding `data` usage:

| Command | Map Code | Description | Data Parameters |
| --- | --- | --- | --- |
| **PLAY** | 0x01 | Start | `[0, 0, 0]` |
| **PAUSE** | 0x02 | Pause | `[0, 0, 0]` |
| **RESET** | 0x03 | Reset | `[0, 0, 0]` |
| **RELEASE** | 0x04 | Enter `UNLOAD` state | `[0, 0, 0]` |
| **LOAD** | 0x05 | Enter `READY` state | `[0, 0, 0]` |
| **TEST** | 0x06 | Change LED color | `[R, G, B]` (0-255) |
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

### Method: `check_status`

Sends a CHECK command to the ESP32, switching it to scan mode to listen for ACK broadcasts from Receivers, and returns informations of the latest command.

```python
check_status()
```

#### Return Value (`check_status`)

Returns the scan report:

```json
{
    "from": "Host_PC",
    "topic": "check_report",
    "statusCode": 0,
    "payload": {
        "scan_duration_sec": 2,
        "found_devices": [
            {
                "target_id": 1,        // ID of the Receiver
                "cmd_id": 0,           // The command ID locked by the receiver
                "cmd_type": 2,         // The command type executed (e.g., 2=PAUSE)
                "target_delay": 4255023 // Calculated delay in microseconds
            }
        ]
    }
}
```

## Example

Run the following command in the `lps-ctrl` directory:
```bash
python .\examples\lps_ctrl_ex.py
```

Example Code: `lps_ctrl_ex.py`

```python
from lps_ctrl import ESP32BTSender
import json

# Port number
PORT = 'COM3' 

def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            # 1. Send Command (Burst)
            response = sender.send_burst(
                cmd_input='PAUSE',
                delay_sec=5, 
                prep_led_sec=1,
                target_ids=[0, 1, 5],
                data=[0, 0, 0], 
                retries=3,
            )
            print(f"Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
            
            # 2. Check Status
            # Ask Sender to scan for Receivers' ACK
            result = sender.check_status()
            print(json.dumps(result, indent=4))

    except Exception as e:
        print(f"Main execution error: {e}")

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
        "target_id": "[0, 1, 5]",
        "command": "PAUSE",
        "command_id": "0",
        "message": "Success"
    }
}
{
    "from": "Host_PC",
    "topic": "check_report",
    "statusCode": 0,
    "payload": {
        "scan_duration_sec": 2,
        "found_devices": [
            {
                "target_id": 1,
                "cmd_id": 0,
                "cmd_type": 2,
                "target_delay": 4255023
            }
        ]
    }
}
```