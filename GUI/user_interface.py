import sys
import socket
import json
import time
from collections import deque
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QGridLayout,
                             QTableWidgetItem, QVBoxLayout, QHBoxLayout, 
                             QWidget, QLabel, QTabWidget, QHeaderView, QPushButton, 
                             QGroupBox, QLineEdit, QPlainTextEdit, QSplitter)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont
import pyqtgraph as pg

import TCP_Manager

class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Industrial Monitoring System v2.0")
        self.resize(1100, 900)

        self.limits = {
            "temp": {"low": 20, "high": 80},
            "press": {"low": 12, "high": 45},
            "speed": {"low": 10, "high": 180},
            "vib":   {"low": 0.1, "high": 4.0},
            "optical": {"low": 1, "high": 102}
        }
        self.sensor_to_row = {name: i for i, name in enumerate(self.limits.keys())}
        self.previous_state = {name: "OK" for name in self.limits.keys()}

        self.setup_ui()
        self.apply_styles()

        self.receiver = TCP_Manager.TCPManager()
        self.receiver.data_received.connect(self.process_packet)
        self.receiver.log_signal.connect(self.update_maintenance_log)
        self.receiver.start()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        outer_layout = QVBoxLayout(central_widget)

        # 1. Global Status Indicator (TOP)
        self.status_label = QLabel("SYSTEM STATUS: INITIALIZING...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(50)
        outer_layout.addWidget(self.status_label)

        # 2. Main Splitter (Separates Top Tabs from Bottom Terminal)
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_layout.addWidget(self.main_splitter)

        # --- TOP SECTION: TABS ---
        self.tabs = QTabWidget()
        self.main_splitter.addWidget(self.tabs)

        # Tab 1: Live Status
        self.table_tab = QWidget()
        table_layout = QVBoxLayout(self.table_tab)
        self.table = QTableWidget(len(self.limits), 5) 
        self.table.setHorizontalHeaderLabels(["Sensor", "Value", "Timestamp", "HW Status", "Process Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        table_layout.addWidget(self.table)
        self.tabs.addTab(self.table_tab, "Live Status")

        # Tab 2: Plots
        self.plot_tab = QWidget()
        self.plot_grid = QGridLayout(self.plot_tab)
        self.plots, self.plot_data, self.curves = {}, {}, {}
        for i, name in enumerate(self.limits.keys()):
            p_widget = pg.PlotWidget(title=f"{name.upper()} Trend")
            if name == "optical": p_widget.setYRange(90, 110)
            else: p_widget.setYRange(self.limits[name]['low'] - 10, self.limits[name]['high'] + 10)
            self.plot_grid.addWidget(p_widget, i // 2, i % 2)
            self.plots[name] = p_widget
            self.plot_data[name] = deque([0.0] * 40, maxlen=40)
            self.curves[name] = p_widget.plot(pen=pg.mkPen(color='g', width=2))
        self.tabs.addTab(self.plot_tab, "Real-Time Plots")

        # Tab 3: Alarms
        self.alarm_tab = QWidget()
        alarm_layout = QVBoxLayout(self.alarm_tab)
        self.alarm_table = QTableWidget(0, 4)
        self.alarm_table.setHorizontalHeaderLabels(["Time", "Sensor", "Value", "Alarm Type"])
        self.alarm_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        alarm_layout.addWidget(self.alarm_table)
        self.tabs.addTab(self.alarm_tab, "Alarm History")

        # --- BOTTOM SECTION: MAINTENANCE CONSOLE (VS Code Terminal Style) ---
        self.console_panel = QWidget()
        console_layout = QVBoxLayout(self.console_panel)
        
        # Access Control / Console Area
        self.login_group = QGroupBox("Engineer Login Required")
        login_h = QHBoxLayout(self.login_group)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_login = QPushButton("Unlock Console")
        self.btn_login.clicked.connect(self.check_password)
        login_h.addWidget(self.password_input)
        login_h.addWidget(self.btn_login)
        console_layout.addWidget(self.login_group)

        self.console_content = QWidget()
        self.console_content.setVisible(False)
        content_layout = QVBoxLayout(self.console_content)
        
        # Terminal Log
        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        self.live_log.setStyleSheet("background-color: #000; color: #0f0; font-family: Consolas, monospace;")
        content_layout.addWidget(QLabel("TERMINAL / SYSTEM LOGS"))
        content_layout.addWidget(self.live_log)

        # Console Commands
        cmd_h = QHBoxLayout()
        self.btn_restart = QPushButton("Restart Simulator")
        self.btn_test = QPushButton("Clear Alarms")
        self.btn_snap = QPushButton("Value Snapshot")
        cmd_h.addWidget(self.btn_restart)
        cmd_h.addWidget(self.btn_test)
        cmd_h.addWidget(self.btn_snap)
        content_layout.addLayout(cmd_h)
        
        console_layout.addWidget(self.console_content)
        self.main_splitter.addWidget(self.console_panel)
        self.main_splitter.setSizes([600, 300]) # Initial ratio

        # 3. Fixed Bottom Bar (Buttons)
        self.bottom_bar = QHBoxLayout()
        outer_layout.addLayout(self.bottom_bar)
        self.btn_export = QPushButton("Export Logs (CSV)")
        self.btn_clear = QPushButton("Clear Alarm Table")
        self.btn_stop = QPushButton("Emergency Stop")
        self.btn_stop.setStyleSheet("background-color: #7f0000; font-weight: bold;")
        self.bottom_bar.addWidget(self.btn_export)
        self.bottom_bar.addWidget(self.btn_clear)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(self.btn_stop)

        # Connections
        self.btn_test.clicked.connect(self.clear_alarm_log) # Using the 'Clear Alarms' button
        self.btn_snap.clicked.connect(self.take_snapshot)
        self.btn_clear.clicked.connect(self.clear_alarm_log) # Also the bottom bar button

    def process_packet(self, packet):
        name = packet['sensor']
        val, hw_status = packet['value'], packet['status']
        row = self.sensor_to_row.get(name)
        if row is None: return

        # 1. Update Plot
        self.plot_data[name].append(val)
        self.curves[name].setData(list(self.plot_data[name]))

        # 2. Determine Process Alarm
        limit = self.limits.get(name)
        process_status = "OK"
        if val > limit['high']: process_status = "High Limit"
        elif val < limit['low']: process_status = "Low Limit"

        # 3. Define Alarm State for Logging
        # We create a simple 'Is this sensor in trouble?' flag
        is_currently_alarmed = (hw_status == "FAULTY" or process_status != "OK")

        # 4. Trigger Alarm Log (Only on NEW alarm)
        if is_currently_alarmed and self.previous_state[name] == "OK":
            # Decide what text to show in the Alarm History tab
            log_msg = f"HW: {hw_status} | PROC: {process_status}"
            self.add_to_alarm_log(name, val, log_msg)
            self.previous_state[name] = "ALARM"
        
        # Reset state only if EVERYTHING is back to OK
        elif not is_currently_alarmed:
            self.previous_state[name] = "OK"

        # 5. UI Color Logic (HW Fault=Yellow, Process=Red, OK=Green)
        row_color = QColor("#27ae60") 
        line_color = 'g'
        if hw_status == "FAULTY":
            row_color = QColor("#f1c40f") # Yellow
            line_color = 'y'
        elif process_status != "OK":
            row_color = QColor("#c0392b") # Red
            line_color = 'r'

        # 6. Update Table Rows
        ts = time.strftime("%H:%M:%S", time.localtime(packet['timestamp']))
        data = [name, str(val), ts, hw_status, process_status]
        for col, text in enumerate(data):
            item = self.table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(text)
            item.setBackground(row_color)
            item.setForeground(QColor("black") if hw_status == "FAULTY" else QColor("white"))
        
        self.curves[name].setPen(pg.mkPen(color=line_color, width=2))
        self.update_system_status()


    def add_to_alarm_log(self, name, val, alarm_type):
        """Adds a new row to the Alarm History tab"""
        self.alarm_table.insertRow(0) # Always add at the top
        self.alarm_table.setItem(0, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.alarm_table.setItem(0, 1, QTableWidgetItem(name))
        self.alarm_table.setItem(0, 2, QTableWidgetItem(str(val)))
        self.alarm_table.setItem(0, 3, QTableWidgetItem(alarm_type))
        
        # Optional: Make the text red in the history log for visibility
        for i in range(4):
            self.alarm_table.item(0, i).setForeground(QColor("#e74c3c"))
            
        # Log to Maintenance Console as well
        self.update_maintenance_log(f"ALARM TRIGGERED: {name} - {alarm_type}")


    def update_system_status(self):
        # Scan table for worst-case scenario
        worst_case = "OK"
        for r in range(self.table.rowCount()):
            hw = self.table.item(r, 3).text() if self.table.item(r, 3) else "OK"
            proc = self.table.item(r, 4).text() if self.table.item(r, 4) else "OK"
            
            if proc != "OK": worst_case = "PROCESS" # Red
            if hw == "FAULTY": 
                worst_case = "HARDWARE" # Yellow
                break # Hardware fault takes global priority

        if worst_case == "HARDWARE":
            self.status_label.setText("!!! HARDWARE FAULT DETECTED (YELLOW) !!!")
            self.status_label.setStyleSheet("background-color: #f1c40f; color: black; font-weight: bold; font-size: 18px;")
        elif worst_case == "PROCESS":
            self.status_label.setText("!!! PROCESS ALARM: LIMITS EXCEEDED (RED) !!!")
            self.status_label.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 18px;")
        else:
            self.status_label.setText("SYSTEM OPERATIONAL (GREEN)")
            self.status_label.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 18px;")

    def check_password(self):
        if self.password_input.text() == "admin123":
            self.login_group.setVisible(False)
            self.console_content.setVisible(True)
            self.update_maintenance_log("Engineer Authenticated.")
        else:
            self.update_maintenance_log("Auth Failed.")

    def update_maintenance_log(self, text):
        self.live_log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")
        self.live_log.verticalScrollBar().setValue(self.live_log.verticalScrollBar().maximum())

    def clear_alarm_log(self):
        self.alarm_table.setRowCount(0)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QTabWidget::pane { border: 1px solid #333; }
            QTabBar::tab { background: #222; color: #aaa; padding: 10px; }
            QTabBar::tab:selected { background: #005a9e; color: white; }
            QPushButton { background-color: #333; color: white; border: 1px solid #555; padding: 6px; }
            QTableWidget { background-color: #1e1e1e; color: white; }
            QGroupBox { color: #888; border: 1px solid #333; margin-top: 10px; }
        """)

    def clear_alarm_log(self):
        """Action for 'Clear Alarms' button"""
        count = self.alarm_table.rowCount()
        self.alarm_table.setRowCount(0)
        # Log the action in the terminal for the engineer
        self.update_maintenance_log(f"USER ACTION: Alarm History Purged ({count} records cleared).")

    def take_snapshot(self):
        """Action for 'Value Snapshot' button"""
        self.update_maintenance_log("-" * 40)
        self.update_maintenance_log("SYSTEM SNAPSHOT REPORT")
        self.update_maintenance_log(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.update_maintenance_log("-" * 40)
        
        # Format a header for our snapshot
        header = f"{'SENSOR':<10} | {'VALUE':<8} | {'HW':<8} | {'PROCESS'}"
        self.update_maintenance_log(header)
        self.update_maintenance_log("-" * 40)

        # Loop through the main table rows to get current data
        for r in range(self.table.rowCount()):
            try:
                name = self.table.item(r, 0).text()
                val  = self.table.item(r, 1).text()
                hw   = self.table.item(r, 3).text()
                proc = self.table.item(r, 4).text()
                
                row_str = f"{name:<10} | {val:<8} | {hw:<8} | {proc}"
                self.update_maintenance_log(row_str)
            except AttributeError:
                continue # Skip if row is currently being updated/empty

        self.update_maintenance_log("-" * 40)
        self.update_maintenance_log("End of Snapshot.")


    def request_restart(self):
        self.receiver.send_command("restart")
        
        # Clean up the GUI so it looks like a fresh start
        self.live_log.appendPlainText("--- SYSTEM RESTART INITIATED ---")
        self.table.clearSelection()
        # Optional: Clear plots if you want a totally clean slate
        for name in self.plot_data:
            self.plot_data[name].clear()
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorDashboard()
    window.show()
    sys.exit(app.exec())