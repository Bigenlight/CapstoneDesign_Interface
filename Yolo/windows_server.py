import socket
import sys
import pickle
import struct
import numpy as np
import cv2
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QPushButton, QMessageBox
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QThread, pyqtSignal
from ultralytics import YOLO

class VideoReceiverThread(QThread):
    frame_received = pyqtSignal(np.ndarray)
    
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.running = True
        # Load the YOLOv8 model
        self.model = YOLO('yolov8n.pt')
    
    def run(self):
        data = b""
        payload_size = struct.calcsize("!I")
        while self.running:
            # Receive message size
            while len(data) < payload_size:
                packet = self.conn.recv(4 * 1024)  # 4KB
                if not packet:
                    self.running = False
                    break
                data += packet
            if not self.running:
                break
            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("!I", packed_msg_size)[0]
    
            # Receive frame data
            while len(data) < msg_size:
                packet = self.conn.recv(4 * 1024)
                if not packet:
                    self.running = False
                    break
                data += packet
            if not self.running:
                break
            frame_data = data[:msg_size]
            data = data[msg_size:]
    
            # Deserialize frame
            frame = pickle.loads(frame_data)
    
            # Process the frame with YOLOv8
            results = self.model(frame)
            annotated_frame = results[0].plot()
    
            # Emit signal to update GUI
            self.frame_received.emit(annotated_frame)
    
    def stop(self):
        self.running = False
        self.conn.close()
        self.wait()

class VideoStreamWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('YOLOv8 Video Stream')
        self.image_label = QLabel()
        self.image_label.setScaledContents(True)
        layout = QVBoxLayout()
        layout.addWidget(self.image_label)
        self.setLayout(layout)
    
    def update_frame(self, frame):
        # Convert the frame to QImage
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        qimg = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qimg))

def main():
    # Set up server
    server_ip = '0.0.0.0'  # Listen on all interfaces
    server_port = 8000

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((server_ip, server_port))
    server_socket.listen(1)
    print(f"Server listening on {server_ip}:{server_port}")

    conn, addr = server_socket.accept()
    print(f"Connection from: {addr}")

    app = QApplication(sys.argv)
    window = VideoStreamWindow()
    window.show()

    # Start the video receiver thread
    receiver_thread = VideoReceiverThread(conn)
    receiver_thread.frame_received.connect(window.update_frame)
    receiver_thread.start()

    # Execute the app
    try:
        sys.exit(app.exec_())
    finally:
        receiver_thread.stop()
        server_socket.close()

if __name__ == '__main__':
    main()
