import asyncio
from tcp_sender import Esp32TcpServer

async def main():
    # Use your actual paths
    my_control_path = r"C:\Users\yingr\Lightdance2026\WIFI_to_SD\WIFI sender\control.dat"
    my_frame_path = r"C:\Users\yingr\Lightdance2026\WIFI_to_SD\WIFI sender\frame.dat"

    # Instantiate the server
    server = Esp32TcpServer(
        control_file_path=my_control_path,
        frame_file_path=my_frame_path,
        port=3333
    )

    print("Preparing to start the async tcp server...")
    # 'await' the start method to keep the server running
    await server.start()

if __name__ == '__main__':
    try:
        # asyncio.run() handles starting and stopping the event loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer manually stopped.")