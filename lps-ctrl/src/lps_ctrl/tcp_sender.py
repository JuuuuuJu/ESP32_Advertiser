import socket
import struct
import os
import time

class Esp32TcpServer:
    def __init__(self, control_file_path, frame_file_path, host='0.0.0.0', port=3333):
        """
        初始化 TCP 伺服器設定
        必須傳入 control_file_path 與 frame_file_path
        """
        self.host = host
        self.port = port
        self.control_file_path = control_file_path
        self.frame_file_path = frame_file_path
        self.server_socket = None

    def _get_file_data(self, filepath):
        """
        讀取檔案資料。若檔案或目錄不存在，則自動建立路徑與測試用的假檔案。
        """
        if not os.path.exists(filepath):
            print(f"錯誤: 找不到檔案 {filepath}")
            
            # 確保指定的資料夾路徑存在，若無則自動建立
            dir_name = os.path.dirname(filepath)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            # 建立假的測試檔案
            with open(filepath, 'wb') as f:
                filename = os.path.basename(filepath)
                f.write(b'This is a test data for ' + filename.encode())
            print(f"已自動建立測試檔案: {filepath}")
        
        with open(filepath, 'rb') as f:
            return f.read()

    def start(self):
        """
        啟動伺服器並開始監聽 ESP32 的連線請求
        """
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            print(f"========================================")
            print(f"TCP Server 啟動中...")
            print(f"監聽 Port: {self.port}")
            print(f"本機 IP (參考用): {local_ip}")
            print(f"Control 檔案路徑: {self.control_file_path}")
            print(f"Frame 檔案路徑: {self.frame_file_path}")
            print(f"========================================")

            while True:
                print("等待 ESP32 連線...")
                client_sock, addr = self.server_socket.accept()
                print(f"連線成功! 來自: {addr}")

                try:
                    # 1. 接收 Player ID
                    player_id_data = client_sock.recv(1024)
                    if not player_id_data:
                        print("未收到數據，斷開連線")
                        client_sock.close()
                        continue
                    
                    player_id = player_id_data.decode('utf-8').strip()
                    print(f"收到 Player ID: {player_id}")

                    # 準備要發送的檔案數據 (使用類別中儲存的路徑)
                    control_data = self._get_file_data(self.control_file_path)
                    frame_data = self._get_file_data(self.frame_file_path)

                    # 2. 發送 control 檔案
                    print(f"正在發送 Control 資料 ({len(control_data)} bytes)...")
                    size_header = struct.pack('>I', len(control_data))
                    client_sock.sendall(size_header)
                    client_sock.sendall(control_data)
                    
                    time.sleep(0.1)

                    # 3. 發送 frame 檔案
                    print(f"正在發送 Frame 資料 ({len(frame_data)} bytes)...")
                    size_header = struct.pack('>I', len(frame_data))
                    client_sock.sendall(size_header)
                    client_sock.sendall(frame_data)

                    print("發送完成，關閉連線")

                except Exception as e:
                    print(f"傳輸過程發生錯誤: {e}")
                
                finally:
                    client_sock.close()
                    print("----------------------------------------")

        except Exception as e:
            print(f"Server 啟動失敗: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()

    def stop(self):
        if self.server_socket:
            self.server_socket.close()
            print("伺服器已關閉")