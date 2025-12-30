#!/usr/bin/env python3
import random
import threading
import time
import queue
import json
import socket
import os


HOST = '127.0.0.1'
PORT = 5000

class SensorsSimulator:
    # Static variables shared by ALL instances
    data_queue = queue.Queue()
    fault_probability = 0.02
    # Use an Event for Reset (Thread-safe Traffic Light)
    reset_evt = threading.Event()
    # Use an Event for Global Running status
    running_evt = threading.Event()


    def __init__(self, sensor_id: int, name: str, min_val: int, max_val: int, interval: float) -> None:
        self.id = sensor_id
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.interval = interval

    def run_simulation(self) -> None:
        """Logic loop with Restart Support"""
        file_path = f"./test_data/{self.name}_data.txt"
        try:
            with open(file_path) as f:
                lines = f.read().splitlines()
        except:
            print(f"File {file_path} not found. Thread ending.")
            return
        
        while SensorsSimulator.running_evt.is_set():
            for line in lines:
                # CHECK FOR RESET
                if SensorsSimulator.reset_evt.is_set():
                    break 

                if not SensorsSimulator.running_evt.is_set():
                    return # Exit thread entirely
                
                value = float(line.strip())
                status = "FAULTY" if random.random() < self.fault_probability else "OK"
                packet = {
                    "id": self.id, "sensor": self.name, "value": value,
                    "timestamp": time.time(), "status": status
                }
                SensorsSimulator.data_queue.put(packet)

                time.sleep(self.interval)
                    

            # ------ Handle the reset logic ----
            if SensorsSimulator.reset_evt.is_set():
                if self.id == 100: # Only first sensor flips flag back
                    SensorsSimulator.reset_evt.clear()
                print(f"Simulator: {self.name} resetart!")
            
            else:
                # in this case the reset event doesn't being sat, so this means reached the end of the test data 
                # this could be treated to be FAULTY sensor where no data comming from
                # the sensor will stuck into this case until being reset
                while not SensorsSimulator.reset_evt.is_set() and SensorsSimulator.running_evt.is_set():
                    value = 0
                    status = "FAULTY"
                    packet = {
                        "id": self.id, "sensor": self.name, "value": value,
                        "timestamp": time.time(), "status": status
                    }
                    SensorsSimulator.data_queue.put(packet)
                    time.sleep(self.interval)
            
            

    @staticmethod
    def tcp_transmitter() -> None:
        """Centralized transmitter for all instances"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # Allow address reuse (prevents "Port already in use" errors on restart)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen(1)
            print(f"Simulator: Server started. Waiting for Dashboard on {PORT}...")

            conn, addr = s.accept()
            print(f"Simulator: Dashboard connected from {addr}")

            # start the tcp_receiver as thread inside the tcp_transmitter after accepting connection, 
            # both threads share the same conn
            # We pass the 'conn' object so it can listen on the same pipe
            receiver_thread = threading.Thread(target=SensorsSimulator.tcp_receiver, args=(conn,), daemon=True)
            receiver_thread.start()

            with conn:
                while SensorsSimulator.running_evt.is_set():
                    try:
                        data = SensorsSimulator.data_queue.get()
                        message = json.dumps(data) + "\n"
                        conn.sendall(message.encode('utf-8'))
                    except queue.Empty:
                        continue # Keep the loop alive if no sensor data is ready
                    except (ConnectionResetError, BrokenPipeError):
                        print("Dashboard disconnected.")
                        break

    @ staticmethod
    def tcp_receiver(conn):
        """Bonus A: Maintenance Console Logic"""
        print("Simulator: Command Listener Active.")
        while SensorsSimulator.running_evt.is_set():
            try:
                # Receive the command from the GUI
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                
                # TCP can "clump" messages, so we split by newline if needed
                for line in data.strip().split('\n'):
                    cmd = json.loads(line)
                    if cmd.get('action') == "restart":
                        # 1. Clear the queue backlog
                        while not SensorsSimulator.data_queue.empty():
                            try: SensorsSimulator.data_queue.get_nowait()
                            except: break
                        # 2. Trigger the Event
                        SensorsSimulator.reset_evt.set()
            except: break
                    

if __name__ == "__main__":
    
    SensorsSimulator.running_evt.set() # Set to "Running"
    SensorsSimulator.reset_evt.clear()

    # Create instances
    sensors = [
        # SensorID, Name, Min, Max, Interval
        SensorsSimulator(100, "temp", 20, 100, 1),
        SensorsSimulator(200, "optical", 0, 1000, 0.2),
        SensorsSimulator(300, "press", 0, 10, 0.3),
        SensorsSimulator(400, "speed", 0, 1500, 0.5),
        SensorsSimulator(500, "vib", 0, 10, 0.8)
    ]

    # Start Transmitter
    threading.Thread(target=SensorsSimulator.tcp_transmitter, daemon=True).start()

    time.sleep(2)

    # Start each sensor in its own thread
    for s in sensors:
        threading.Thread(target=s.run_simulation, daemon=True).start()
        print(f"Thread started for {s.name}")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        SensorsSimulator.running_evt.clear() # Trigger shutdown
        print("\nStopping simulator...")