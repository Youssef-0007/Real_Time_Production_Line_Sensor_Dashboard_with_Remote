import sys, socket, json, time
from collections import deque
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pyqtgraph as pg
from plyer import notification
import requests
import threading
import csv

try:
    from GUI import TCP_Manager  # When running from root (main/test_suit)
except ImportError:
    import TCP_Manager           # When running user_interface.py directly

class SensorDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        # set up the Top window of the dashboard
        self.setWindowTitle("Industrial Monitoring System v3.0 - Final Prototype")
        self.resize(1100, 900)
        
        self.load_config()

        # Dynamically build the mapping for table rows 
        self.sensor_to_row = {name: i for i, name in enumerate(self.limits.keys())}
        self.previous_state = {name: "OK" for name in self.limits.keys()}

        # Throttling Logic State
        # create peocess, and HW counter and status for each sensor
        # this makes it easy to track the process and hw status and 
        # know when it is true positive alarm to notify for!
        self.proc_counters = {name: 0 for name in self.limits.keys()}
        self.proc_notified = {name: False for name in self.limits.keys()}
        self.hw_counters = {name: 0 for name in self.limits.keys()}
        self.hw_notified = {name: False for name in self.limits.keys()}

        # FIXED: Case-sensitivity standardization
        self.PROC_THRESHOLD = 5     # Urgent -> fast notification for the machine safety (need immediate engagment)
        self.HW_THRESHOLD = 15      # Slow notifications (filtering hangs), but need to be represented for future checking

        # Connection Watchdog
        self.is_shutting_down = False
        self.watchdog_timer = QTimer()
        self.watchdog_timer.setInterval(3000) # 3 seconds
        self.watchdog_timer.timeout.connect(self.handle_connection_loss)
        self.watchdog_timer.start()
        
        # the setup functions of the UI
        self.setup_ui()
        self.apply_styles()

        # the TCP connection functions
        self.receiver = TCP_Manager.TCPManager()
        self.receiver.data_received.connect(self.process_packet)
        self.receiver.log_signal.connect(self.update_maintenance_log)
        self.receiver.start()

    def load_config(self):
        """ Load configuration data"""
        with open('config.json', 'r') as f:
            config = json.load(f)
        
        # Dynamically build the limits dictionary for the GUI
        self.limits = {}
        for s in config['sensors']:
            self.limits[s['name']] = {"low": s['min'], "high": s['max']}
        
        # Dynamically build the mapping for table rows
        #self.sensor_to_row = {name: i for i, name in enumerate(self.limits.keys())}
        
    def setup_ui(self):
        """ prepare the dashboard and divide and organize the visual apperance of the windows and buttons """

        # prepare the main structure of the dashboard
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
        self.btn_export = QPushButton("Export CSV")
        self.btn_shutdown = QPushButton("Shutdown Machine")

        # Set specific styling for the restart/action buttons
        self.btn_restart.setStyleSheet("font-weight: bold; color: #ffca28;") 
        # Styling it Red to indicate danger/finality
        self.btn_shutdown.setStyleSheet("""
            QPushButton {
                background-color: #c0392b; 
                color: white; 
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)

        # adding the interaction buttons to the console
        cmd_h.addWidget(self.btn_restart)
        cmd_h.addWidget(self.btn_test)
        cmd_h.addWidget(self.btn_snap)
        cmd_h.addWidget(self.btn_export)
        cmd_h.addWidget(self.btn_shutdown) 
        content_layout.addLayout(cmd_h)
        
        console_layout.addWidget(self.console_content)
        self.main_splitter.addWidget(self.console_panel)

        # Connections
        self.btn_restart.clicked.connect(self.request_restart)
        self.btn_test.clicked.connect(self.clear_alarm_log)
        self.btn_snap.clicked.connect(self.take_snapshot)
        self.btn_export.clicked.connect(self.export_to_csv)
        self.btn_shutdown.clicked.connect(self.request_shutdown)

    def process_packet(self, packet):
        # Reset watchdog as we just received data
        if not self.is_shutting_down:
            self.watchdog_timer.start()
        else:
            # Drop any leftover packets during shutdown
            return 
        
        # extract the required information form the packet
        name = packet['sensor']
        val, hw_status = packet['value'], packet['status']
        row = self.sensor_to_row.get(name)
        if row is None: return

        # add the value of this sensor to it's real time plot
        self.plot_data[name].append(val)
        self.curves[name].setData(list(self.plot_data[name]))

        # get the limits of the current sensor, to start the alarm checking operation
        limit = self.limits.get(name)
        process_status = "OK"
        if val > limit['high']: process_status = "High Limit"
        elif val < limit['low']: process_status = "Low Limit"

        is_currently_alarmed = (hw_status == "FAULTY" or process_status != "OK")
        # determining the ALARM in case it is PROCESS or HW, and not alarmed before
        if is_currently_alarmed and self.previous_state[name] == "OK":
            self.add_to_alarm_log(name, val, f"HW:{hw_status}/PR:{process_status}")
            self.previous_state[name] = "ALARM"
        elif not is_currently_alarmed:
            self.previous_state[name] = "OK"

        # at this point we have two tracks to follow, HW ALARMS, and PROCESS ALARMS
        # --- TRACK 1: PROCESS LIMITS (Leaky Bucket) ---
        is_proc_alarm = (val > limit['high'] or val < limit['low'])
        if is_proc_alarm:
            self.proc_counters[name] += 1
        else:
            # Decrement slowly (minimum 0) - this is the "Leak"
            if self.proc_counters[name] > 0:
                self.proc_counters[name] -= 1
            # If counter drops low enough, allow a new notification later
            if self.proc_counters[name] == 0:
                self.proc_notified[name] = False

        # Trigger Process Notification
        if self.proc_counters[name] >= self.PROC_THRESHOLD and not self.proc_notified[name]:
            # pop up desktop notification
            self.send_desktop_notification(name, val, "CRITICAL: Process Limit Exceeded")
            # send webhook alert
            self.send_discord_webhook(name, val, "CRITICAL: Process Limit Exceeded")
            self.proc_notified[name] = True

        # --- TRACK 2: HARDWARE RELIABILITY (Cumulative) ---
        if hw_status == "FAULTY":
            self.hw_counters[name] += 1
        
        # We DO NOT decrement hw_counters here. It stays high even if it fixes itself.
        # considering it need to be checked by the engineers

        # Trigger Reliability Notification
        if self.hw_counters[name] >= self.HW_THRESHOLD and not self.hw_notified[name]:
            self.send_desktop_notification(name, val, "MAINTENANCE: Low Sensor Reliability")
            self.send_discord_webhook(name, val, "MAINTENANCE: Low Sensor Reliability")
            self.hw_notified[name] = True
            # After notifying, we reset so we can track the next 15 failures
            self.hw_counters[name] = 0

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
        # send command to the simulator, and clear the plots and the alarm logs
        self.receiver.send_command("restart")
        self.clear_alarm_log()
        self.live_log.clear()
        self.update_maintenance_log("--- SYSTEM RESTART INITIATED ---")
        
        # CLEAR PLOTS
        for name in self.plot_data:
            self.plot_data[name].clear()
            self.curves[name].setData([])
            self.previous_state[name] = "OK"
        # clear the notification alarms' counters
        for name in self.limits.keys():
            self.proc_counters[name] = 0
            self.hw_counters[name] = 0
            self.proc_notified[name] = False
            self.hw_notified[name] = False
        self.update_maintenance_log("--- System Purged: All Reliability Counters Reset ---")
        
    def apply_styles(self):
        """ apply the style and colors to the dashboard """
        self.setStyleSheet("QMainWindow { background-color: #121212; } QTableWidget { background-color: #1e1e1e; color: white; }")

    def clear_alarm_log(self):
        """ Clear the alarm logs in the dashboard"""
        self.alarm_table.setRowCount(0)
        for name in self.limits.keys():
            self.proc_notified[name] = False
            self.hw_notified[name] = False
        self.update_maintenance_log("Alarm history purged.")
    
    def add_to_alarm_log(self, name, val, alarm_type):
        """ the main logging function of the alarms """
        self.alarm_table.insertRow(0)
        self.alarm_table.setItem(0, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.alarm_table.setItem(0, 1, QTableWidgetItem(name))
        self.alarm_table.setItem(0, 2, QTableWidgetItem(str(val)))
        self.alarm_table.setItem(0, 3, QTableWidgetItem(alarm_type))

    def take_snapshot(self):
        """ Take snapshot of the current values on the table and log it to the real-time logs"""
        self.update_maintenance_log("--- SNAPSHOT ---")
        for r in range(self.table.rowCount()):
            n = self.table.item(r,0).text() if self.table.item(r,0) else "?"
            v = self.table.item(r,1).text() if self.table.item(r,1) else "?"
            self.update_maintenance_log(f"{n}: {v}")

    def export_to_csv(self):
        """" Export the alarm logs into a .csv file """
        path, _ = QFileDialog.getSaveFileName(self, "Export Alarm Log", "", "CSV Files (*.csv)")
        if path:
            try:
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    # Header row
                    writer.writerow(["Timestamp", "Sensor", "Value", "Alarm Type"])
                    # Table data
                    for r in range(self.alarm_table.rowCount()):
                        row_data = [self.alarm_table.item(r, c).text() for c in range(4)]
                        writer.writerow(row_data)
                self.update_maintenance_log(f"Data successfully exported to {path}")
                QMessageBox.information(self, "Success", "Alarm log exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {e}")


    def update_system_status(self):
        """ Tracing and updating the system status """
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
        """ check the password to open the maintanance console """
        if self.password_input.text() == "admin123":
            self.login_group.setVisible(False)
            self.console_content.setVisible(True)
            self.update_maintenance_log("Engineer Authenticated.")
        else:
            # Friendly popup for failed attempts
            QMessageBox.warning(self, "Security Alert", "Unauthorized Access: Wrong Password.")
            self.password_input.clear()
            self.update_maintenance_log("Auth Failed: Invalid password attempt.")

    def update_maintenance_log(self, text):
        """ Tracing and updating the real-time logs for the system"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        formatted_text = f"[{timestamp}] {text}"
        
        # Update UI
        self.live_log.appendPlainText(formatted_text)
        
        # Write to permanent file (Append mode)
        try:
            with open("industrial_monitor.log", "a") as f:
                f.write(formatted_text + "\n")
        except:
            pass # Prevent app crash if file is locked


    def send_desktop_notification(self, sensor, value, alarm_type):
        """Bonus B: Desktop Notification System"""
        try:
            # prepare the notification packet
            notification.notify(
                title=f"SENSOR ALERT: {sensor.upper()}",
                message=f"Status: {alarm_type}\nValue: {value}\nAction Required!",
                app_name="Industrial Monitor",
                timeout=10 # Notification stays for 10 seconds
            )
            self.update_maintenance_log(f"NOTIFICATION SENT: {sensor} ({alarm_type})")
        except Exception as e:
            self.update_maintenance_log(f"Notification Error: {e}")

    import requests # You might need to pip install requests

    def send_discord_webhook(self, sensor, value, alarm_type):
        """Bonus B: Discord Integration (Highly Reliable for Prototypes)"""
        # the webhook URL from discord channel
        webhook_url = "https://discordapp.com/api/webhooks/1455988477127557288/y0Q2ypbHXsdn8_OhFSfKCUD9tutYbHQPZjX-B1fEj3jwXlHF0cwpXqjFFOP-wEUH3461"
        
        # Use 'embeds' for a professional look with a colored side bar
        color = 15158332 if "CRITICAL" in alarm_type else 15844367 # Red vs Yellow
        
        payload = {
            "embeds": [{
                "title": f"🚨 SENSOR ALERT: {sensor.upper()}",
                "description": f"**Status:** {alarm_type}\n**Current Value:** `{value:.2f}`",
                "color": color,
                "footer": {"text": f"Logged at: {time.strftime('%H:%M:%S')}"}
            }]
        }

        def post_request():
            """ send the notification to the channel """
            try:
                # Send the data to Discord
                requests.post(webhook_url, json=payload, timeout=5)
            except Exception as e:
                print(f"Discord Webhook Error: {e}")

        # Run in background so the GUI doesn't flicker or freeze
        threading.Thread(target=post_request, daemon=True).start()

    def handle_connection_loss(self):
        """ Notify for connection loss by updating the system dashboard """
        self.status_label.setText("⚠️ SYSTEM OFFLINE - CONNECTION LOST")
        self.status_label.setStyleSheet("background-color: #7f8c8d; color: white; font-weight: bold;")
        self.update_maintenance_log("CRITICAL: No data received for 3 seconds. Check Simulator.")

    def request_shutdown(self):
        """ hanndle the shutdown operation by stopping the watchdog, TCP receiver, and send sommand to the simulator """
        confirm = QMessageBox.critical(self, "Confirm Shutdown", 
                                    "This will kill the simulator and stop GUI polling. Proceed?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if confirm == QMessageBox.StandardButton.Yes:
            # 1. Kill the Watchdog first so it stops complaining
            # set the kill switch flag firs
            self.is_shutting_down = True
            # kill the watchdog
            self.watchdog_timer.stop()
            
            # 2. Tell the receiver to stop reconnecting
            self.receiver.stop() 
            
            # 3. Send the final command to the simulator
            self.receiver.send_command("shutdown")
            
            # 4. Update UI to "Offline" mode
            self.update_maintenance_log("--- PLANNED SHUTDOWN COMPLETE ---")
            self.status_label.setText("SYSTEM STATUS: POWERED OFF (MANUAL)")
            self.status_label.setStyleSheet("background-color: #2c3e50; color: #95a5a6; font-weight: bold;")
            
            # Disable buttons
            self.btn_shutdown.setEnabled(False)
            self.btn_restart.setEnabled(False)


if __name__ == "__main__":# this 
    app = QApplication(sys.argv)
    window = SensorDashboard(); window.show()
    sys.exit(app.exec())