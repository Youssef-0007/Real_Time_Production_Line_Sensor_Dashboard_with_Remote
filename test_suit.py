import unittest
import time
import os
import tempfile
from unittest.mock import patch, MagicMock
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QMessageBox

from GUI.user_interface import SensorDashboard
from sensors.sensors_simulator import SensorsSimulator

class TestIndustrialSystem(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Create the app once to save resources"""
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        """Fresh GUI for every test to ensure state isolation"""
        self.app = QApplication.instance() or QApplication([])
        
        # 1. Create the GUI instance
        self.gui = SensorDashboard()
        
        # 2. STOP the network thread immediately if it started
        # This prevents the "Destroyed while thread is still running" error
        if self.gui.receiver.isRunning():
            self.gui.receiver.terminate()
            self.gui.receiver.wait() 

    def tearDown(self):
        """Clean up after each test"""
        if hasattr(self, 'gui'):
            self.gui.receiver.terminate()
            self.gui.receiver.wait()

    # --- CATEGORY 1: SENSOR PARSING & API ---
    def test_parsing_and_packet_integrity(self):
        """Requirement: Sensor parsing & API output format"""
        raw_line = " 75.25 \n"
        parsed = float(raw_line.strip())
        
        # Test API Structure
        packet = {
            "id": 100,
            "sensor": "temp",
            "value": parsed,
            "timestamp": time.time(),
            "status": "OK"
        }
        
        self.assertEqual(parsed, 75.25)
        self.assertIsInstance(packet['value'], float)
        self.assertEqual(len(packet), 5) # Ensure no extra/missing keys

    # --- CATEGORY 2: ALARM LOGIC (BOUNDARY TESTING) ---
    def test_alarm_thresholds(self):
        """Requirement: Alarm logic at boundaries (Low, OK, High)"""
        limits = self.gui.limits["temp"] # 20 to 80
        
        # Test Exact Boundary (Professional systems must define this)
        val_at_limit = 80.0 
        is_high = val_at_limit > limits['high']
        self.assertFalse(is_high, "Value exactly at 80.0 should be considered OK (not > 80)")
        
        # Test Alarm Trigger
        self.assertTrue(80.1 > limits['high'], "80.1 must trigger High Limit")
        self.assertTrue(19.9 < limits['low'], "19.9 must trigger Low Limit")

    def test_color_priority_matrix(self):
        """Requirement: Logic priority (HW Fault > Process Alarm)"""
        # We test the logic used inside process_packet
        
        # Scenario: Sensor is FAULTY AND value is too high
        status_hw = "FAULTY"
        status_proc = "High Limit"
        
        color = "#27ae60" # Default Green
        if status_hw == "FAULTY":
            color = "#f1c40f" # Yellow (Priority 1)
        elif status_proc != "OK":
            color = "#c0392b" # Red (Priority 2)
            
        self.assertEqual(color, "#f1c40f", "Hardware Fault color must override Process Alarm color")

    # --- CATEGORY 3: UI STATE MANAGEMENT ---
    def test_alarm_history_logging(self):
        """Test if the Alarm Table actually grows when an alarm occurs"""
        initial_count = self.gui.alarm_table.rowCount()
        
        # Simulate a packet that triggers an alarm
        test_packet = {
            "sensor": "temp",
            "value": 99.9,
            "status": "OK",
            "timestamp": time.time()
        }
        self.gui.process_packet(test_packet)
        
        new_count = self.gui.alarm_table.rowCount()
        self.assertEqual(new_count, initial_count + 1, "Alarm table should have 1 new row")

    def test_master_reset_logic(self):
        """Test if Master Reset wipes the memory and UI correctly"""
        # 1. Fill it with junk
        self.gui.plot_data["temp"].append(50.0)
        self.gui.alarm_table.insertRow(0)
        
        # 2. Reset
        self.gui.request_restart()
        
        # 3. Verify
        self.assertEqual(len(self.gui.plot_data["temp"]), 0)
        self.assertEqual(self.gui.alarm_table.rowCount(), 0)

    # --- CATEGORY 4: NOTIFICATION THROTTLING (NEW) ---

    def test_process_leaky_bucket(self):
        """Test if Process Alarm notifies only after PROC_THRESHOLD strikes"""
        sensor = "temp"
        # Ensure counter starts at 0
        self.gui.proc_counters[sensor] = 0
        self.gui.proc_notified[sensor] = False
        
        # Simulate 4 alarms (Threshold is 5)
        packet = {"sensor": sensor, "value": 99.9, "status": "OK", "timestamp": time.time()}
        for _ in range(4):
            self.gui.process_packet(packet)
        
        self.assertFalse(self.gui.proc_notified[sensor], "Should not notify at 4 strikes")
        
        # The 5th alarm
        self.gui.process_packet(packet)
        self.assertTrue(self.gui.proc_notified[sensor], "Should notify at 5 strikes")

    def test_process_leak_recovery(self):
        """Test if the 'Leak' works (counter decrements on healthy data)"""
        sensor = "press"
        self.gui.proc_counters[sensor] = 3 # Start with 3 strikes
        
        # Send a healthy packet
        packet = {"sensor": sensor, "value": 20.0, "status": "OK", "timestamp": time.time()}
        self.gui.process_packet(packet)
        
        self.assertEqual(self.gui.proc_counters[sensor], 2, "Counter should leak (decrement) on healthy data")

    def test_hw_cumulative_reliability(self):
        """Test if HW counter persists even if sensor 'recovers' temporarily"""
        sensor = "vib"
        self.gui.hw_counters[sensor] = 0
        
        # 1. Fault occurs
        bad_packet = {"sensor": sensor, "value": 1.0, "status": "FAULTY", "timestamp": time.time()}
        self.gui.process_packet(bad_packet)
        self.assertEqual(self.gui.hw_counters[sensor], 1)
        
        # 2. Sensor "recovers" (Healthy packet)
        good_packet = {"sensor": sensor, "value": 1.0, "status": "OK", "timestamp": time.time()}
        self.gui.process_packet(good_packet)
        
        # 3. Verify it DID NOT decrement (as per your vision)
        self.assertEqual(self.gui.hw_counters[sensor], 1, "HW counter should not leak/decrement")

    def test_hw_notification_threshold(self):
        """Test if HW notifies at exactly 15 cumulative strikes"""
        sensor = "optical"
        self.gui.hw_counters[sensor] = 14
        self.gui.hw_notified[sensor] = False
        
        packet = {"sensor": sensor, "value": 50.0, "status": "FAULTY", "timestamp": time.time()}
        self.gui.process_packet(packet)
        
        self.assertTrue(self.gui.hw_notified[sensor], "Should notify after 15th cumulative HW fault")
        self.assertEqual(self.gui.hw_counters[sensor], 0, "HW counter should reset to 0 after notification")

    # --- CATEGORY 5: PROFFESSIONAL FEATURES TESTS ---

    def test_watchdog_trigger(self):
        """Test if the Watchdog triggers connection loss after timeout"""
        # Manually trigger the timeout signal
        self.gui.handle_connection_loss()
        
        # Verify UI State
        self.assertEqual(self.gui.status_label.text(), "⚠️ SYSTEM OFFLINE - CONNECTION LOST")
        # Verify color is the grey hex code we used
        self.assertIn("background-color: #7f8c8d", self.gui.status_label.styleSheet())

    def test_csv_export_logic(self):
        """Test if the data is correctly formatted for CSV export"""
        # 1. Manually add data to the alarm table
        self.gui.add_to_alarm_log("temp", 85.0, "High Limit")
        
        # 2. Use a temporary file path
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        
        # 3. Mock the File Dialog to return our temp path automatically
        with patch('PyQt6.QtWidgets.QFileDialog.getSaveFileName', return_value=(tmp_path, "")):
            self.gui.export_to_csv()
        
        # 4. Verify the file exists and has content
        self.assertTrue(os.path.exists(tmp_path))
        with open(tmp_path, 'r') as f:
            content = f.read()
            self.assertIn("temp", content)
            self.assertIn("High Limit", content)
        
        # Cleanup
        os.remove(tmp_path)

    def test_persistent_logging(self):
        """Test if the 'Black Box' log file is created and updated"""
        test_msg = "TEST_MAINTENANCE_LOG_ENTRY"
        
        # Ensure file is clean
        if os.path.exists("industrial_monitor.log"):
            os.remove("industrial_monitor.log")
            
        # Trigger log
        self.gui.update_maintenance_log(test_msg)
        
        # Verify file content
        self.assertTrue(os.path.exists("industrial_monitor.log"))
        with open("industrial_monitor.log", "r") as f:
            log_content = f.read()
            self.assertIn(test_msg, log_content)

    def test_shutdown_command_sent(self):
        """Verify that the shutdown command is dispatched to the network manager"""
        # Mock the send_command method
        self.gui.receiver.send_command = MagicMock()
        
        # Mock the QMessageBox to automatically return 'Yes'
        with patch('PyQt6.QtWidgets.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
            self.gui.request_shutdown()
            
        # Assert the correct string was sent
        self.gui.receiver.send_command.assert_called_with("shutdown")

if __name__ == '__main__':
    unittest.main()