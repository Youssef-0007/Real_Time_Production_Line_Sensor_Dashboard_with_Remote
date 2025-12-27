import sys
import socket
import json
import time
from collections import deque
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QGridLayout,
                             QTableWidgetItem, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QTabWidget, QSplitter, QHeaderView)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg

# --- THE WORKER: TCP RECEIVER ---
class TCPReceiver(QThread):
    data_received = pyqtSignal(dict)

    def run(self):
        host, port = '127.0.0.1', 5000
        while True: # Retry loop
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((host, port))
                    buffer = s.makefile('r')
                    while True:
                        line = buffer.readline()
                        if not line: break
                        packet = json.loads(line)
                        self.data_received.emit(packet)
            except Exception as e:
                print(f"Connection lost/failed: {e}. Retrying in 2s...")
                time.sleep(2)

# --- THE MAIN UI ---
class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Industrial Sensor Suite - SCADA Interface")
        self.resize(1100, 850)

        # 1. Configuration & Thresholds
        self.limits = {
            "temp1": {"low": 20, "high": 80},
            "temp2": {"low": 20, "high": 80},
            "press": {"low": 12, "high": 45},
            "speed": {"low": 10, "high": 180},
            "vib":   {"low": 0.1, "high": 4.0},
            "optical": {"low": 98, "high": 102}
        }
        self.sensor_to_row = {name: i for i, name in enumerate(self.limits.keys())}
        self.previous_state = {name: "OK" for name in self.limits.keys()}

        self.setup_ui()
        self.apply_styles()

        # Start Networking
        self.receiver = TCPReceiver()
        self.receiver.data_received.connect(self.process_packet)
        self.receiver.start()

    def setup_ui(self):
        # Main Container
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # --- TAB 1: LIVE DASHBOARD ---
        self.dash_tab = QWidget()
        self.dash_layout = QVBoxLayout(self.dash_tab)

        # Global Status
        self.status_label = QLabel("SYSTEM STATUS: CONNECTING...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dash_layout.addWidget(self.status_label)

        # Splitter for Table and Graphs
        self.splitter = QSplitter(Qt.Orientation.Vertical)

        # Sensor Table
        self.table = QTableWidget(len(self.limits), 4)
        self.table.setHorizontalHeaderLabels(["Sensor Name", "Value", "Timestamp", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.splitter.addWidget(self.table)

        # Plotting Area
        self.plot_container = QWidget()
        self.plot_grid = QGridLayout(self.plot_container)
        self.plots = {}
        self.plot_data = {}
        self.curves = {}

        for i, name in enumerate(self.limits.keys()):
            p_widget = pg.PlotWidget(title=f"{name.upper()} Real-Time Trend")
            p_widget.setLabel('left', 'Value')
            p_widget.showGrid(x=True, y=True)
            
            # Fix Scaling for Optical or apply limits
            if name == "optical":
                p_widget.setYRange(95, 105)
            else:
                p_widget.setYRange(self.limits[name]['low'] - 10, self.limits[name]['high'] + 10)

            self.plot_grid.addWidget(p_widget, i // 2, i % 2)
            self.plots[name] = p_widget
            self.plot_data[name] = deque([0.0] * 40, maxlen=40)
            self.curves[name] = p_widget.plot(pen=pg.mkPen(color='g', width=2))

        self.splitter.addWidget(self.plot_container)
        self.dash_layout.addWidget(self.splitter)

        # --- TAB 2: ALARM HISTORY ---
        self.alarm_tab = QWidget()
        self.alarm_layout = QVBoxLayout(self.alarm_tab)
        
        self.alarm_table = QTableWidget(0, 4)
        self.alarm_table.setHorizontalHeaderLabels(["Time", "Sensor", "Value", "Alarm Type"])
        self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.alarm_table.verticalHeader().setVisible(False)
        
        self.alarm_layout.addWidget(QLabel("HISTORICAL FAULT LOG"))
        self.alarm_layout.addWidget(self.alarm_table)

        # Add tabs
        self.tabs.addTab(self.dash_tab, "Live Dashboard")
        self.tabs.addTab(self.alarm_tab, "Alarm History")

    def process_packet(self, packet):
        name = packet['sensor']
        val = packet['value']
        status = packet['status']
        row = self.sensor_to_row.get(name)
        if row is None: return

        # 1. Alarm Analysis
        limit = self.limits.get(name)
        alarm_msg = ""
        if status == "Faulty Sensor":
            alarm_msg = "Hardware Fault"
        elif val > limit['high']:
            alarm_msg = "High Limit Exceeded"
        elif val < limit['low']:
            alarm_msg = "Low Limit Exceeded"

        # 2. Trigger Alarm Log
        if alarm_msg != "" and self.previous_state[name] == "OK":
            self.add_to_alarm_log(name, val, alarm_msg)
            self.previous_state[name] = "ALARM"
        elif alarm_msg == "":
            self.previous_state[name] = "OK"

        # 3. Update Table
        data = [name, str(val), time.strftime("%H:%M:%S", time.localtime(packet['timestamp'])), status]
        color = QColor("#e74c3c") if alarm_msg else QColor("#2ecc71") # Soft red/green

        for col, text in enumerate(data):
            item = self.table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(text)
            item.setBackground(color)
            item.setForeground(QColor("white"))

        # 4. Update Plots
        self.plot_data[name].append(val)
        self.curves[name].setData(list(self.plot_data[name]))
        self.curves[name].setPen(pg.mkPen(color=('r' if alarm_msg else 'g'), width=2))

        # 5. Global Status
        if any(s == "ALARM" for s in self.previous_state.values()):
            self.status_label.setText("!!! SYSTEM CRITICAL - ALARMS ACTIVE !!!")
            self.status_label.setStyleSheet("background-color: #c0392b; color: white; padding: 10px; font-weight: bold; font-size: 20px;")
        else:
            self.status_label.setText("SYSTEM NOMINAL")
            self.status_label.setStyleSheet("background-color: #27ae60; color: white; padding: 10px; font-weight: bold; font-size: 20px;")

    def add_to_alarm_log(self, name, val, alarm_type):
        self.alarm_table.insertRow(0)
        self.alarm_table.setItem(0, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.alarm_table.setItem(0, 1, QTableWidgetItem(name))
        self.alarm_table.setItem(0, 2, QTableWidgetItem(str(val)))
        
        type_item = QTableWidgetItem(alarm_type)
        type_item.setForeground(QColor("#e74c3c"))
        self.alarm_table.setItem(0, 3, type_item)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2c3e50; }
            QTabWidget::pane { border: 1px solid #34495e; }
            QTabBar::tab {
                background: #34495e; color: #ecf0f1; padding: 12px 30px; 
                font-weight: bold; border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #2980b9; border-bottom: 2px solid #3498db; }
            QTableWidget { 
                background-color: #34495e; color: #ecf0f1; 
                gridline-color: #2c3e50; font-size: 13px;
            }
            QHeaderView::section {
                background-color: #1a252f; color: white; padding: 5px; border: 1px solid #2c3e50;
            }
            QLabel { color: #ecf0f1; font-weight: bold; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = SensorDashboard()
    window.show()
    sys.exit(app.exec())