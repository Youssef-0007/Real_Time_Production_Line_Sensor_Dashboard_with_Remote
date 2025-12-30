import subprocess
import time
import sys

def launch():
    # 1. Start Simulator (The Server)
    # We use 'stdout=subprocess.DEVNULL' if you want to hide the simulator's text 
    # and only see GUI logs.
    sim_proc = subprocess.Popen([sys.executable, "sensors/sensors_simulator.py"])
    
    # 2. Give the server a moment to open Port 5000
    # If the GUI starts too fast, it will fail to connect.
    time.sleep(1) 
    
    # 3. Start GUI (The Client)
    print("System starting...")
    gui_proc = subprocess.Popen([sys.executable, "GUI/user_interface.py"])

    try:
        # Keep main.py alive as long as the GUI is running
        gui_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        # When GUI is closed, kill the simulator too
        sim_proc.terminate()
        gui_proc.terminate()
        print("System shutdown complete.")

if __name__ == "__main__":
    launch()