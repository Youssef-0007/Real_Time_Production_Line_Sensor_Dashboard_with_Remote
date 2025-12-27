import sys
import socket
import json
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QGridLayout,
                             QTableWidgetItem, QVBoxLayout, QWidget, QLabel)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor
import pyqtgraph as pg
from collections import deque

# --- THE WORKER: TCP RECEIVER ---
class TCPReceiver(QThread):
    # This is the "Mailbox" signal that carries the JSON dictionary
    data_received = pyqtSignal(dict)

    def run(self):
        host, port = '127.0.0.1', 5000
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((host, port))
                # makefile('r') handles the \n buffering for us automatically
                buffer = s.makefile('r')
                while True:
                    line = buffer.readline()
                    if line:
                        packet = json.loads(line)
                        self.data_received.emit(packet)
            except Exception as e:
                print(f"Connection Error: {e}")

# --- THE MAIN UI ---
class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Production Line Sensor Dashboard")
        self.resize(800, 600)

        # 1. Define Thresholds (Requirement 4)
        self.limits = {
            "temp1": {"low": 20, "high": 80},
            "optical": {"low": 1, "high": 100},
            "press": {"low": 12, "high": 45},
            "speed": {"low": 10, "high": 180},
            "vib":   {"low": 0.1, "high": 4.0}
        }

        # 2. Setup Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # 3. Global Status Indicator
        self.status_label = QLabel("SYSTEM STATUS: CONNECTING...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 18px; font-weight: bold; background-color: gray; color: white;")
        self.layout.addWidget(self.status_label)

        # 4. Sensor Table (Requirement 3)
        self.table = QTableWidget(5, 4) # 5 Sensors, 4 Columns
        self.table.setHorizontalHeaderLabels(["Sensor Name", "Value", "Timestamp", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.table)

        # Map sensor names to row index for easy lookup
        self.sensor_to_row = {
            "temp1": 0, "optical": 1, "press": 2, "speed": 3, "vib": 4
        }

        # 5. Alarm Log Table (Requirement 3)
        self.layout.addWidget(QLabel("ALARM LOG HISTORY")) # A simple title
        self.alarm_table = QTableWidget(0, 4) # Start with 0 rows
        self.alarm_table.setHorizontalHeaderLabels(["Time", "Sensor", "Value", "Alarm Type"])
        self.alarm_table.horizontalHeader().setStretchLastSection(True)
        self.layout.addWidget(self.alarm_table)

        # Dictionary to track previous state to avoid duplicate logs
        self.previous_state = { "temp1": "OK", "optical": "OK", "press": "OK", "speed": "OK", "vib": "OK" }

        # 6. Setup Plotting Area (Requirement 3)
        plot_container = QWidget()
        self.plot_layout = QGridLayout(plot_container) # Use a Grid for the 5 plots
        self.layout.addWidget(QLabel("REAL-TIME SENSOR TRENDS (ROLLING 20s)"))
        self.layout.addWidget(plot_container)

        self.plots = {}      # Stores the PlotWidget objects
        self.plot_data = {}  # Stores the deques (the actual numbers)
        self.curves = {}     # Stores the line objects

        # Create a plot for each sensor
        for i, name in enumerate(self.sensor_to_row.keys()):
            # Create the widget
            p_widget = pg.PlotWidget(title=name)
            p_widget.setBackground('k') # Black background
            p_widget.setLabel('left', 'Value')
            p_widget.showGrid(x=True, y=True)
            
            # Set fixed range or let it auto-scale
            p_widget.setYRange(self.limits[name]['low'] - 5, self.limits[name]['high'] + 5)
            
            # Add to grid: 2 columns
            self.plot_layout.addWidget(p_widget, i // 2, i % 2)
            
            # Initialize data storage (last 40 points = ~20 seconds at 2Hz)
            self.plots[name] = p_widget
            self.plot_data[name] = deque([0.0] * 40, maxlen=40)
            self.curves[name] = p_widget.plot(pen=pg.mkPen(color='g', width=2))
        
        # 5. Start TCP Receiver Thread
        self.receiver = TCPReceiver()
        self.receiver.data_received.connect(self.process_packet)
        self.receiver.start()
    
    def process_packet(self, packet):
        name = packet['sensor']
        val = packet['value']
        status = packet['status'] # Expected: "OK" or "Faulty Sensor"
        row = self.sensor_to_row.get(name)

        limit = self.limits.get(name)
        alarm_msg = ""
        
        # 1. Determine if THIS sensor has an alarm
        if status == "Faulty Sensor":
            alarm_msg = "Hardware Fault"
        elif val > limit['high']:
            alarm_msg = "High Limit Exceeded"
        elif val < limit['low']:
            alarm_msg = "Low Limit Exceeded"

        # 2. Log to Alarm Table only on NEW alarm
        if alarm_msg != "" and self.previous_state[name] == "OK":
            self.add_to_alarm_log(name, val, alarm_msg)
            self.previous_state[name] = "ALARM"
        elif alarm_msg == "":
            self.previous_state[name] = "OK"
            
        if row is not None:
            # Update Table Cells
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(str(val)))
            self.table.setItem(row, 2, QTableWidgetItem(packet['timestamp']))
            self.table.setItem(row, 3, QTableWidgetItem(status))

            # Color this specific row
            is_currently_alarmed = (alarm_msg != "")
            color = QColor("red") if is_currently_alarmed else QColor("green")
            for col in range(4):
                item = self.table.item(row, col)
                if not item: # Create item if it doesn't exist yet
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setBackground(color)
                item.setForeground(QColor("white"))

            # 3. GLOBAL STATUS CHECK (Requirement 3)
            # Scan all previous_states to see if ANY sensor is in ALARM
            if any(s == "ALARM" for s in self.previous_state.values()):
                self.status_label.setText("SYSTEM STATUS: CRITICAL ALARM")
                self.status_label.setStyleSheet("background-color: red; color: white; font-weight: bold;")
            else:
                self.status_label.setText("SYSTEM STATUS: ALL SYSTEMS OK")
                self.status_label.setStyleSheet("background-color: green; color: white; font-weight: bold;")

        # Update Plotting Data
        if name in self.plot_data:
            # Add new value to deque
            self.plot_data[name].append(val)
            
            # Update the line on the graph
            self.curves[name].setData(list(self.plot_data[name]))
            
            # Change curve color if in alarm state
            if name in self.previous_state and self.previous_state[name] == "ALARM":
                self.curves[name].setPen(pg.mkPen(color='r', width=2))
            else:
                self.curves[name].setPen(pg.mkPen(color='g', width=2))

    def add_to_alarm_log(self, name, val, alarm_type):
        # Insert at the very top (index 0) so newest is always visible
        self.alarm_table.insertRow(0)
        self.alarm_table.setItem(0, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.alarm_table.setItem(0, 1, QTableWidgetItem(name))
        self.alarm_table.setItem(0, 2, QTableWidgetItem(str(val)))
        
        # Style the alarm type cell
        type_item = QTableWidgetItem(alarm_type)
        type_item.setForeground(QColor("red"))
        self.alarm_table.setItem(0, 3, type_item)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorDashboard()
    window.show()
    sys.exit(app.exec())