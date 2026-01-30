import serial
import time
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
cmd_list = [0]*16
idx=-1
class ESP32BTSender:
    CMD_MAP = { "PLAY": 0x01, "PAUSE": 0x02,"RESET": 0x03, "RELEASE": 0x04,  "LOAD": 0x05,"TEST": 0x06,  "CANCEL": 0x07 }

    def __init__(self, port, baud_rate=921600, timeout=10):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.ser = None

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
            "from": "Host_PC", # or "RPi"?
            "topic": "command",
            "statusCode": status_code,
            "payload": {
                "target_id": str(target_ids), # I don't know what to put in "MAC" 
                "command": str(cmd),
                "command_id": str(cmd_id),
                "message": message
            }
        }
    
    def send_burst(self, cmd_input, delay_sec, prep_led_sec, target_ids, data):
        global idx, cmd_list
        error_response = self._format_response(-1, cmd_input, target_ids, -1, "Port not open or initialization failed")
        if not self.ser or not self.ser.is_open:
            return error_response

        cmd_int = cmd_input if isinstance(cmd_input, int) else self.CMD_MAP.get(cmd_input, 0)
        delay_us = int(delay_sec * 1_000_000)
        prep_led_us = int(prep_led_sec * 1_000_000)
        target_mask = 0
        for pid in target_ids:
            target_mask |= (1 << pid)
        
        packet=""
        t_start_pc = time.perf_counter()
        target_time = t_start_pc + delay_sec
        add_cmd_fail = 1
        
        for i in range(16):
            if cmd_list[i] < t_start_pc and i != idx:
                cmd_list[i] = target_time
                cmd_int = i * 16 + cmd_int
                packet = f"{cmd_int},{delay_us},{prep_led_us},{target_mask:x},{data[0]},{data[1]},{data[2]}\n"
                add_cmd_fail = 0
                idx = i
                break 
        logger.info(f"Sending: {packet.strip()}")
        if add_cmd_fail == 1:
            msg = "Add command FAIL due to full pending number"
            print(f"{msg}\n")
            return self._format_response(-1, cmd_input, target_ids, idx, msg)
        last_error_msg = "Unknown Error"
        self.ser.reset_input_buffer()          
        try:
            self.ser.write(packet.encode('utf-8'))
            raw_response = self.ser.read_until(b'\n')
            line = raw_response.decode('utf-8', errors='ignore').strip()
            if "ACK:OK" in line:
                return self._format_response(0, cmd_input, target_ids, idx, "Success")
            elif "NAK" in line:
                last_error_msg = f"Device rejected: {line}"
                logger.warning(last_error_msg)
            else:
                if not line:
                    last_error_msg = "Timeout: No ACK received"
                    logger.warning(last_error_msg)
                else:
                    last_error_msg = f"Unexpected response: {line}"
                    logger.warning(last_error_msg)
        except Exception as e:
            last_error_msg = f"Exception: {str(e)}"
            logger.error(last_error_msg)

        logger.error("Failed to send command.")
        return self._format_response(-1, cmd_input, target_ids, idx, last_error_msg)
    def check_status(self):
        if not self.ser or not self.ser.is_open:
            return {"statusCode": -1, "message": "Port not open"}

        logger.info("Sending CHECK command...")
        self.ser.reset_input_buffer()
        self.ser.write(b"CHECK\n")
        try:
            ack = self.ser.read_until(b'\n').decode().strip()
            if "ACK:CHECK_START" not in ack:
                logger.warning(f"Did not receive CHECK ACK. Got: {ack}")
        except Exception as e:
            logger.error(f"Error reading start ack: {e}")
        found_packets = []
        start_time = time.time()
        
        while (time.time() - start_time) < 4.0:
            line_bytes = self.ser.read_until(b'\n')
            if not line_bytes:
                continue
            
            line = line_bytes.decode(errors='ignore').strip()
            
            if line == "CHECK_DONE":
                # logger.info("Get CHECK_DONE\n")
                break
                
            if line.startswith("FOUND:"):
                parts = line.replace("FOUND:", "").split(',')
                if len(parts) >= 4:
                    packet = {
                        "target_id": int(parts[0]),
                        "cmd_id": int(parts[1]),
                        "cmd_type": int(parts[2]),
                        "target_delay": int(parts[3])
                    }
                    if packet not in found_packets:
                        found_packets.append(packet)
        return {
            "from": "Host_PC",
            "topic": "check_report",
            "statusCode": 0,
            "payload": {
                "scan_duration_sec": 2,
                "found_devices": found_packets
            }
        }
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()