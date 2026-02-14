from lps_ctrl import ESP32BTSender
import json
import time
PORT = 'COM3' 
def main():    
    try:
        with ESP32BTSender(port=PORT) as sender:
            for i in range(100):
                response = sender.send_burst(cmd_input='PLAY', delay_sec=10.0, prep_led_sec=5, target_ids=[], data=[0,0,0])
                time.sleep(2)
    except Exception as e:
        print(f"Error: {e}")
if __name__ == "__main__":
    main()