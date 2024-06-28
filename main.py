import time
from PyQt5 import uic, QtCore, QtWidgets, QtWebEngineWidgets  # pip install pyqtwebengine
from folium.plugins import Draw, MousePosition
import folium, io, sys, json
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QMainWindow, QLabel
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import serial
from folium.plugins import MarkerCluster
import numpy as np
from jinja2 import Template
import paho.mqtt.client as mqtt

######## MQTT
# Define the MQTT broker address and port
# iceslab_5g
#broker_address = "192.168.0.12" 
# 핫스팟
#broker_address = "192.168.151.154"
# 노트북 핫스팟
broker_address = "192.168.137.1" 

port = 1883  # Default MQTT port

# Define the topics
topic = "test/topic"
# 모터 상태 토픽
motor_state_topic = "motor_state"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to broker")
        client.subscribe("gps_location_topic")
    else:
        print("Connection failed with code", rc)

def on_message(client, userdata, msg):
    try:
        coords_str = msg.payload.decode()
        lat, lng = map(float, coords_str.strip('()').split(', '))
        # Use Qt's signal-slot mechanism to update the UI thread safely
        window.mqtt_message_received.emit(lat, lng, coords_str)
    except Exception as e:
        print(f"Error processing message: {e}")

client = mqtt.Client("WindowsPublisher")
client.on_connect = on_connect
client.on_message = on_message

form_class = uic.loadUiType("V1_UI.ui")[0]
app = QtWidgets.QApplication(sys.argv)

###### 여기 부터 인터페이스 코드
class WebEnginePage(QtWebEngineWidgets.QWebEnginePage):
    def __init__(self, parent=None):
        super(WebEnginePage, self).__init__(parent)
        self.window = parent

    def javaScriptAlert(self, securityOrigin: QtCore.QUrl, msg: str):
        coords_dict = json.loads(msg)
        coords = coords_dict['geometry']['coordinates']
        print(coords)
        
        # Write coordinates to file
        with open('stdout.txt', 'w') as f:
            f.write(str(coords))

        # Add coordinates to the list view
        self.window.add_coordinates_to_list(coords)

