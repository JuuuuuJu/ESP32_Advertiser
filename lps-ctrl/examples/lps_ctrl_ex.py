from lps_ctrl import ESP32BTSender
import json
import time
PORT = 'COM3' 
def main():    
    try:
        with ESP32BTSender(port=PORT) as sender:

            # Cmd ID 0: Schedules PLAY to execute in 2.0s.
            response = sender.send_burst(cmd_input='PLAY', delay_sec=2.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            
            # Cmd ID 1: Schedules PAUSE to execute in 5.0s.
            response = sender.send_burst(cmd_input='PAUSE', delay_sec=5.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # Cmd ID 2: Cancels Cmd ID 1 (PAUSE) in 1.0s.
            # Since 1.0s < 5.0s, the PAUSE action will be intercepted and stopped.
            response = sender.send_burst(cmd_input='CANCEL', delay_sec=1.0, prep_led_sec=0, target_ids=[], data=[1,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            
            time.sleep(0.5)
            # Cmd ID 3: Triggers a non-blocking status check.
            # ESP32 broadcasts for 600ms, then scans for 2s in background.
            response = sender.trigger_check()
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")
            
            # Cmd ID 4: Schedules STOP at 6.0s.
            # This command is queued successfully even if the Sender is currently scanning.
            response = sender.send_burst(cmd_input='STOP', delay_sec=6.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # Cmd ID 5: Schedules TEST at 7.0s.
            response = sender.send_burst(cmd_input='TEST', delay_sec=7.0, prep_led_sec=0, target_ids=[], data=[0,0,0])
            print(f"{json.dumps(response, indent=4, ensure_ascii=False)}")

            # Waits for the 2s scan window to finish, then fetches the aggregated report.
            time.sleep(2)            
            report = sender.get_latest_report()
            print(json.dumps(report, indent=4, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()