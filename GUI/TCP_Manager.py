import socket
import json
import time
from PyQt6.QtCore import QThread, pyqtSignal

class TCPManager(QThread):
    data_received = pyqtSignal(dict)
    log_signal = pyqtSignal(str) 

    def __init__(self, host='127.0.0.1', port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self._socket = None
        self.running = True

    def run(self):
        """The background loop for receiving data"""
        while self.running:
            try:
                self.log_signal.emit(f"Connecting to {self.host}:{self.port}...")
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    self._socket = s 
                    s.connect((self.host, self.port))
                    self.log_signal.emit("Network: Connected to Simulator.")
                    
                    # Use a file-like object for easier line reading
                    f = s.makefile('r')
                    while self.running:
                        line = f.readline()
                        if not line:
                            break
                        packet = json.loads(line)
                        self.data_received.emit(packet)
            except Exception as e:
                self._socket = None
                self.log_signal.emit(f"Connection lost: {e}. Retrying...")
                time.sleep(2)

    def send_command(self, action, params=None):
        """Method called by the GUI to send data back to the simulator"""
        if self._socket:
            try:
                command = {"action": action, "params": params or {}, "timestamp": time.time()}
                message = json.dumps(command) + "\n"
                self._socket.sendall(message.encode('utf-8'))
                self.log_signal.emit(f"CMD SENT: {action}")
                return True
            except Exception as e:
                self.log_signal.emit(f"SEND FAILED: {e}")
                return False
        self.log_signal.emit("SEND ERROR: No active connection.")
        return False