# ESP32 BLE Advertiser - UART Controlled

This project configures the ESP32 as a BLE advertising sender. It receives text commands from a PC via UART and uses the Raw HCI interface to send BLE advertising packets containing precise countdown timers.

## Introduction

The main workflow is as follows:

1. **Receive Command (UART):** Receives text commands from the PC via USB Serial.
2. **BLE Broadcasting (BLE Burst):** Uses the Raw HCI (Host Controller Interface) to directly control the Bluetooth controller to broadcast packets without establishing a connection.
3. **Synchronized Countdown:** Continuously transmits a series of broadcast packets (Burst) within a specified delay time. These packets contain the "remaining time," allowing the receiver to synchronize actions precisely.
4. **Status Checking:** Supports a hybrid `CHECK` command that first broadcasts a query signal, then switches to scanning mode to collect feedback from receivers.

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

**All commands**, including `CHECK`, use the following CSV format. The Python script (`lps_ctrl.py`) handles this formatting automatically.

```text
cmd_in,delay_us,prep_led_us,target_mask,in_data[0],in_data[1],in_data[2]
```

| Parameter | Type | Description |
| --- | --- | --- |
| **cmd_in** | `int` | Combined value of Command ID and Command Type. Format: `(Command_ID << 4)` |
| **delay_us** | `unsigned long` | Execution delay (us). For `CHECK`, this defines the broadcast duration (e.g., 600000us). |
| **prep_led_us** | `unsigned long` | Duration for the preparation LED (us). |
| **target_mask** | `unsigned long long` | Bitmask for target IDs. E.g., `5` represents `00...0101` (ID 0 & 2). |
| **in_data[0]** | `int` | Data 0 (Red value / Command ID). |
| **in_data[1]** | `int` | Data 1 (Green value). |
| **in_data[2]** | `int` | Data 2 (Blue value). |

#### Supported Command Types (Low 4 bits of `cmd_in`)

| Command | Type Code | Description | Data Parameters |
| --- | --- | --- | --- |
| **PLAY** | 0x01 | Start playback | `[0, 0, 0]` |
| **PAUSE** | 0x02 | Pause playback | `[0, 0, 0]` |
| **RESET** | 0x03 | Reset timeline | `[0, 0, 0]` |
| **RELEASE** | 0x04 | Enter `UNLOAD` state | `[0, 0, 0]` |
| **LOAD** | 0x05 | Enter `READY` state | `[0, 0, 0]` |
| **TEST** | 0x06 | Change LED color | `[R, G, B]` (0-255), `[0, 0, 0]` for playing pattern |
| **CANCEL** | 0x07 | Cancel specific command | `[cmd_id, 0, 0]` |
| **CHECK** | **0x08** | **Trigger Check Sequence** | `[0, 0, 0]` |

### 2. Response Format (ESP32 -> PC)

#### Successful Receipt (ACK)

When **ANY** command (including `CHECK`) is parsed and added to the scheduler, the ESP32 returns:

```text
ACK:OK:<read_latency>:<parse_latency>:<total_latency>
```

* Data units are in microseconds (us), used for latency profiling.

#### Error (NAK)

* `NAK:ParseError`: Insufficient parameters or incorrect format.
* `NAK:Overflow`: Receive buffer overflow.

### 3. Check Status Workflow

The `CHECK` command (Type 0x08) initiates a specific sequence on the ESP32:

1. **Broadcast Phase (approx. 600ms):** The ESP32 broadcasts the `CHECK` signal so receivers know to report back. This phase runs in parallel with other commands in the scheduler.
2. **Scan Phase (approx. 2000ms):**
The ESP32 stops broadcasting and enables the RX scanner to listen for ACKs from receivers.

**PC Report Format (Streaming):**

During the Scan Phase, when a valid ACK is received, the ESP32 streams the following line immediately:

```text
FOUND:<target_id>,<cmd_id>,<cmd_type>,<delay>,<state>
```

| Field | Description |
| --- | --- |
| `target_id` | The ID of the Receiver device. |
| `cmd_id` | The ID of the command currently **locked/executing** on the receiver. |
| `cmd_type` | The Type of the command currently locked on the receiver (e.g., 1 for PLAY). |
| `delay` | The remaining time (us) calculated by the receiver. |
| `state` | The current FSM state of the Player (e.g., 0=UNLOADED, 1=READY, 2=PLAYING). |

**Completion:**

When the scan duration ends, the ESP32 sends:

```text
CHECK_DONE
```

## BLE Advertising Packet Structure

The packet content is placed in the Manufacturer Specific Data section.

| Byte | Content | Description |
| --- | --- | --- |
| 0-2 | `0xFFFF` | Company ID (Reserved) |
| 3 | `cmd` | **High 4-bit**: Command ID. **Low 4-bit**: Command Type |
| 4-11 | `target_mask` | 8 Bytes, supports IDs 0~63 |
| 12-15 | `delay_us` | Remaining delay time (microseconds) |
| 16-19 | `prep_led_us` | Preparation time (microseconds) |
| 20-22 | `data[3]` | R, G, B or other parameters |

## Notes

1. **Latency Compensation**: There is a built-in `TX_OFFSET_US` (default 9000us) to compensate for the hardware delay between sending the command and the actual wireless transmission.
2. **Task Scheduling**: The Sender uses a Round-Robin scheduler to interleave multiple active commands (e.g., broadcasting `PLAY` and `CHECK` simultaneously during the broadcast phase).
3. **Check Limitation**: During the **Scan Phase** (2 seconds), the Sender **cannot broadcast**. Any commands sent from the PC during this time will be queued and broadcasted after the scan finishes.