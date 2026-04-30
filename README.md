# Real_Time_Production_Line_Sensor_Dashboard_with_Remote
Python desktop application designed for a production line environment. The system monitor at least 5 sensors simultaneously, update data in real time, trigger alarms when limits are exceeded, provide remote data access, and include optional advanced maintenance &amp; notification features.

# Real-Time Production Line Sensor Dashboard with Remote Monitoring

A comprehensive Python desktop application for industrial production line monitoring, featuring real-time sensor data visualization, intelligent alarm management, remote access capabilities, and advanced maintenance features.

## 📋 Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running Instructions](#running-instructions)
- [TCP Protocol Description](#tcp-protocol-description)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Future Enhancements](#future-enhancements)

---

## ✨ Features

### Core Functionality
- **Multi-Sensor Monitoring**: Simultaneous tracking of 5+ sensors (temperature, optical, pressure, speed, vibration)
- **Real-Time Data Visualization**: Live plots and status tables with sub-second updates
- **Dual-Track Alarm System**: 
  - Process limit alarms (critical threshold violations)
  - Hardware reliability alarms (sensor malfunction detection)
- **Remote TCP Communication**: Bidirectional data streaming and command execution
- **Intelligent Alert Throttling**: Leaky bucket algorithm prevents notification spam

### Advanced Features
- **Desktop Notifications**: System-level alerts using `plyer`
- **Discord Webhook Integration**: Real-time alerts to team channels with color-coded embeds
- **Live Maintenance Console**: Password-protected engineer terminal with command execution
- **Data Export**: CSV export of alarm history for post-incident analysis
- **Persistent Logging**: Automatic file-based logging to `industrial_monitor.log`
- **Connection Watchdog**: Automatic detection and notification of simulator disconnection
- **Graceful Shutdown**: Coordinated shutdown of simulator and dashboard with confirmation

### Operational Commands
- **Restart Simulator**: Complete system reset with memory purge
- **Clear Alarms**: Reset alarm history and notification counters
- **Value Snapshot**: Capture current sensor readings to log
- **Export CSV**: Generate timestamped alarm reports
- **Shutdown Machine**: Coordinated termination of all system components

---

## 🏗️ System Architecture

### High-Level Component Overview

```
╔═════════════════════════════════════════════════════════════════════════╗
║                     INDUSTRIAL MONITORING SYSTEM                        ║
║                          (Two-Process Architecture)                     ║
╚═════════════════════════════════════════════════════════════════════════╝

┌────────────────────────────────────┐      ┌─────────────────────────────────────┐
│    PROCESS 1: SENSOR SIMULATOR     │      │     PROCESS 2: DASHBOARD GUI        │
│   (sensors/sensors_simulator.py)   │      │    (GUI/user_interface.py)          │
├────────────────────────────────────┤      ├─────────────────────────────────────┤
│                                    │      │                                     │
│  ┌───────────────────────────────┐ │      │  ┌────────────────────────────────┐ │
│  │   MAIN THREAD                 │ │      │  │   MAIN THREAD (Qt Event Loop)  │ │
│  │  - Load config.json           │ │      │  │  - SensorDashboard (QMainWindow) │
│  │  - Create sensor instances    │ │      │  │  - Load config.json            │ │
│  │  - Start all threads          │ │      │  │  - Initialize UI components    │ │
│  │  - Keep-alive loop            │ │      │  │  - Watchdog timer (3s)         │ │
│  └───────────────────────────────┘ │      │  └────────────────────────────────┘ │
│                                    │      │                                     │
│  ┌───────────────────────────────┐ │      │  ┌───────────────────────────────┐  │
│  │  SENSOR THREADS (5 workers)   │ │      │  │  TCP MANAGER (QThread)        │  │
│  │  ┌─────────────────────────┐  │ │      │  │  ┌─────────────────────────┐  │  │
│  │  │ Thread 1: temp          │  │ │      │  │  │ - Connect to simulator  │  │  │
│  │  │  - Read test_data/      │  │ │      │  │  │ - Receive JSON packets  │  │  │
│  │  │  - Add fault (2% prob)  │◄─┼─┼──┐   │  │  │ - Emit data_received    │  │  │
│  │  │  - Push to data_queue   │  │ │  │   │  │  │ - Auto-reconnect on fail│  │  │
│  │  └─────────────────────────┘  │ │  │   │  │  └─────────────────────────┘  │  │
│  │  │ Thread 2: optical       │  │ │  │   │  └───────────────────────────────┘  │
│  │  │ Thread 3: press         │  │ │  │   │                                     │
│  │  │ Thread 4: speed         │  │ │  │   │  ┌───────────────────────────────┐  │
│  │  │ Thread 5: vib           │  │ │  │   │  │  UI COMPONENTS                │  │
│  │  └─────────────────────────┘  │ │  │   │  │  - QTableWidget (Live Status) │  │
│  └───────────────────────────────┘ │  │   │  │  - PyQtGraph plots (5 sensors)│  │
│                                    │  │   │  │  - Alarm history table        │  │
│  ┌───────────────────────────────┐ │  │   │  │  - Maintenance console        │  │
│  │  SHARED CLASS VARIABLES       │ │  │   │  └───────────────────────────────┘  │
│  │  ┌─────────────────────────┐  │ │  │   │                                     │
│  │  │ data_queue (Queue)      │◄─┼─┼──┘   │  ┌───────────────────────────────┐  │
│  │  │ fault_probability=0.02  │  │ │      │  │  ALARM LOGIC                  │  │
│  │  │ reset_evt (Event)       │  │ │      │  │  - proc_counters{} (Leaky)    │  │
│  │  │ running_evt (Event)     │  │ │      │  │  - hw_counters{} (Cumulative) │  │
│  │  └─────────────────────────┘  │ │      │  │  - PROC_THRESHOLD = 5         │  │
│  └──────────────||───────────────┘ │      │  │  - HW_THRESHOLD = 15          │  │
│                 ▼                  │      │  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐ │      │                                     │
│  │  TCP TRANSMITTER THREAD       │ │      │  ┌───────────────────────────────┐  │
│  │  ┌─────────────────────────┐  │ │      │  │  NOTIFICATION SYSTEM          │  │
│  │  │ - Bind 127.0.0.1:5000   │  │ │      │  │  - Desktop (plyer)            │  │
│  │  │ - Accept connection     │  │ │      │  │  - Discord webhook            │  │
│  │  │ - Start tcp_receiver    │  │ │      │  │  - File logging               │  │
│  │  │ - while running:        │  │ │      │  └───────────────────────────────┘  │
│  │  │   • Get from data_queue │  │ │      │                                     │
│  │  │   • JSON encode         │──┼─┼─┐    └─────────────────────────────────────┘
│  │  │   • Send + "\n"         │  │ │ │                      ▲
│  │  └─────────────────────────┘  │ │ │                      │
│  └───────────────────────────────┘ │ │    ┌─────────────────┴─────────────────┐
│                                    │ │    │    TCP/IP SOCKET CONNECTION       │
│  ┌───────────────────────────────┐ │ │    │    Port: 5000 (configurable)      │
│  │  TCP RECEIVER THREAD          │ │ │    │    Protocol: JSON + newline       │
│  │  ┌─────────────────────────┐  │ │ │    │    Mode: Full-duplex              │ 
│  │  │ - Listen on same conn   │  │ │ │    └───────────────────────────────────┘
│  │  │ - Parse commands:       │  │ │ │                      │
│  │  │   • "restart"           │  │ │ │                      ▼
│  │  │   • "shutdown"          │  │ │ │    ┌─────────────────────────────────────┐
│  │  │   • JSON {"action":...} │◄─┼─┼─┘    │  COMMAND FLOW (Dashboard → Sim)     │
│  │  │ - Trigger actions       │  │ │      │  1. User clicks button              │
│  │  └─────────────────────────┘  │ │      │  2. send_command() in TCPManager    │
│  └───────────────────────────────┘ │      │  3. JSON encode + sendall()         │
│                                    │      │  4. Simulator tcp_receiver parses   │
│  ┌───────────────────────────────┐ │      │  5. Action executed (reset_evt.set) │
│  │  DATA SOURCE                  │ │      └─────────────────────────────────────┘
│  │  test_data/*.txt files        │ │
│  │  - temp_data.txt              │ │      ┌──────────────────────────────────────┐
│  │  - optical_data.txt           │ │      │  DATA FLOW (Simulator → Dashboard)   │
│  │  - press_data.txt             │ │      │  1. Sensor thread reads file         │
│  │  - speed_data.txt             │ │      │  2. Adds to shared data_queue        │
│  │  - vib_data.txt               │ │      │  3. TCP transmitter gets from queue  │
│  └───────────────────────────────┘ │      │  4. Sends JSON packet over network   │
│                                    │      │  5. TCP Manager receives in QThread  │
└────────────────────────────────────┘      │  6. Emits data_received signal       │
                                            │  7. SensorDashboard.process_packet() │
                                            │  8. Update UI + check alarms         │
                                            └──────────────────────────────────────┘
```

### Detailed Threading Model

```
SIMULATOR PROCESS
═════════════════
Main Thread (Keep-Alive)
│
├─► Worker Thread 1: temp.run_simulation()
│   ├─ while running_evt.is_set():
│   │   ├─ for value in temp_data.txt:
│   │   │   ├─ Check reset_evt → break if set
│   │   │   ├─ Add fault randomly (2%)
│   │   │   ├─ data_queue.put(packet)
│   │   │   └─ time.sleep(interval)
│   │   └─ Loop back or send FAULTY packets
│   └─ Thread exits when running_evt cleared
│
├─► Worker Thread 2-5: (optical, press, speed, vib) - Same logic
│
├─► TCP Transmitter Thread
│   ├─ socket.bind(127.0.0.1:5000)
│   ├─ socket.listen(1)
│   ├─ conn, addr = socket.accept()
│   ├─ Start tcp_receiver thread with conn
│   └─ while running_evt.is_set():
│       ├─ packet = data_queue.get()
│       ├─ message = json.dumps(packet) + "\n"
│       └─ conn.sendall(message.encode())
│
└─► TCP Receiver Thread
    └─ while running_evt.is_set():
        ├─ raw_data = conn.recv(1024)
        ├─ Parse commands (plain text or JSON)
        ├─ if "restart": clear queue, set reset_evt
        └─ if "shutdown": os._exit(0)


DASHBOARD PROCESS
═════════════════
Main Thread (Qt Event Loop)
│
├─► SensorDashboard.__init__()
│   ├─ Load config.json
│   ├─ Initialize proc_counters, hw_counters
│   ├─ Setup UI (tables, plots, console)
│   ├─ Start watchdog_timer (3s interval)
│   └─ Create & start TCPManager thread
│
├─► TCP Manager (QThread)
│   └─ run():
│       └─ while self.running:
│           ├─ socket.connect(127.0.0.1:5000)
│           ├─ log_signal.emit("Connected")
│           └─ while self.running:
│               ├─ line = socket.makefile().readline()
│               ├─ packet = json.loads(line)
│               └─ data_received.emit(packet) → SIGNAL
│
└─► UI Event Handlers (Main Thread)
    ├─ process_packet(packet) ← Connected to data_received
    │   ├─ Reset watchdog timer
    │   ├─ Update plot curves
    │   ├─ Check process limits
    │   ├─ Check hardware status
    │   ├─ Apply leaky bucket algorithm
    │   ├─ Trigger notifications if threshold met
    │   └─ Update table + status banner
    │
    ├─ request_restart() ← Button click
    │   ├─ receiver.send_command("restart")
    │   ├─ Clear plots and alarm logs
    │   └─ Reset all counters
    │
    └─ request_shutdown() ← Button click
        ├─ Stop watchdog timer
        ├─ receiver.stop()
        └─ receiver.send_command("shutdown")
```

---

## 📦 Prerequisites

### System Requirements
- **Python**: 3.8 or higher
- **Operating System**: Windows, Linux, or macOS
- **RAM**: Minimum 2GB
- **Network**: Localhost TCP support

### Python Dependencies
```bash
PyQt6>=6.4.0
pyqtgraph>=0.13.0
plyer>=2.0.0
requests>=2.28.0
```

---

## 🚀 Installation & Setup

### Step 1: Clone or Extract Project
```bash
cd /path/to/project
```

### Step 2: Install Dependencies
```bash
pip install PyQt6 pyqtgraph plyer requests
```

**For Debian/Ubuntu systems** (if `plyer` notifications fail):
```bash
sudo apt-get install libnotify-bin
```

### Step 3: Verify Directory Structure
Ensure the following structure exists:
```
project_root/
├── config.json
├── sensors/
│   ├── __init__.py
│   └── sensors_simulator.py
├── GUI/
│   ├── __init__.py
│   ├── TCP_Manager.py
│   └── user_interface.py
├── sensors_data/
│   ├── temp_data.txt
│   ├── optical_data.txt
│   ├── press_data.txt
│   ├── speed_data.txt
│   └── vib_data.txt
└── sensors_monitor.py
```

### Step 4: Configure Discord Webhook (Optional)
1. Create a Discord webhook in your server
2. Open `GUI/user_interface.py`
3. Replace the webhook URL in the `send_discord_webhook()` method:
```python
webhook_url = "YOUR_DISCORD_WEBHOOK_URL_HERE"
```

---

## ▶️  Running Instructions

### Method 1: Using Main Entry Point (Recommended)
```bash
python sensors_monitor.py
```

### Method 2: Running Components Separately

**Terminal 1 - Start Simulator:**
```bash
cd sensors/
python sensors_simulator.py
```

**Terminal 2 - Start Dashboard:**
```bash
cd GUI/
python user_interface.py
```

### Initial Login
When the dashboard starts:
1. Enter password: `admin123`
2. Click "Unlock Console" or press Enter
3. Maintenance console becomes accessible

---

## 🔌 TCP Protocol Description

### Connection Model
- **Protocol**: TCP/IP (Transmission Control Protocol)
- **Port**: 5000 (configurable via `config.json`)
- **Host**: 127.0.0.1 (localhost)
- **Mode**: Bidirectional full-duplex communication

### Message Format

#### Simulator → Dashboard (Data Packets)
```json
{
  "id": 100,
  "sensor": "temp",
  "value": 45.3,
  "timestamp": 1704153600.123,
  "status": "OK"
}
```

**Fields:**
- `id` (int): Unique sensor identifier
- `sensor` (string): Sensor name
- `value` (float): Current reading
- `timestamp` (float): UNIX epoch timestamp
- `status` (string): "OK" or "FAULTY"

#### Dashboard → Simulator (Commands)
```json
{
  "action": "restart",
  "params": {},
  "timestamp": 1704153600.456
}
```

**Supported Actions:**
- `restart`: Reset all sensor threads and clear queue
- `shutdown`: Graceful termination of simulator process

### Communication Flow

```
1. HANDSHAKE
   Dashboard → [SYN] → Simulator
   Simulator → [SYN-ACK] → Dashboard
   Dashboard → [ACK] → Simulator
   ✓ Connection Established

2. DATA STREAMING
   Simulator → [JSON + "\n"] → Dashboard (continuous)
   
3. COMMAND EXECUTION
   Dashboard → [JSON + "\n"] → Simulator (on-demand)
   
4. DISCONNECTION
   Dashboard → [FIN] → Simulator
   Simulator → [FIN-ACK] → Dashboard
```

### Error Handling
- **Broken Pipe**: Automatic reconnection with 2-second backoff
- **Connection Reset**: Dashboard logs error and attempts reconnect
- **Timeout**: 3-second watchdog triggers "OFFLINE" status
- **Malformed JSON**: Logged and discarded (simulator continues)

---

## 📚 API Documentation

### Communication Protocol Between Simulator & Dashboard

#### Overview
The system uses a **client-server TCP model** where:
- **Simulator = Server** (binds to port, waits for connection)
- **Dashboard = Client** (initiates connection)
- **Protocol = JSON over TCP** with newline delimiters
- **Communication = Full-duplex** (bidirectional data flow)

---

### Message Format Specifications

#### 1. Simulator → Dashboard (Data Stream)

**Packet Structure:**
```json
{
  "id": 100,
  "sensor": "temp",
  "value": 45.3,
  "timestamp": 1704153600.123,
  "status": "OK"
}
```

**Field Specifications:**

| Field | Type | Description | Example Values |
|-------|------|-------------|----------------|
| `id` | int | Unique sensor identifier from config.json | 100, 200, 300, 400, 500 |
| `sensor` | string | Sensor name (matches test_data filename) | "temp", "optical", "press" |
| `value` | float | Current sensor reading | 45.3, 78.9, 0.42 |
| `timestamp` | float | UNIX epoch time (seconds since 1970) | 1704153600.123 |
| `status` | string | Hardware reliability indicator | "OK" or "FAULTY" |

**Transmission Details:**
- **Encoding:** UTF-8
- **Delimiter:** Single newline character `\n`
- **Rate:** Determined by sensor `interval` in config.json
- **Reliability:** No acknowledgment (fire-and-forget)

**Python Implementation (Simulator Side):**
```python
# In tcp_transmitter() static method
data = SensorsSimulator.data_queue.get()
message = json.dumps(data) + "\n"
conn.sendall(message.encode('utf-8'))
```

**Python Implementation (Dashboard Side):**
```python
# In TCPManager.run() method
f = socket.makefile('r')
line = f.readline()  # Blocks until newline received
packet = json.loads(line)
self.data_received.emit(packet)  # Qt signal to main thread
```

---

#### 2. Dashboard → Simulator (Commands)

**Command Structure:**
```json
{
  "action": "restart",
  "params": {},
  "timestamp": 1704153600.456
}
```

**Field Specifications:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | string | Yes | Command type ("restart" or "shutdown") |
| `params` | dict | No | Reserved for future use (currently empty) |
| `timestamp` | float | Yes | Client-side command timestamp |

**Supported Actions:**

| Action | Description | Simulator Response |
|--------|-------------|-------------------|
| `restart` | Reset all sensor threads | Clears data_queue, sets reset_evt, logs restart |
| `shutdown` | Terminate simulator process | Calls os._exit(0) immediately |

**Alternative Plain Text Format:**
The simulator also accepts bare strings for backward compatibility:
```
restart\n
shutdown\n
```

**Python Implementation (Dashboard Side):**
```python
# In TCPManager.send_command() method
command = {
    "action": action,
    "params": params or {},
    "timestamp": time.time()
}
message = json.dumps(command) + "\n"
self._socket.sendall(message.encode('utf-8'))
```

**Python Implementation (Simulator Side):**
```python
# In tcp_receiver() static method
raw_data = conn.recv(1024).decode('utf-8')
for line in raw_data.strip().split('\n'):
    if line == "restart":
        SensorsSimulator._trigger_restart()
    elif line == "shutdown":
        os._exit(0)
    else:
        try:
            cmd = json.loads(line)
            if cmd.get('action') == "restart":
                SensorsSimulator._trigger_restart()
        except json.JSONDecodeError:
            pass  # Ignore malformed data
```

---

### Communication Sequence Diagrams

#### Startup Handshake
```
SIMULATOR                              DASHBOARD
    |                                      |
    | 1. socket.bind(127.0.0.1:5000)      |
    | 2. socket.listen(1)                 |
    | 3. Waiting for connection...        |
    |                                      | 4. socket.connect(127.0.0.1:5000)
    | <────────── TCP SYN ────────────── |
    | ──────────── SYN-ACK ────────────► |
    | <────────── ACK ───────────────── |
    |                                      |
    | 5. Connection established           | 6. Log: "Connected to Simulator"
    | 6. Start tcp_receiver thread        |
    | 7. Begin transmitting data          | 7. Begin receiving loop
    |                                      |
```

#### Normal Data Flow
```
SIMULATOR                              DASHBOARD
    |                                      |
[Sensor Thread]                      [TCP Manager Thread]
    | 1. Read value from file             |
    | 2. Add fault (2% chance)            |
    | 3. data_queue.put(packet)           |
    |                                      |
[TCP Transmitter]                          |
    | 4. data_queue.get()                 |
    | 5. JSON encode + "\n"               |
    | ──────── {"id":100,...}\n ────────► | 6. readline()
    |                                      | 7. JSON decode
    |                                      | 8. emit data_received(packet)
    |                                      |
    |                                 [Main Thread]
    |                                      | 9. process_packet()
    |                                      | 10. Update UI
    |                                      | 11. Check alarms
    |                                      | 12. Send notifications
    |                                      |
```

#### Command Execution (Restart)
```
DASHBOARD                              SIMULATOR
    |                                      |
[User Action]                              |
    | 1. Click "Restart" button           |
    | 2. request_restart()                |
    |                                      |
[TCP Manager]                              |
    | 3. send_command("restart")          |
    | 4. JSON encode                      |
    | ───── {"action":"restart"}\n ─────► |
    |                                      |
    |                                 [TCP Receiver]
    |                                      | 5. recv(1024)
    |                                      | 6. Parse JSON
    |                                      | 7. _trigger_restart()
    |                                      |
    |                                      | 8. Clear data_queue
    |                                      | 9. reset_evt.set()
    |                                      |
    |                                 [Sensor Threads]
    |                                      | 10. Detect reset_evt
    |                                      | 11. Break from loop
    |                                      | 12. Reset to start of data
    |                                      | 13. reset_evt.clear()
    |                                      |
[Dashboard]                                |
    | 14. Clear plots                     |
    | 15. Clear alarm logs                |
    | 16. Reset counters                  |
    |                                      |
```

#### Connection Loss & Recovery
```
SIMULATOR                              DASHBOARD
    |                                      |
    | ───── Data packet ─────────────────► | 1. Received OK
    | ───── Data packet ─────────────────► | 2. Reset watchdog (3s)
    |                                      |
    | [CRASH or network issue]            |
    X                                      | 3. readline() blocks
    |                                      | 4. Watchdog timer expires
    |                                      | 5. handle_connection_loss()
    |                                      | 6. UI: "SYSTEM OFFLINE"
    |                                      |
    | [Simulator restarted]               |
    | socket.listen()                     |
    |                                      | 7. Connection fails
    |                                      | 8. except: log error
    |                                      | 9. time.sleep(2)
    |                                      | 10. Retry connection
    | <────────── TCP SYN ────────────── |
    | ──────────── SYN-ACK ────────────► |
    |                                      | 11. Log: "Reconnected"
    | ───── Resume data stream ─────────► |
```

---

### API Reference by Component

### 1. TCPManager Class (GUI/TCP_Manager.py)

**Purpose:** Handles network communication in a separate QThread to prevent UI freezing.

#### Constructor
```python
def __init__(self, host='127.0.0.1', port=5000)
```

**Behavior:**
- Loads `config.json` to get actual host/port
- Initializes socket to `None`
- Sets `running = True` flag

**Attributes:**
- `_socket` (socket.socket): Active connection object
- `running` (bool): Controls thread loop
- `host` (str): Simulator IP address
- `port` (int): Simulator TCP port

---

#### run() - Main Thread Loop
```python
def run(self)
```

**Description:** Background worker that maintains connection and receives data.

**Algorithm:**
```
while running:
    try:
        Connect to simulator
        Create file-like object from socket
        while running:
            Read line (blocks until newline)
            Parse JSON
            Emit data_received signal
    except Exception:
        Log error
        Sleep 2 seconds
        Retry connection
    finally:
        Close socket
```

**Signals Emitted:**
- `data_received(dict)`: Parsed sensor packet
- `log_signal(str)`: Status/error messages

**Thread Safety:** Uses Qt signal/slot mechanism for thread-safe UI updates.

---

#### send_command() - Outbound Communication
```python
def send_command(self, action, params=None) -> bool
```

**Parameters:**
- `action` (str): "restart" or "shutdown"
- `params` (dict, optional): Reserved for future use

**Returns:**
- `True`: Command sent successfully
- `False`: No active connection or send failed

**Error Handling:**
- Checks if `_socket` exists
- Catches exceptions and logs via `log_signal`
- Returns False on any failure

**Example Usage:**
```python
# In SensorDashboard class
self.receiver.send_command("restart")
self.receiver.send_command("shutdown")
```

---

#### stop() - Graceful Shutdown
```python
def stop(self)
```

**Actions:**
1. Set `running = False` to exit loops
2. Shutdown socket for reading/writing
3. Close socket
4. Call `quit()` to stop QThread

**Called By:** `request_shutdown()` in dashboard

---

### 2. SensorsSimulator Class (sensors/sensors_simulator.py)

**Purpose:** Multi-threaded sensor data generator with TCP server.

#### Class Variables (Shared State)
```python
data_queue = queue.Queue()        # Thread-safe FIFO
fault_probability = 0.02          # 2% FAULTY injection rate
reset_evt = threading.Event()     # Global reset signal
running_evt = threading.Event()   # Master kill switch
```

**Why Static?**
- Shared across all sensor instances
- Enables thread coordination without locks
- Single source of truth for system state

---

#### Constructor
```python
def __init__(self, sensor_id: int, name: str, interval: float)
```

**Instance Variables:**
- `self.id`: Unique sensor identifier
- `self.name`: Sensor name (must match test_data file)
- `self.interval`: Seconds between readings

---

#### run_simulation() - Sensor Thread Worker
```python
def run_simulation(self) -> None
```

**Lifecycle:**
```
1. Load test_data/{name}_data.txt
2. while running_evt.is_set():
    3. for value in file:
        4. Check reset_evt → break if True
        5. Generate status (OK or FAULTY)
        6. Create packet
        7. data_queue.put(packet)
        8. time.sleep(interval)
    9. if reset_evt: clear flag and restart loop
    10. else: send FAULTY packets until reset
```

**Reset Behavior:**
- Only sensor ID 100 clears `reset_evt` to prevent race conditions
- All sensors detect the event and restart simultaneously

**Fault Injection:**
```python
status = "FAULTY" if random.random() < 0.02 else "OK"
```

---

#### tcp_transmitter() - Server Thread
```python
@staticmethod
def tcp_transmitter() -> None
```

**Responsibilities:**
1. Bind socket to configured host/port
2. Listen for single client connection
3. Spawn `tcp_receiver` thread with same connection
4. Continuously transmit queued packets

**Code Flow:**
```python
with socket.socket() as s:
    s.bind((HOST, PORT))
    s.listen(1)
    conn, addr = s.accept()
    
    # Start command listener
    threading.Thread(target=tcp_receiver, args=(conn,)).start()
    
    while running_evt.is_set():
        data = data_queue.get()
        message = json.dumps(data) + "\n"
        conn.sendall(message.encode('utf-8'))
```

---

#### tcp_receiver() - Command Listener
```python
@staticmethod
def tcp_receiver(conn) -> None
```

**Purpose:** Parse incoming commands and trigger actions.

**Parsing Strategy:**
1. Try plain text match first (fast path)
2. Fall back to JSON parsing (flexible)
3. Ignore unrecognized data

**Command Handlers:**
- `restart`: Calls `_trigger_restart()`
- `shutdown`: Calls `os._exit(0)` (hard kill)

---

#### _trigger_restart() - Internal Helper
```python
@staticmethod
def _trigger_restart()
```

**Actions:**
1. Clear `data_queue` of all pending packets
2. Set `reset_evt` to signal sensor threads
3. Log restart event

**Why Separate Method?**
- Reduces code duplication
- Allows future expansion (e.g., logging, validation)

---

### 3. SensorDashboard Class (GUI/user_interface.py)

#### process_packet() - Main Data Handler
```python
def process_packet(self, packet: dict)
```

**Connected To:** `TCPManager.data_received` signal

**Processing Pipeline:**
```
1. Reset watchdog timer (connection alive)
2. Extract sensor name, value, status
3. Append value to plot deque (40 samples)
4. Update PyQtGraph curve
5. Check process limits (min/max from config)
6. Determine process_status ("OK", "High Limit", "Low Limit")
7. Apply leaky bucket to proc_counters
8. Apply cumulative tracking to hw_counters
9. Trigger notifications if thresholds exceeded
10. Update table row with color coding
11. Refresh system status banner
```

**Alarm Logic:**
```python
# Process alarms (leaky bucket)
if val > limit['high'] or val < limit['low']:
    proc_counters[name] += 1
else:
    proc_counters[name] = max(0, proc_counters[name] - 1)

if proc_counters[name] >= 5 and not proc_notified[name]:
    send_notification()
    proc_notified[name] = True

# Hardware alarms (cumulative)
if hw_status == "FAULTY":
    hw_counters[name] += 1

if hw_counters[name] >= 15 and not hw_notified[name]:
    send_maintenance_alert()
    hw_counters[name] = 0  # Reset for next batch
```

---

#### Communication Methods

##### request_restart()
```python
def request_restart(self)
```

**Full Sequence:**
1. `receiver.send_command("restart")` → Simulator resets
2. `clear_alarm_log()` → Clears alarm table
3. `live_log.clear()` → Clears console
4. Clear all plot data deques
5. Reset `previous_state` to "OK"
6. Reset all alarm counters

---

##### request_shutdown()
```python
def request_shutdown(self)
```

**Confirmation:** QMessageBox with Yes/No buttons

**Shutdown Order (Critical):**
1. Set `is_shutting_down = True` flag
2. Stop watchdog timer
3. Call `receiver.stop()` (stops reconnection)
4. Send `"shutdown"` command to simulator
5. Update UI to offline state
6. Disable all action buttons

**Why This Order?**
- Watchdog must stop first to prevent false "OFFLINE" alerts
- TCP stop prevents reconnection during shutdown
- Command sent after TCP stopped (uses existing connection)

---

#### Notification Methods

##### send_desktop_notification()
```python
def send_desktop_notification(self, sensor, value, alarm_type)
```

**Platform Support:**
- Windows: Native toast notifications
- Linux: libnotify (requires system package)
- macOS: Notification Center

**Timeout:** 10 seconds

---

##### send_discord_webhook()
```python
def send_discord_webhook(self, sensor, value, alarm_type)
```

**Implementation:** Threaded POST request to avoid UI blocking

**Embed Colors:**
- Red (15158332): Critical process alarms
- Yellow (15844367): Maintenance/hardware alarms

**Webhook Format:**
```json
{
  "embeds": [{
    "title": "🚨 SENSOR ALERT: TEMP",
    "description": "**Status:** CRITICAL\n**Value:** `78.23`",
    "color": 15158332,
    "footer": {"text": "Logged at: 14:32:45"}
  }]
}
```

---

## 🗂️ Project Structure

```
project_root/
│
├── config.json                    # System configuration
│   ├─► network settings (host, port)
│   └─► sensor definitions (id, name, limits, interval)
│
├── sensors/                       # Simulator package
│   ├── __init__.py
│   └── sensors_simulator.py       # Multi-threaded sensor engine
│       ├─► SensorsSimulator class
│       ├─► TCP transmitter/receiver
│       └─► Data queue management
│
├── GUI/                           # Dashboard package
│   ├── __init__.py
│   ├── TCP_Manager.py             # Network communication layer
│   │   └─► QThread-based TCP client
│   └── user_interface.py          # Main GUI application
│       ├─► SensorDashboard (QMainWindow)
│       ├─► Real-time plotting
│       ├─► Alarm management
│       └─► Notification system
│
├── test_data/                     # Sensor data files
│   ├── temp_data.txt              # Temperature readings
│   ├── optical_data.txt           # Optical sensor values
│   ├── press_data.txt             # Pressure measurements
│   ├── speed_data.txt             # Speed readings
│   └── vib_data.txt               # Vibration levels
│
├── sensors_monitor.py             # Main entry point
│   └─► Launches simulator + dashboard
│
├── simulator_test_suit.py         # Simulator unit tests
├── gui_test_suit.py               # GUI component tests
│
└── industrial_monitor.log         # Auto-generated runtime log
```

---

## ⚙️ Configuration

### config.json Structure

```json
{
  "network": {
    "host": "127.0.0.1",
    "port": 5000
  },
  "sensors": [
    {
      "id": 100,
      "name": "temp",
      "min": 20,
      "max": 80,
      "interval": 5
    }
  ]
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `network.host` | string | Simulator bind address |
| `network.port` | int | TCP port number |
| `sensors[].id` | int | Unique sensor identifier |
| `sensors[].name` | string | Sensor name (must match test_data file) |
| `sensors[].min` | float | Low process limit |
| `sensors[].max` | float | High process limit |
| `sensors[].interval` | float | Sampling period (seconds) |

### Adding New Sensors

1. Add entry to `config.json`:
```json
{
  "id": 600,
  "name": "humidity",
  "min": 30,
  "max": 70,
  "interval": 4
}
```

2. Create data file: `test_data/humidity_data.txt`
```
45.2
48.1
51.3
...
```

3. Restart system - sensor auto-detected!

---

## 🎯 Advanced Features

### Intelligent Alarm Throttling

#### Leaky Bucket Algorithm (Process Alarms)
```python
PROC_THRESHOLD = 5  # Consecutive violations needed

if sensor_exceeds_limit:
    counter += 1
else:
    counter -= 1  # Leak rate: 1 per good reading

if counter >= PROC_THRESHOLD:
    send_notification()  # Critical alert
```

**Purpose:** Prevents alert spam from brief spikes while catching sustained problems.

---

#### Cumulative Tracking (Hardware Alarms)
```python
HW_THRESHOLD = 15  # Total FAULTY readings

if sensor_status == "FAULTY":
    hw_counter += 1

if hw_counter >= HW_THRESHOLD:
    send_maintenance_alert()
    hw_counter = 0  # Reset for next batch
```

**Purpose:** Detects unreliable sensors without alerting on every hiccup.

---

### Connection Watchdog

Monitors data flow health:
```python
watchdog_timer.setInterval(3000)  # 3 seconds

def handle_timeout():
    status_label.setText("⚠️ SYSTEM OFFLINE")
    log("CONNECTION LOST")
```

**Reset Condition:** Any new packet arrival restarts timer.

---

### Persistent Logging

All events logged to `industrial_monitor.log`:
```
[2026-01-01 14:32:45] Engineer Authenticated.
[2026-01-01 14:33:12] NOTIFICATION SENT: temp (CRITICAL: Process Limit Exceeded)
[2026-01-01 14:35:01] --- SYSTEM RESTART INITIATED ---
```

**Retention:** Append-only (manual cleanup required).

---

## 🚧 Future Enhancements

### Short-Term Improvements
- [ ] **Multi-Dashboard Support**: Allow multiple GUIs to connect simultaneously
- [ ] **Historical Data Storage**: SQLite database for long-term trend analysis
- [ ] **Advanced Plotting**: Zoom, pan, and time-range selection on graphs
- [ ] **User Management**: Role-based access control (Admin/Engineer/Operator)
- [ ] **Email Alerts**: SMTP integration for critical alarms

### Medium-Term Goals
- [ ] **Web Interface**: Flask/Django dashboard for remote browser access
- [ ] **REST API**: RESTful endpoints for third-party integrations
- [ ] **Machine Learning**: Anomaly detection using trained models
- [ ] **Report Generation**: Automated PDF/HTML shift reports
- [ ] **Cloud Integration**: AWS IoT Core or Azure IoT Hub connectivity

### Long-Term Vision
- [ ] **Predictive Maintenance**: Failure prediction using historical patterns
- [ ] **Mobile App**: iOS/Android companion app with push notifications
- [ ] **Multi-Site Deployment**: Centralized monitoring of distributed factories
- [ ] **Edge Computing**: On-device analytics to reduce network load
- [ ] **Digital Twin Integration**: 3D visualization of production line

---

## 📄 License

This project is provided as-is for educational and industrial prototyping purposes.

---

## 🤝 Contributing

Contributions welcome! Please follow these guidelines:
1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## 📧 Support

For issues or questions:
- Check [Troubleshooting](#troubleshooting) section
- Review `industrial_monitor.log`
- Open GitHub issue with logs attached

---

**Version:** 3.0 Final Prototype  
**Last Updated:** January 2026  
**Maintainer:** Youssef Hasan
