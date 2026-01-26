from lps_ctrl import ESP32BTSender
import json
PORT = 'COM3' 
def main():
    try:
        with ESP32BTSender(port=PORT) as sender:
            response = sender.send_burst(
                cmd_input='LOAD',
                delay_sec=1, 
                prep_led_sec=1,
                target_ids=[0, 1, 5],
                data=[0, 0, 0], 
                retries=3,
            )
            print(f"Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
            response = sender.send_burst(
                cmd_input='PLAY',
                delay_sec=3, 
                prep_led_sec=1,
                target_ids=[0, 1, 5],
                data=[0, 0, 0], 
                retries=3,
            )
            print(f"Result: {json.dumps(response, indent=4, ensure_ascii=False)}")
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
            # if response['statusCode'] == 0:
            #     pass
            # else:
            #     print(f"PLAY failed, Reason: {response['payload']['message']}")
    except Exception as e:
        print(f"Main execution error: {e}")
if __name__ == "__main__":

    main()
# import serial
# import time
# import threading
# ser = serial.Serial('COM3', 921600, timeout=1)
# def monitor_thread(ser_instance):
#     while True:
#         try:
#             if ser_instance.in_waiting > 0:
#                 line = ser_instance.readline().decode('utf-8', errors='ignore').strip()
#                 if line:
#                     print(f"[ESP Log]: {line}")
#         except:
#             break
# t = threading.Thread(target=monitor_thread, args=(ser,))
# t.daemon = True
# t.start()

# try:
#     print("Start")
#     cmd = "1,1000000,1000000,23,0,0,0\n"
#     print(f"[PC] Sending: {cmd.strip()}")
#     ser.write(cmd.encode())
#     time.sleep(1)
#     print("[PC] Sending CHECK...")
#     ser.write(b"CHECK\n")
#     time.sleep(5) 

# except KeyboardInterrupt:
#     print("Stop")
#     ser.close()