##### Qt widget Layout
class WindowClass(QMainWindow, form_class):
    mqtt_message_received = QtCore.pyqtSignal(float, float, str)

    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.view = QtWebEngineWidgets.QWebEngineView()
        self.view.setContentsMargins(50, 50, 50, 50)

        self.Folium.addWidget(self.view, stretch=1)

        self.m = folium.Map(
            location=[37.631104100930436, 127.0779647879758], zoom_start=13
        )

        folium.raster_layers.TileLayer(
            tiles="http://mt1.google.com/vt/lyrs=m&h1=p1Z&x={x}&y={y}&z={z}",
            name="Standard Roadmap",
            attr="Google Map",
        ).add_to(self.m)
        folium.raster_layers.TileLayer(
            tiles="http://mt1.google.com/vt/lyrs=s&h1=p1Z&x={x}&y={y}&z={z}",
            name="Satellite Only",
            attr="Google Map",
        ).add_to(self.m)
        folium.raster_layers.TileLayer(
            tiles="http://mt1.google.com/vt/lyrs=y&h1=p1Z&x={x}&y={y}&z={z}",
            name="Hybrid",
            attr="Google Map",
        ).add_to(self.m)

        folium.LayerControl().add_to(self.m)
        folium.Marker((37.631104100930436, 127.0779647879758)).add_to(self.m)

        draw = Draw(
            draw_options={
                'polyline': False,
                'rectangle': False,
                'polygon': False,
                'circle': False,
                'marker': True,
                'circlemarker': False},
            edit_options={'edit': False})
        self.m.add_child(draw)

        formatter = "function(num) {return L.Util.formatNum(num, 3) + ' º ';};"
        MousePosition(
            position="topright",
            separator=" | ",
            empty_string="NaN",
            lng_first=True,
            num_digits=20,
            prefix="Coordinates:",
            lat_formatter=formatter,
            lng_formatter=formatter,
        ).add_to(self.m)

        self.data = io.BytesIO()
        self.m.save(self.data, close_file=False)

        self.page = WebEnginePage(self)
        self.view.setPage(self.page)
        self.view.setHtml(self.data.getvalue().decode())

        # Create a model for the list view
        self.listViewModel = QStandardItemModel(self.listView)
        self.listView.setModel(self.listViewModel)

        # Create a model for the second list view
        self.listViewModel2 = QStandardItemModel(self.listView_2)
        self.listView_2.setModel(self.listViewModel2)

        # List to store received coordinates
        self.received_coordinates = []

        # 버튼과 함수 연결
        self.pushButton_2.clicked.connect(self.clear_coordinates_list) # 리스트 초기화
        self.pushButton_1.clicked.connect(self.draw_line_between_coordinates) # 경로 생성
        self.pushButton_3.clicked.connect(self.send_coordinates_over_serial) # 경로 전송
        self.pushButton.clicked.connect(self.send_motor_state) # 가동
        self.pushButton_4.clicked.connect(self.send_motor_state_stop) # 중지

        # Set up a timer to poll the serial port
        self.timer = QTimer()
        self.timer.start(1000)  # Poll every second

        # Connect the custom signal to the slot for handling MQTT messages
        self.mqtt_message_received.connect(self.handle_mqtt_message)

        # Start the MQTT client after initialization
        QTimer.singleShot(2000, self.start_mqtt_client)

    def start_mqtt_client(self):
        client.connect(broker_address, port)
        client.loop_start()

    def closeEvent(self, event):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
        event.accept()

    def GetPosition(self, latitude=37, longitude=127):
        js = Template(
            """
        L.marker([{{latitude}}, {{longitude}}] )
            .addTo({{map}});
        L.circleMarker(
            [{{latitude}}, {{longitude}}], {
                "bubblingMouseEvents": true,
                "color": "#3388ff",
                "dashArray": null,
                "dashOffset": null,
                "fill": false,
                "fillColor": "#3388ff",
                "fillOpacity": 0.2,
                "fillRule": "evenodd",
                "lineCap": "round",
                "lineJoin": "round",
                "opacity": 1.0,
                "radius": 2,
                "stroke": true,
                "weight": 5
            }
        ).addTo({{map}});
        """
        ).render(map=self.m.get_name(), latitude=latitude, longitude=longitude)
        self.view.page().runJavaScript(js)

    def add_coordinates_to_list(self, coords):
        item = QStandardItem(f"Longitude: {coords[0]}, Latitude: {coords[1]}")
        self.listViewModel.appendRow(item)

    def add_received_message_to_list(self, message):
        item = QStandardItem(message)
        self.listViewModel2.appendRow(item)

    def clear_coordinates_list(self):
        self.listViewModel.clear()
        self.clear_map_lines()

    def get_coordinates_from_list(self):
        coordinates = []
        for row in range(self.listViewModel.rowCount()):
            item = self.listViewModel.item(row)
            text = item.text()
            # Extract coordinates from the text
            lng, lat = map(float, text.replace("Longitude: ", "").replace("Latitude: ", "").split(", "))
            coordinates.append([lat, lng])
        return coordinates

    def draw_line_between_coordinates(self):
        coordinates = self.get_coordinates_from_list()
        if len(coordinates) < 2:
            return

        # Create a polyline on the map
        js = Template(
            """
        L.polyline({{coordinates}}, {color: 'green'}).addTo({{map}});
        """
        ).render(map=self.m.get_name(), coordinates=json.dumps(coordinates))
        self.view.page().runJavaScript(js)

    def clear_map_lines(self):
        # JavaScript to clear all layers added by draw_line_between_coordinates
        js = Template(
            """
        {{map}}.eachLayer(function (layer) {
            if (layer instanceof L.Polyline) {
                {{map}}.removeLayer(layer);
            }
        });
        """
        ).render(map=self.m.get_name())
        self.view.page().runJavaScript(js)

    def send_coordinates_over_serial(self):
        coordinates = self.get_coordinates_from_list()
        if not coordinates:
            return

        # Convert coordinates to a string with order numbers
        coord_str = "; ".join([f"({lat}, {lng}, {idx})" for idx, (lat, lng) in enumerate(coordinates)])
        
        # Add start and end
        coord_str = f"start; {coord_str}; end;"

        # Send coordinates via MQTT
        client.publish(topic, coord_str, qos=1)
        print(f"Published: {coord_str}")

        # Add a slight delay
        time.sleep(1)

    def update_map_with_line(self):
        # Create a polyline on the map with received coordinates
        js = Template(
            """
        console.log("Drawing line with coordinates: {{coordinates}}");
        L.polyline({{coordinates}}, {color: 'red'}).addTo({{map}});
        """
        ).render(map=self.m.get_name(), coordinates=json.dumps(self.received_coordinates))
        self.view.page().runJavaScript(js)

    def handle_mqtt_message(self, lat, lng, coords_str):
        self.received_coordinates.append([lat, lng])
        self.update_map_with_line()
        self.add_received_message_to_list(coords_str)

    def send_motor_state(self):
        client.publish(motor_state_topic, "start", qos=1)
        print("Published: 'on' to motor_state")
    def send_motor_state_stop(self):
        client.publish(motor_state_topic, "stop", qos=1)
        print("Published: 'stop' to motor_state")

# Instantiate the WindowClass globally so it can be accessed in on_message
window = WindowClass()
window.show()

sys.exit(app.exec_())
