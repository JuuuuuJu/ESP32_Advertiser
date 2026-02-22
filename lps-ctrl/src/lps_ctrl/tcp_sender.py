import asyncio
import struct
import os
import socket

class Esp32TcpServer:
    def __init__(self, control_paths_list, frame_paths_list, host='0.0.0.0', port=3333):
        """
        初始化非同步 TCP 伺服器設定。
        """
        self.host = host
        self.port = port
        self.control_paths_list = control_paths_list
        self.frame_paths_list = frame_paths_list
        self.server = None

    def _get_file_data(self, filepath):
        """
        讀取檔案資料。
        """
        if not os.path.exists(filepath):
            # 拋出異常，交給外層的 handle_client 處理
            raise FileNotFoundError(f"找不到檔案: {filepath}")
        
        with open(filepath, 'rb') as f:
            return f.read()

    async def handle_client(self, reader, writer):
        """
        處理每個 ESP32 連線的獨立非同步任務。
        """
        addr = writer.get_extra_info('peername')
        print(f"Connection successful! From: {addr}")

        try:
            # 1. 接收 Player ID
            player_id_data = await reader.read(1024)
            if not player_id_data:
                print("No data received, disconnecting.")
                return
            
            player_id_str = player_id_data.decode('utf-8').strip()
            print(f"Received Player ID: {player_id_str}")

            try:
                pid = int(player_id_str)
                idx = pid - 1
            except ValueError:
                print(f"Error: Invalid Player ID format '{player_id_str}'")
                return

            # 檢查 ID 是否超出陣列範圍
            if idx < 0 or idx >= len(self.control_paths_list) or idx >= len(self.frame_paths_list):
                print(f"Error: Player ID {pid} is out of bounds (Max: {len(self.control_paths_list)}).")
                return

            player_control_path = self.control_paths_list[idx]
            player_frame_path = self.frame_paths_list[idx]

            # --- 嘗試讀取檔案 ---
            try:
                control_data = self._get_file_data(player_control_path)
                frame_data = self._get_file_data(player_frame_path)
            except FileNotFoundError as e:
                # 發現檔案遺失，印出醒目錯誤並提早結束這個任務 (return)
                print(f"Incomplete data for Player {pid}: {e}")
                print(f"Disconnected Player {pid} to preserve existing SD card data.")
                return 

            # 2. 發送 control 檔案
            print(f"Sending Control data ({len(control_data)} bytes) to Player {pid}...")
            size_header = struct.pack('>I', len(control_data))
            writer.write(size_header)
            writer.write(control_data)
            await writer.drain() 
            
            await asyncio.sleep(0.1) 

            # 3. 發送 frame 檔案
            print(f"Sending Frame data ({len(frame_data)} bytes) to Player {pid}...")
            size_header = struct.pack('>I', len(frame_data))
            writer.write(size_header)
            writer.write(frame_data)
            await writer.drain()

            # 4. 等待 ESP32 回傳 ACK 確認
            print(f"Waiting for Player {pid} to save to SD card and send ACK...")
            try:
                ack_data = await asyncio.wait_for(reader.read(1024), timeout=15.0)
                if ack_data:
                    ack_msg = ack_data.decode('utf-8').strip()
                    if ack_msg == "DONE":
                        print(f"Player {pid} successfully received and saved all files!")
                    else:
                        print(f"Received unknown message from Player {pid}: {ack_msg}")
                else:
                    print(f"Connection closed early, Player {pid} did not send ACK.")
                    
            except asyncio.TimeoutError:
                print(f"ACK timeout! Player {pid} might have failed to save or disconnected.")

        except Exception as e:
            print(f"Error during transmission: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
            print("----------------------------------------")

    async def start(self):
        """
        啟動非同步伺服器
        """
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f"========================================")
        print(f"Async TCP Server Starting...")
        print(f"Listening on Port: {self.port}")
        print(f"Local IP (for reference): {local_ip}")
        print(f"Loaded {len(self.control_paths_list)} control paths and {len(self.frame_paths_list)} frame paths.")
        print(f"========================================")

        async with self.server:
            await self.server.serve_forever()