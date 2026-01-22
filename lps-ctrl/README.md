# ESP32 BLE Sender - UART Controlled

本專案提供了一個封裝好的 Python 模組 `lps_ctrl.py`，這個模組實現了一個透過 PC 端 Python 腳本經由 UART (USB Serial) 控制 ESP32 發送藍牙 (BLE) 廣播指令封包的系統。

## 安裝需求

建議在`lps-ctrl`資料夾（包含 `pyproject.toml`）下建立虛擬環境並安裝需要的package

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## API 說明

### Class: `ESP32BTSender`

```python
__init__(port, baud_rate=921600, timeout=10)
```
* port (必填): 序列埠名稱 (例如 Windows 的 `'COM3'` 或 Linux 的 `'/dev/ttyS3'`)。
* baud_rate: 預設 `921600`，和`adv_esp`裡`main.c`的設定要一致。
* timeout: 預設 `10` 秒。

### Method: `send_burst`

發送指令封包給 ESP32，並等待執行結果。

```python
send_burst(cmd_input, delay_sec, prep_led_sec, target_ids, data, retries=3)
```

#### 參數說明

| 參數 | 類型 | 說明 |
| :--- | :--- | :--- |
| **cmd_input** | `str` | 指令類型 (詳見下方指令列表) |
| **delay_sec** | `float` | 預期送達時間 (秒)，至少 1 秒 (e.g., 30)。 |
| **prep_led_sec** | `float` | delay 燈持續時間 (秒) |
| **target_ids** | `list[int]` | 目標設備 ID 列表 (e.g., [0, 2, 5])。 |
| **data** | `list[int]` | 附加資料，必須包含 3 個整數`[d0, d1, d2]` |
| **retries** | `int` | 若未收到 ESP32 的 ACK，自動重試的次數。預設為 `3` |

#### 支援指令與 Data 對應表

目前支援的 `cmd_input` 及其對應的 `data` 用法：

| Command     | map code    | 說明                     | data 參數           |
|:----------- |:--- |:------------------------ |:------------------- |
| **PLAY**    | 0x01 | 開始                     | `[0, 0, 0]`         |
| **PAUSE**   | 0x02 | 暫停                     | `[0, 0, 0]`         |
| **RESET**   | 0x03 | 重置                     | `[0, 0, 0]`         |
| **RELEASE** | 0x04 | 進入 `UNLOAD` state      | `[0, 0, 0]`         |
| **LOAD**    | 0x05 | 進入 `READY` state       | `[0, 0, 0]`         |
| **TEST**    | 0x06 | 改變 LED 顏色            | `[R, G, B]` (0-255) |
| **CANCEL**  | 0x07 | 取消特定command id的指令 | `[cmd_id, 0, 0]`    |

補充: command id 會包含在`send_burst`回傳的內容，且保證前後相鄰的command，id必不相同。若瞬間指令過多 (>16筆 pending) 可能會導致新指令無法加入。如果要CANCEL特定指令可以往回找到該指令的id進而CANCEL掉該指令。

#### Return Value

包含`command_id`與詳細訊息：

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

* **statusCode**:
    * `0`: 成功 (收到 ACK 且收到 DONE 信號)
    * `-1`: 失敗 (連線錯誤、超時、或 ESP32 回傳 NAK)

## 使用範例

在`lps-ctrl`目錄下執行

```bash
python .\examples\lps_ctrl_ex.py
```

範例: `lps_ctrl_ex.py`
```python
from lps_ctrl import ESP32BTSender
import json

# Port number
PORT = 'COM3' 

def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            # send_burst return json format
            response = sender.send_burst(
                cmd_input='PLAY',
                delay_sec=3, 
                prep_led_sec=1,
                target_ids=[0, 1, 5],
                data=[0, 0, 0], 
                retries=3,
            )
            print(f"Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
            if response['statusCode'] == 0:
                pass
            else:
                print(f"PLAY failed, Reason: {response['payload']['message']}")
    except Exception as e:
        print(f"Main execution error: {e}")
if __name__ == "__main__":

    main()

```
以下是return的json
```json
{
    "from": "Host_PC",
    "topic": "command",
    "statusCode": 0,
    "payload": {
        "target_id": "[0, 1, 5]",
        "command": "PLAY",
        "command_id": "0",
        "message": "Success"
    }
}
```