# ESP32 BLE Sender - UART Controlled

本專案提供了一個封裝好的 Python 模組 bt_controller.py。這個模組實現了一個透過 PC 端 Python 腳本經由 UART (USB Serial) 控制 ESP32 發送藍牙 (BLE) 廣播指令封包的系統。

## 安裝需求

```powershell
pip install -e .
```

## API 說明

Class: ESP32BTSender
```
__init__(port, baud_rate=921600, timeout=1):
```
port: (必填) 序列埠名稱。

baud_rate: 預設為 921600 (需與 ESP32 設定一致)。
```
send_burst(cmd_input, delay_sec, target_ids, prep_sec):
```
cmd_input (str): 指令類型 ('RESET', 'READY', 'TEST', 'PLAY', 'PAUSE')。

delay_sec (float): 預期送達時間 (秒)，至少 1 秒 (e.g., 30)。

prep_sec (float): delay 燈持續時間 (秒)

target_ids (list): 目標設備 ID 列表 (e.g., [0, 2, 5])。

data (list): 當指令為 'TEST' 或 'CANCEL' 時需填入
| Command       | data[0] | data[1] | data[2] | 說明 |
|:-------------:|:-------:|:-------:|:-------:|:----:|
|'TEST'  |R|G|B|設定 RGB 燈光顏色|
|'CANCEL'|cmd_id|(N/A)|(N/A)|取消指定 ID 的指令|

Return: True 代表執行成功且收到 ESP32 回應；False 代表失敗或超時。

## 使用範例
```
from src.lps_ctrl.lps_ctrl import ESP32BTSender

# 請修改為實際 COM Port
PORT = 'COM13' 

with ESP32BTSender(port=PORT) as sender:
    # 發送指令：類型 play ，倒數 3 秒，給 player ID 0, 1, 5 ，delay 燈 1 秒
    if sender.send_burst(
        cmd_input='PLAY',
        delay_sec=2, 
        prep_led_sec=1,
        target_ids=[0, 1, 5],
        data=[0, 0, 0],
        retries=3,
    ):
        print("Passed")
    else:
        print("Failed")
```
