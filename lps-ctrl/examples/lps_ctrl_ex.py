from lps_ctrl import ESP32BTSender
import json
import time
PORT = 'COM3' 
def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            response = sender.send_burst(
                cmd_input='LOAD',
                delay_sec=5, 
                prep_led_sec=1,
                target_ids=[],
                data=[0, 0, 0],
            )
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            response = sender.send_burst(
                cmd_input='PLAY',
                delay_sec=5, 
                prep_led_sec=1,
                target_ids=[],
                data=[0, 0, 0],
            )
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            response = sender.send_burst(
                cmd_input='PAUSE',
                delay_sec=5, 
                prep_led_sec=1,
                target_ids=[],
                data=[0, 0, 0],
            )
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            time.sleep(2)
            result = sender.check_status()
            print(json.dumps(result, indent=4))
    except Exception as e:
        print(f"Main execution error: {e}")
if __name__ == "__main__":
    main()