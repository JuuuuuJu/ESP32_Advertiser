import serial
import time
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ESP32BTSender:
    CMD_MAP = { "PLAY": 0x01, "PAUSE": 0x02, "STOP": 0x03, "RELEASE": 0x04, "TEST": 0x05, "CANCEL": 0x06, "CHECK": 0x07 }
    STATE_MAP = { 0: "UNLOADED", 1: "READY", 2: "PLAYING", 3: "PAUSE", 4: "TEST" }

    def __init__(self, port, baud_rate=921600, timeout=1):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None
        
        self.found_devices_buffer = [] 
        self.cmd_list = [0] * 16 
        self.idx = -1

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
            time.sleep(2)
            self.ser.reset_input_buffer()
            logger.info(f"Connected to {self.port}")
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _format_response(self, status_code, cmd, target_ids, cmd_id, message):
        return {
            "from": "Host_PC",
            "topic": "command",
            "statusCode": status_code,
            "payload": {
                "target_id": str(target_ids),
                "command": str(cmd),
                "command_id": str(cmd_id),
                "message": message
            }
        }

    def _read_until_ack_or_timeout(self, expected_ack="ACK:OK", timeout=1.0):
        start_time = time.time()
        last_msg = ""
        
        while (time.time() - start_time) < timeout:
            if self.ser.in_waiting > 0:
                try:
                    line = self.ser.read_until(b'\n').decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    if expected_ack in line:
                        return True, "Success"
                    
                    elif line.startswith("FOUND:"):
                        self._parse_found_line(line)
                    
                    elif line == "CHECK_DONE":
                        pass
                        
                    elif "NAK" in line:
                        return False, f"Device rejected: {line}"
                    
                    else:
                        last_msg = line
                        
                except Exception as e:
                    return False, str(e)
            else:
                time.sleep(0.005) 
                
        return False, f"Timeout or Unexpected: {last_msg}"

    def _parse_found_line(self, line):
        try:
            parts = line.replace("FOUND:", "").split(',')
            if len(parts) >= 5:
                state = self.STATE_MAP.get(int(parts[4]), "UNKNOWN")
                packet = {
                    "target_id": int(parts[0]),
                    "cmd_id": int(parts[1]),
                    "cmd_type": int(parts[2]),
                    "target_delay": int(parts[3]),
                    "state": state
                }
                if packet not in self.found_devices_buffer:
                    self.found_devices_buffer.append(packet)
        except Exception as e:
            logger.error(f"Parse error: {e}")

    def send_burst(self, cmd_input, delay_sec, prep_led_sec, target_ids, data):
        error_response = self._format_response(-1, cmd_input, target_ids, -1, "Port not open")
        if not self.ser or not self.ser.is_open:
            return error_response

        cmd_int = cmd_input if isinstance(cmd_input, int) else self.CMD_MAP.get(cmd_input, 0)
        delay_us = int(delay_sec * 1_000_000)
        prep_led_us = int(prep_led_sec * 1_000_000)
        target_mask = 0
        if not target_ids or 0 in target_ids:
            target_mask = 0xFFFFFFFFFFFFFFFF
        else:
            for pid in target_ids:
                if pid > 0: target_mask |= (1 << pid)
        
        t_start_pc = time.perf_counter()
        target_time = t_start_pc + delay_sec
        add_cmd_fail = 1
        
        for i in range(16):
            if self.cmd_list[i] < t_start_pc and i != self.idx:
                self.cmd_list[i] = target_time
                cmd_int = i * 16 + cmd_int
                packet = f"{cmd_int},{delay_us},{prep_led_us},{target_mask:x},{data[0]},{data[1]},{data[2]}\n"
                add_cmd_fail = 0
                self.idx = i
                break 
        
        logger.info(f"Sending: {packet.strip()}")
        if add_cmd_fail == 1:
            return self._format_response(-1, cmd_input, target_ids, self.idx, "Queue full")

        self.ser.write(packet.encode('utf-8'))
        
        success, msg = self._read_until_ack_or_timeout(expected_ack="ACK:OK", timeout=0.5)
        
        status = 0 if success else -1
        return self._format_response(status, cmd_input, target_ids, self.idx, msg)

    def trigger_check(self, target_ids=[]):
        if not self.ser or not self.ser.is_open:
            return self._format_response(-1, "CHECK", target_ids, -1, "Port not open")
            
        resp = self.send_burst(
                cmd_input='CHECK', 
                delay_sec=0.6, 
                prep_led_sec=0, 
                target_ids=target_ids, 
                data=[0, 0, 0]
            )
        if resp['statusCode'] != 0:
            return resp
        self.found_devices_buffer = []
        cmd_id = resp['payload']['command_id']
        return {
            "from": "Host_PC",
            "topic": "check_trigger",
            "statusCode": 0,
            "payload": {
                "target_id": str(target_ids),
                "command": "CHECK",
                "command_id": str(cmd_id),
                "message": f"Check started (ID: {cmd_id})"
            }
        }

    def get_latest_report(self):
        self._drain_serial()
        
        return {
            "from": "Host_PC",
            "topic": "check_report",
            "statusCode": 0,
            "payload": {
                "scan_duration_sec": 2,
                "found_count": len(self.found_devices_buffer),
                "found_devices": self.found_devices_buffer
            }
        }

    def _drain_serial(self):
        if self.ser and self.ser.is_open:
            while self.ser.in_waiting > 0:
                try:
                    line = self.ser.read_until(b'\n').decode('utf-8', errors='ignore').strip()
                    if line.startswith("FOUND:"):
                        self._parse_found_line(line)
                except:
                    break

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()