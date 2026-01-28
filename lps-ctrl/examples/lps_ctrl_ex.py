from lps_ctrl import ESP32BTSender
import json
PORT = 'COM3' 
def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            response = sender.send_burst(
                cmd_input='PAUSE',
                delay_sec=5, 
                prep_led_sec=1,
                target_ids=[0, 1, 5],
                data=[0, 0, 0], 
                retries=3,
            )
            print(f"Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
            result = sender.check_status()
            print(json.dumps(result, indent=4))
    except Exception as e:
        print(f"Main execution error: {e}")
if __name__ == "__main__":
    main()