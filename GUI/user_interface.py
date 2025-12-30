import sys, socket, json, time
from collections import deque
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pyqtgraph as pg
import TCP_Manager

class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Industrial Monitoring System v2.0 - Final Prototype")
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

        self.status_label = QLabel("SYSTEM STATUS: INITIALIZING...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFixedHeight(50)
        outer_layout.addWidget(self.status_label)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_layout.addWidget(self.main_splitter)

        self.tabs = QTabWidget()
        self.main_splitter.addWidget(self.tabs)

        # Tab 1: Live Status
        self.table_tab = QWidget()
        table_layout = QVBoxLayout(self.table_tab)
        self.table = QTableWidget(len(self.limits), 5) 
        self.table.setHorizontalHeaderLabels(["Sensor", "Value", "Timestamp", "HW Status", "Process Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table)
        self.tabs.addTab(self.table_tab, "Live Status")

        # Tab 2: Plots
        self.plot_tab = QWidget()
        self.plot_grid = QGridLayout(self.plot_tab)
        self.plots, self.plot_data, self.curves = {}, {}, {}
        for i, name in enumerate(self.limits.keys()):
            p_widget = pg.PlotWidget(title=f"{name.upper()} Trend")
            self.plot_grid.addWidget(p_widget, i // 2, i % 2)
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

        # Maintenance Console (Bottom)
        self.console_panel = QWidget()
        console_layout = QVBoxLayout(self.console_panel)
        
        # --- Login Group (With Enter Key Support) ---
        self.login_group = QGroupBox("Engineer Login Required")
        login_h = QHBoxLayout(self.login_group)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter Password...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        # Connect 'Enter' key to the login function
        self.password_input.returnPressed.connect(self.check_password) 
        
        self.btn_login = QPushButton("Unlock Console")
        self.btn_login.clicked.connect(self.check_password)
        
        login_h.addWidget(self.password_input)
        login_h.addWidget(self.btn_login)
        console_layout.addWidget(self.login_group)

        # --- Console Content (Initially Hidden) ---
        self.console_content = QWidget()
        self.console_content.setVisible(False)
        content_layout = QVBoxLayout(self.console_content)
        
        self.live_log = QPlainTextEdit()
        self.live_log.setReadOnly(True)
        # Terminal-style styling
        self.live_log.setStyleSheet("""
            background-color: #000; 
            color: #0f0; 
            font-family: 'Consolas', 'Monaco', monospace;
            border: 1px solid #333;
        """)
        
        content_layout.addWidget(QLabel("MAINTENANCE TERMINAL"))
        content_layout.addWidget(self.live_log)

        # --- Command Buttons ---
        cmd_h = QHBoxLayout()
        self.btn_restart = QPushButton("Restart Simulator")
        self.btn_test = QPushButton("Clear Alarms")
        self.btn_snap = QPushButton("Value Snapshot")
        
        # Set specific styling for the restart/action buttons
        self.btn_restart.setStyleSheet("font-weight: bold; color: #ffca28;") 
        
        cmd_h.addWidget(self.btn_restart)
        cmd_h.addWidget(self.btn_test)
        cmd_h.addWidget(self.btn_snap)
        content_layout.addLayout(cmd_h)
        
        console_layout.addWidget(self.console_content)
        self.main_splitter.addWidget(self.console_panel)

        # Connections
        self.btn_restart.clicked.connect(self.request_restart)
        self.btn_test.clicked.connect(self.clear_alarm_log)
        self.btn_snap.clicked.connect(self.take_snapshot)

    def process_packet(self, packet):
        name = packet['sensor']
        val, hw_status = packet['value'], packet['status']
        row = self.sensor_to_row.get(name)
        if row is None: return

        self.plot_data[name].append(val)
        self.curves[name].setData(list(self.plot_data[name]))

        limit = self.limits.get(name)
        process_status = "OK"
        if val > limit['high']: process_status = "High Limit"
        elif val < limit['low']: process_status = "Low Limit"

        is_currently_alarmed = (hw_status == "FAULTY" or process_status != "OK")

        if is_currently_alarmed and self.previous_state[name] == "OK":
            self.add_to_alarm_log(name, val, f"HW:{hw_status}/PR:{process_status}")
            self.previous_state[name] = "ALARM"
        elif not is_currently_alarmed:
            self.previous_state[name] = "OK"

        row_color = QColor("#27ae60") # Green
        if hw_status == "FAULTY": row_color = QColor("#f1c40f") # Yellow
        elif process_status != "OK": row_color = QColor("#c0392b") # Red

        ts = time.strftime("%H:%M:%S", time.localtime(packet['timestamp']))
        data = [name, str(val), ts, hw_status, process_status]
        for col, text in enumerate(data):
            item = QTableWidgetItem(text)
            item.setBackground(row_color)
            item.setForeground(QColor("black") if hw_status == "FAULTY" else QColor("white"))
            self.table.setItem(row, col, item)
        
        self.update_system_status()

    def request_restart(self):
        """The Master Reset: Clears Simulator and GUI memory"""
        self.receiver.send_command("restart")
        self.clear_alarm_log()
        self.live_log.clear()
        self.update_maintenance_log("--- SYSTEM RESTART INITIATED ---")
        
        # CLEAR PLOTS
        for name in self.plot_data:
            self.plot_data[name].clear()
            self.curves[name].setData([])
            self.previous_state[name] = "OK"

    def clear_alarm_log(self):
        self.alarm_table.setRowCount(0)
        self.update_maintenance_log("Alarm history purged.")

    def take_snapshot(self):
        self.update_maintenance_log("--- SNAPSHOT ---")
        for r in range(self.table.rowCount()):
            n = self.table.item(r,0).text() if self.table.item(r,0) else "?"
            v = self.table.item(r,1).text() if self.table.item(r,1) else "?"
            self.update_maintenance_log(f"{n}: {v}")

    def add_to_alarm_log(self, name, val, alarm_type):
        self.alarm_table.insertRow(0)
        self.alarm_table.setItem(0, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.alarm_table.setItem(0, 1, QTableWidgetItem(name))
        self.alarm_table.setItem(0, 2, QTableWidgetItem(str(val)))
        self.alarm_table.setItem(0, 3, QTableWidgetItem(alarm_type))

    def update_system_status(self):
        worst = "OK"
        for r in range(self.table.rowCount()):
            hw = self.table.item(r, 3).text() if self.table.item(r,3) else "OK"
            pr = self.table.item(r, 4).text() if self.table.item(r,4) else "OK"
            if pr != "OK": worst = "PROCESS"
            if hw == "FAULTY": worst = "HARDWARE"; break

        if worst == "HARDWARE":
            self.status_label.setText("!!! HARDWARE FAULT (YELLOW) !!!")
            self.status_label.setStyleSheet("background-color: #f1c40f; color: black; font-weight: bold;")
        elif worst == "PROCESS":
            self.status_label.setText("!!! PROCESS ALARM (RED) !!!")
            self.status_label.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        else:
            self.status_label.setText("SYSTEM OPERATIONAL (GREEN)")
            self.status_label.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")

    def check_password(self):
        if self.password_input.text() == "admin123":
            self.login_group.setVisible(False)
            self.console_content.setVisible(True)
            self.update_maintenance_log("Engineer Authenticated.")
        else:
            # New: Friendly popup for failed attempts
            QMessageBox.warning(self, "Security Alert", "Unauthorized Access: Wrong Password.")
            self.password_input.clear()
            self.update_maintenance_log("Auth Failed: Invalid password attempt.")

    def update_maintenance_log(self, text):
        self.live_log.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {text}")

    def apply_styles(self):
        self.setStyleSheet("QMainWindow { background-color: #121212; } QTableWidget { background-color: #1e1e1e; color: white; }")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SensorDashboard(); window.show()
    sys.exit(app.exec())