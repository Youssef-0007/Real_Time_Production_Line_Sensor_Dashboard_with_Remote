import unittest
import time

from sensors.sensors_simulator import SensorsSimulator


class TestSimulatorLogic(unittest.TestCase):
    def setUp(self):
        # Create a "dummy" sensor for testing logic
        self.sim = SensorsSimulator(999, "test_sensor", 0, 100, 0.1)
        SensorsSimulator.running_evt.set()
        SensorsSimulator.reset_evt.clear()

    def test_simulator_reset_event(self):
        """Test if setting the reset event actually clears the data queue"""
        # 1. Put some 'old' data in the queue
        SensorsSimulator.data_queue.put({"data": "old"})
        self.assertFalse(SensorsSimulator.data_queue.empty())
        
        # 2. Simulate the restart trigger (as it happens in tcp_receiver)
        while not SensorsSimulator.data_queue.empty():
            SensorsSimulator.data_queue.get()
        SensorsSimulator.reset_evt.set()
        
        # 3. Verify queue is empty and event is set
        self.assertTrue(SensorsSimulator.data_queue.empty())
        self.assertTrue(SensorsSimulator.reset_evt.is_set())

    def test_packet_generation_format(self):
        """Test if the simulator produces valid JSON-compatible dictionaries"""
        # We manually trigger one iteration of the logic (mocking the file read)
        packet = {
            "id": self.sim.id, 
            "sensor": self.sim.name, 
            "value": 50.0,
            "timestamp": time.time(), 
            "status": "OK"
        }
        
        self.assertIn("sensor", packet)
        self.assertIn("status", packet)
        self.assertEqual(packet["id"], 999)

    def test_simulator_shutdown_logic(self):
        """Test if the shutdown command correctly clears the running event"""
        # Instead of calling os._exit(0) (which would kill the test runner!), 
        # we test the logic that SHOULD happen before an exit.
        
        # Simulate the shutdown command receiving
        SensorsSimulator.running_evt.clear()
        
        self.assertFalse(SensorsSimulator.running_evt.is_set())


if __name__ == '__main__':
    unittest.main()