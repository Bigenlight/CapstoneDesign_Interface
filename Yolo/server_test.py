# server_test.py
import socket

server_ip = '0.0.0.0'
server_port = 8000

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((server_ip, server_port))
server_socket.listen(1)
print(f"Server listening on {server_ip}:{server_port}")

try:
    conn, addr = server_socket.accept()
    print(f"Connection from: {addr}")
except KeyboardInterrupt:
    print("Server shutting down.")
finally:
    server_socket.close()
