# ESP32 BLE Advertiser (UART Controlled)

This project configures the ESP32 as a BLE advertising sender. It receives text commands from a PC via UART and uses the Raw HCI interface to send BLE advertising packets containing precise countdown timers.

## Introduction

The main workflow is as follows:

1.  **Receive Command (UART):** Receives text commands from the PC via USB Serial.
2.  **BLE Broadcasting (BLE Burst):** Uses the Raw HCI (Host Controller Interface) to directly control the Bluetooth controller to broadcast packets without establishing a connection.
3.  **Synchronized Countdown:** Continuously transmits a series of broadcast packets (Burst) within a specified delay time. These packets contain the "remaining time," allowing the receiver to synchronize actions precisely.

## Project Structure

```text
├── adv_esp/
│   ├── CMakeLists.txt      
│   └── main/
│       ├── CMakeLists.txt  
│       ├── main.c          # UART handling, command parsing, task scheduling
│       ├── bt_sender.c     # BLE HCI control, packet assembly
│       └── bt_sender.h     # Header file

```

## UART Protocol

UART settings are as follows:

* **Baud Rate**: `921600`
* **Data bits**: 8, **Stop bits**: 1, **Parity**: None
* **Flow Control**: Disable

### 1. Command Format (PC -> ESP32)

The Python script (`lps_ctrl.py`) formats data into the following string structure for transmission:

```text
cmd_in,delay_us,prep_led_us,target_mask,in_data[0],in_data[1],in_data[2]
```

| Parameter | Type | Description |
| --- | --- | --- |
| **cmd_in** | `int` | Combined value of Command ID and Command Type. Format: `(Command_ID * 16) + Command_Type`. ( 4 bits ( Command ID ) + 1 bit ( blank ) + 3 bits ( Command Type ) ) |
| **delay_us** | `unsigned long` | Expected arrival time (us), at least 1 second. |
| **prep_led_us** | `unsigned long` | Duration for the preparation LED (us). |
| **target_mask** | `unsigned long long` | Bitmask for target IDs. E.g., `5` represents `00...0101` (ID 0 & 2). |
| **in_data[0]** | `int` | Data 0 (Red value / Command ID). |
| **in_data[1]** | `int` | Data 1 (Green value). |
| **in_data[2]** | `int` | Data 2 (Blue value). |

| Command | map code | Description | Data Parameters |
| --- | --- | --- | --- |
| **PLAY** | 0x01 | Start | `[0, 0, 0]` |
| **PAUSE** | 0x02 | Pause | `[0, 0, 0]` |
| **RESET** | 0x03 | Reset | `[0, 0, 0]` |
| **RELEASE** | 0x04 | Enter `UNLOAD` state | `[0, 0, 0]` |
| **LOAD** | 0x05 | Enter `READY` state | `[0, 0, 0]` |
| **TEST** | 0x06 | Change LED color | `[R, G, B]` (0-255) |
| **CANCEL** | 0x07 | Cancel specific command | `[cmd_id, 0, 0]` |

**Example Packet**:

```text
22,3000000,1000000,5,255,0,0
```
* `22`: Represents ID=1, Command=TEST (1*16 + 6)
* `3000000`: 3 seconds delay
* `1000000`: Preparation LED duration of 1 second
* `5`: Targets are IDs 0 and 2
* `255,0,0`: Red
### 2. Response Format (ESP32 -> PC)

#### Successful Receipt (ACK)

When the command is parsed successfully, the ESP32 returns:

```text
ACK:OK:<read_latency>:<parse_latency>:<total_latency>
```
* Data units are in microseconds (us), used for the PC to calculate transmission latency. (For testing purposes)
#### Execution Complete (DONE)

Returned when the Burst broadcast sequence is finished:

```text
DONE
```

#### Error (NAK)

* `NAK:ParseError`: Insufficient parameters or incorrect format.
* `NAK:Overflow`: Receive buffer overflow.

### 3. Check Status

The PC can send a CHECK command to switch the ESP32 into scanning mode temporarily to listen for ACK feedback signals from Receivers.

**PC Sends:**

```text
CHECK
```

**ESP32 Response Flow:**

1. **Confirmation:**
```text
ACK:CHECK_START
```


2. **Reporting Found Devices (Continuous during scan):**
When an ACK packet (Type 0x08) from a receiver is scanned, ESP32 returns:
```text
FOUND:<target_id>,<cmd_id>,<cmd_type>,<delay>
```


* `target_id`: Receiver's Player ID.
* `cmd_id`: The Command ID currently locked by the device.
* `cmd_type`: The command type executed by the device.
* `delay`: The delay time calculated by the device (us).


3. **Scan Complete:**
After the scan duration (default 4 seconds), returns:
```text
CHECK_DONE
```

## BLE Advertising Packet Structure

The packet content is placed in the Manufacturer Specific Data section, sent via `hci_cmd_send_ble_set_adv_data`.

| Byte | Content | Description |
| --- | --- | --- |
| 0-1 | `0xFFFF` | Company ID (Reserved) |
| 2 | `cmd` | Command Type (includes ID) |
| 3-10 | `target_mask` | 8 Bytes, supports IDs 0~63 |
| 11-14 | `delay_us` | Remaining delay time (microseconds) |
| 15-18 | `prep_led_us` | Preparation time (microseconds) |
| 19-21 | `R, G, B` | Color data or command ID to cancel |

## Notes

1. **Latency Compensation**: There is a built-in `TX_OFFSET_US` (default 9000us) to compensate for the hardware delay between sending the command and the actual wireless transmission. This can be adjusted in `bt_sender.c`.
2. **Baud Rate**: Ensure both the Python script and the ESP32 are configured to `921600`.