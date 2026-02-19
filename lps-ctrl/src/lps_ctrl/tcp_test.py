from tcp_sender import Esp32TcpServer

# 這裡可以換成任何你存放檔案的實際路徑
my_control_path = r"C:\Users\yingr\Lightdance2026\WIFI_to_SD\WIFI sender\control.dat"
my_frame_path = r"C:\Users\yingr\Lightdance2026\WIFI_to_SD\WIFI sender\frame.dat"

# 實例化伺服器，並把路徑傳進去
server = Esp32TcpServer(
    control_file_path=my_control_path,
    frame_file_path=my_frame_path,
    port=3333
)

print("準備啟動專案伺服器...")
server.start()