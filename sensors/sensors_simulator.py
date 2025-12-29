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
    running = True 
    fault_probability = 0.02


    def __init__(self, sensor_id: int, name: str, min_val: int, max_val: int, interval: float) -> None:
        self.id = sensor_id
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.interval = interval

    def determine_status(self) -> str:
        """Determine if sensor is OK, or FAULTY"""
        # Random faulty sensor (1% chance)
        if random.random() < SensorsSimulator.fault_probability:
            return "FAULTY"
        return "OK"      

    def run_simulation(self) -> None:
        """The logic loop for each sensor instance reading from a file"""
        
        # 1. Load the data into memory once
        try:
            # Note: Ensure the path is correct relative to where you RUN the script
            with open(f"../test_data/{self.name}_data.txt") as f:
                lines = f.read().splitlines()
            print(f"Loaded {len(lines)} data points for {self.name}")
        except Exception as e:
            print(f"Error: Could not open test_data/{self.name}_data.txt: {e}")
            return
        
        # 2. Start the infinite loop
        while SensorsSimulator.running:
            for line in lines:
                if not SensorsSimulator.running: break
                
                try:
                    # Convert string from file to float
                    value = float(line.strip())
                    
                    # Call status logic (pass the value!)
                    status = self.determine_status()

                    packet = {
                        "id": self.id,
                        "sensor": self.name,
                        "value": value, #round(value, 2), 
                        "timestamp": time.time(),
                        "status": status,
                    }

                    SensorsSimulator.data_queue.put(packet)
                    
                    # Control the speed of playback
                    time.sleep(self.interval)
                    
                except ValueError:
                    print(f"Skipping invalid data line in {self.name}: {line}")
                    continue

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
                while SensorsSimulator.running:
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
        while SensorsSimulator.running:
            try:
                # Receive the command from the GUI
                data = conn.recv(1024).decode('utf-8')
                if not data:
                    break
                
                # TCP can "clump" messages, so we split by newline if needed
                for line in data.strip().split('\n'):
                    cmd = json.loads(line)
                    action = cmd.get('action')
                    
                    print(f"\n[COMMAND RECEIVED]: {action}")
                    
                    if action == "restart":
                        print(">>> ACTION: Re-initializing sensor baseline...")
                        # Logic to reset sensors 
                    elif action == "self_test":
                        print(">>> ACTION: Running internal diagnostic sweep...")
                    elif action == "snapshot":
                        print(">>> ACTION: Generating high-priority data dump...")
            except Exception as e:
                print(f"Receiver Error: {e}")
                break

if __name__ == "__main__":
    # 1. Create instances
    sensors = [
        # SensorID, Name, Min, Max, Interval
        SensorsSimulator(100, "temp", 20, 100, 10),
        SensorsSimulator(200, "optical", 0, 1000, 2),
        SensorsSimulator(300, "press", 0, 10, 3),
        SensorsSimulator(400, "speed", 0, 1500, 5),
        SensorsSimulator(500, "vib", 0, 10, 8)
    ]

    # 2. Start Transmitter
    threading.Thread(target=SensorsSimulator.tcp_transmitter, daemon=True).start()

    # 3. Start each sensor in its own thread
    for s in sensors:
        threading.Thread(target=s.run_simulation, daemon=True).start()
        print(f"Thread started for {s.name}")

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        SensorsSimulator.running = False
        print("\nStopping simulator...")