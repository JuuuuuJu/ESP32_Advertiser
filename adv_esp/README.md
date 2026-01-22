# ESP32 BLE Advertiser (UART Controlled)

本專案將 ESP32 作為 BLE 廣播發射器，透過 UART 接收 PC 端的指令，並利用 Raw HCI 介面發送帶有精確倒數計時的 BLE 廣播封包。

## 簡介

主要運作流程如下：

1.  接收指令 (UART)：透過 USB Serial 接收來自 PC 的文字指令。
2.  藍牙廣播 (BLE Burst)：使用 Raw HCI (Host Controller Interface) 直接控制藍牙控制器，不建立連線，只是發送廣播封包。
3.  同步倒數：在指定的延遲時間內，連續發送一連串的廣播封包 (Burst)，封包內含「剩餘時間」，讓接收端能精準同步執行動作。



## 專案結構

```text
├── adv_esp/
│   ├── CMakeLists.txt      
│   └── main/
│       ├── CMakeLists.txt  
│       ├── main.c          # UART 處理、指令解析、任務排程
│       ├── bt_sender.c     # BLE HCI 控制、廣播封包組建
│       └── bt_sender.h     # 標頭檔
```

## UART 通訊協定

UART 設定如下：

* **Baud Rate**: `921600`
* **Data bits**: 8, **Stop bits**: 1, **Parity**: None
* **Flow Control**: Disable

### 1. 接收指令格式 (PC -> ESP32)

Python 端的 `lps_ctrl.py` 會將資料格式化為以下結構用字串的形式發送：

```text
cmd_in,delay_us,prep_led_us,target_mask,in_data[0],in_data[1],in_data[2]
```

| 參數 | 類型 | 說明 |
| --- | --- | --- |
| **cmd_in** | `int` | 包含 Command ID 與 Command Type 的組合值。格式為：`(Command_ID * 16) + Command_Type`，也就是 4 bits ( Command ID ) + 1 bit ( blank ) + 3 bits ( Command Type ) |
| **delay_us** | `unsigned long` | 預期送達時間 (us)，至少 1 秒 。 |
| **prep_led_us** | `unsigned long` | delay 燈持續時間 (us) |
| **target_mask** | `unsigned long long` | 目標 ID 的 Bitmask，例如 `5` 代表 `00...0101` (ID 0 & 2) |
| **in_data[0]** | `int` | 資料 0 (R 值 / Command ID ) |
| **in_data[1]** | `int` | 資料 1 (G 值) |
| **in_data[2]** | `int` | 資料 2 (B 值) |


| Command     | map code    | 說明                     | data 參數           |
|:----------- |:--- |:------------------------ |:------------------- |
| **PLAY**    | 0x01 | 開始                     | `[0, 0, 0]`         |
| **PAUSE**   | 0x02 | 暫停                     | `[0, 0, 0]`         |
| **RESET**   | 0x03 | 重置                     | `[0, 0, 0]`         |
| **RELEASE** | 0x04 | 進入 `UNLOAD` state      | `[0, 0, 0]`         |
| **LOAD**    | 0x05 | 進入 `READY` state       | `[0, 0, 0]`         |
| **TEST**    | 0x06 | 改變 LED 顏色            | `[R, G, B]` (0-255) |
| **CANCEL**  | 0x07 | 取消特定command id的指令 | `[cmd_id, 0, 0]`    |

**範例封包**:

```text
17,3000000,1000000,5,255,0,0
```

* `17`: 代表 ID=1, Command=PLAY (1*16 + 1)
* `3000000`: 延遲 3 秒
* `1000000`: delay 燈持續 1 秒
* `5`: 目標為 ID 0 和 2
* `255,0,0`: 紅色

### 2. 回應格式 (ESP32 -> PC)

ESP32 會回傳執行狀態與延遲測量數據。

#### 成功接收 (ACK)

當指令解析成功，ESP32 會回傳：

```text
ACK:OK:<read_latency>:<parse_latency>:<total_latency>
```

* 數據單位皆為微秒 (us)，用於讓 PC 端計算傳輸延遲。(測試用)

#### 執行完成 (DONE)

當 Burst 廣播序列發送完畢後回傳：

```text
DONE
```

#### 錯誤 (NAK)

* `NAK:ParseError`: 參數數量不足或格式錯誤。
* `NAK:Overflow`: 接收緩衝區溢出。

## BLE 廣播封包結構

封包內容放在 Manufacturer Specific Data，在`hci_cmd_send_ble_set_adv_data`裡發送。

| Byte | 內容 | 說明 |
| --- | --- | --- |
| 0-1 | `0xFFFF` | Company ID (Reserved) |
| 2 | `cmd` | Command Type (含 ID) |
| 3-10 | `target_mask` | 8 Bytes，支援 ID 0~63 |
| 11-14 | `delay_us` | 剩餘延遲時間 (微秒) |
| 15-18 | `prep_led_us` | 預備時間 (微秒) |
| 19-21 | `R, G, B or cancel cmd_id` | 顏色數據 or 要 cancel 的 command id |


## 注意事項

1. **Latency 補償**: 內建 `TX_OFFSET_US` (預設 9000us) 用於補償發送指令到實際發出無線訊號的硬體延遲，可於 `bt_sender.c` 中調整。
2. **Baud Rate**: 務必確保 Python 端與 ESP32 端皆設定為 `921600`。


