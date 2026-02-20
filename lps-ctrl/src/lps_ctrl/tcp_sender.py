import asyncio
import struct
import os
import socket
import time

class Esp32TcpServer:
    def __init__(self, control_file_path, frame_file_path, host='0.0.0.0', port=3333):
        """
        Initialize the Async TCP Server settings.
        Requires control_file_path and frame_file_path.
        """
        self.host = host
        self.port = port
        self.control_file_path = control_file_path
        self.frame_file_path = frame_file_path
        self.server = None

    def _get_file_data(self, filepath):
        """
        Read file data. If the file or directory doesn't exist, create it with dummy data.
        """
        if not os.path.exists(filepath):
            print(f"Error: File not found {filepath}")
            
            # Ensure the directory exists
            dir_name = os.path.dirname(filepath)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            # Create a fake test file
            with open(filepath, 'wb') as f:
                filename = os.path.basename(filepath)
                f.write(b'This is a test data for ' + filename.encode())
            print(f"Auto-created test file: {filepath}")
        
        with open(filepath, 'rb') as f:
            return f.read()

    async def handle_client(self, reader, writer):
        """
        This coroutine is spawned for every new ESP32 connection.
        """
        addr = writer.get_extra_info('peername')
        print(f"Connection successful! From: {addr}")

        try:
            # 1. Receive Player ID (async read)
            player_id_data = await reader.read(1024)
            if not player_id_data:
                print("No data received, disconnecting.")
                return
            
            player_id = player_id_data.decode('utf-8').strip()
            print(f"Received Player ID: {player_id}")

            # Prepare file data
            control_data = self._get_file_data(self.control_file_path)
            frame_data = self._get_file_data(self.frame_file_path)

            # 2. Send control file
            print(f"Sending Control data ({len(control_data)} bytes)...")
            size_header = struct.pack('>I', len(control_data))
            writer.write(size_header)
            writer.write(control_data)
            await writer.drain() # Yield control back to event loop until buffer is drained
            
            await asyncio.sleep(0.1) # Replaces time.sleep()

            # 3. Send frame file
            print(f"Sending Frame data ({len(frame_data)} bytes)...")
            size_header = struct.pack('>I', len(frame_data))
            writer.write(size_header)
            writer.write(frame_data)
            await writer.drain()

            # 4. 等待 Client 傳回完成訊息
            print(f"等待 Player {player_id} 回傳確認中...")
            try:
                # 如果 ESP32 成功回傳，就會立即收到；若超時則拋出異常
                ack_data = await asyncio.wait_for(reader.read(1024), timeout=100.0)
                
                if ack_data:
                    ack_msg = ack_data.decode('utf-8').strip()
                    if ack_msg == "DONE":
                        print(f"Player {player_id} saved files successfully.")
                    else:
                        print(f"Player {player_id} unknown message: {ack_msg}.")
                else:
                    print(f"No ACK from Player {player_id}")
                    
            except asyncio.TimeoutError:
                print(f"Player {player_id} ACK timeout.")
            # -------------------------

        except Exception as e:
            print(f"Error during transmission: {e}")
        
        finally:
            writer.close()
            await writer.wait_closed()
            print("----------------------------------------")

    async def start(self):
        """
        Start the server and begin listening for connections asynchronously.
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
        print(f"Control file path: {self.control_file_path}")
        print(f"Frame file path: {self.frame_file_path}")
        print(f"========================================")

        # Serve forever in the async event loop
        async with self.server:
            await self.server.serve_forever()