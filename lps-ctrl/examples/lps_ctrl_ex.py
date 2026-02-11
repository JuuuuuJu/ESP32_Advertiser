from lps_ctrl import ESP32BTSender
import json
import time
PORT = 'COM3' 
def main():    
    try:
        with ESP32BTSender(port=PORT) as sender:

            # 1. Schedule PLAY (Executes in 2s)
            response = sender.send_burst(cmd_input='PLAY', delay_sec=2.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 2. Trigger CHECK (Non-blocking)
            # ESP32 starts scanning in the background.
            response = sender.trigger_check()
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 3. Schedule PAUSE (Executes in 3s)
            # This proves the check didn't block us from sending more commands.
            response = sender.send_burst(cmd_input='PAUSE', delay_sec=3.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # 4. Wait for scan to finish and get report
            time.sleep(2)            
            report = sender.get_latest_report()
            print(json.dumps(report, indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()