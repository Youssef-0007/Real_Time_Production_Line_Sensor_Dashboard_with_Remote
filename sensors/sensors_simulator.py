#!/usr/bin/env python3
import random
import threading
import time
import queue
import json
import socket
import os



class SensorsSimulator:
    # Static variables shared by ALL instances
    data_queue = queue.Queue()
    fault_probability = 0.02
    # Use an Event for Reset (Thread-safe Traffic Light)
    reset_evt = threading.Event()
    # Use an Event for Global Running status
    running_evt = threading.Event()


    def __init__(self, sensor_id: int, name: str, interval: float) -> None:
        self.id = sensor_id
        self.name = name
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

    @staticmethod
    def tcp_receiver(conn):
        """Standardized Command Listener"""
        print("Simulator: Command Listener Active.")
        while SensorsSimulator.running_evt.is_set():
            try:
                raw_data = conn.recv(1024).decode('utf-8')
                if not raw_data:
                    break
                
                # Split by newline in case multiple commands arrived at once
                for line in raw_data.strip().split('\n'):
                    clean_line = line.strip()
                    if not clean_line: continue

                    # Check for PLAIN TEXT commands first (Simple/Fast)
                    if clean_line == "shutdown":
                        print("SHUTDOWN COMMAND RECEIVED. CLOSING PROCESS...")
                        os._exit(0)
                    
                    if clean_line == "restart":
                        # Handle plain string restart
                        SensorsSimulator._trigger_restart()
                        continue

                    # Check for JSON commands (Robust/Flexible)
                    try:
                        cmd = json.loads(clean_line)
                        action = cmd.get('action')
                        
                        if action == "restart":
                            SensorsSimulator._trigger_restart()
                        elif action == "shutdown":
                            print("SHUTDOWN COMMAND RECEIVED via JSON.")
                            os._exit(0)
                    except json.JSONDecodeError:
                        # If it's not JSON and wasn't caught by the strings above, ignore it
                        print(f"Simulator: Received unknown noise: {clean_line}")

            except Exception as e:
                print(f"Receiver Error: {e}")
                break

    @staticmethod
    def _trigger_restart():
        """Helper to clear queue and set event"""
        print("RESTARTING SENSORS...")
        while not SensorsSimulator.data_queue.empty():
            try: SensorsSimulator.data_queue.get_nowait()
            except: break
        SensorsSimulator.reset_evt.set()

if __name__ == "__main__":
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    SensorsSimulator.running_evt.set() # Set to "Running"
    SensorsSimulator.reset_evt.clear()

    # Automatically create sensor instances from config
    sensors = []
    for s_conf in config['sensors']:
        s = SensorsSimulator(
            sensor_id=s_conf['id'],
            name=s_conf['name'],
            interval=s_conf['interval']
        )
        sensors.append(s)


    HOST = config['network']['host']
    PORT = config['network']['port']

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