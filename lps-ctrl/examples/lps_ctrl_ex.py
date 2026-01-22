import argparse
from lps_ctrl.lps_ctrl import ESP32BTSender
import time
import json
PORT = 'COM3' 
def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            # CANCEL: data[0]=cmd_id / TEST: rgb
            for i in range(2):
                response = sender.send_burst(
                    cmd_input='PLAY',
                    delay_sec=3, 
                    prep_led_sec=1,
                    target_ids=[0, 1, 5],
                    data=[0, 0, 0], 
                    retries=3,
                )
                print(f"Command {i} Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
                if response['statusCode'] == 0:
                    pass
                else:
                    print(f"PLAY failed at index {i}, Reason: {response['payload']['message']}")
    except Exception as e:
        print(f"Main execution error: {e}")
if __name__ == "__main__":

    main()
