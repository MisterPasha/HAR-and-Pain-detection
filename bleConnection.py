import asyncio
import struct
import numpy as np
from bleak import BleakScanner, BleakClient
import threading
import matplotlib.pyplot as plt
from collections import Counter
import time
import csv
import pandas as pd


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.connected_devices_names = []     # Record names of connected devices
        self.RFDUINO_NAMES = ["Head", "RArm", "RShank", "RThigh", "Back", "LShank", "LArm"]  # List of all RFduino names
        self.RFDUINO_NAME_TO_UUID = {         # Get uuid by device name
            "RArm": "12340015-cbed-76db-9423-74ce6ab52dee",
            "RShank": "12340015-cbed-76db-9423-74ce6ab59dee",
            "LShank": "12340015-cbed-76db-9423-74ce6ab57dee",
            "Back": "12340015-cbed-76db-9423-74ce6ab56dee",
            "RThigh": "12340015-cbed-76db-9423-74ce6ab51dee",
            "LArm": "12340015-cbed-76db-9423-74ce6ab53dee"
        }
        self.RFDUINO_UUID_TO_NAME = {
            "12340015-cbed-76db-9423-74ce6ab52dee": "RArm",
            "12340015-cbed-76db-9423-74ce6ab59dee": "RShank",
            "12340015-cbed-76db-9423-74ce6ab57dee": "LShank",
            "12340015-cbed-76db-9423-74ce6ab56dee": "Back",
            "12340015-cbed-76db-9423-74ce6ab51dee": "RThigh",
            "12340015-cbed-76db-9423-74ce6ab53dee": "LArm"
        }
        self.RFDUINO_ADDRESS_TO_UUID = {}     # Get uuid by BleakClient address
        self.is_running = False               # Flag for running function
        self.is_streaming = False
        self.status_var = status_var          # Connection Status String
        self.device_data = {}
        self.connect_time = None
        self.checkpoint = None
        self.stop_time = None
        self.time_synced = False
        self.syncing_intervals = {}
        self.receive_times = {}
        self.sensor_intervals = {}  # Intervals between AccelGyro and Mag extraction intervals
        self.sensor_readings = {}

    # 1. Full 9-axis sensor data handler (accelerometer, gyroscope, magnetometer)
    def data_handler_for_sensor_readings(self, sender, data):
        """
        Handles raw 9-axis sensor data (Accel + Gyro + Mag), each as 16-bit signed integers.
        Expected BLE packet structure: 9 x int16 -> 18 bytes total
        Format: <hhhhhhhhh
        """
        try:
            ax, ay, az, gx, gy, gz, mx, my, mz = struct.unpack("<hhhhhhhhh", data)
            sensor_name = self.RFDUINO_UUID_TO_NAME[sender.uuid]
            self.sensor_readings.setdefault(sensor_name, []).append([ax, ay, az, gx, gy, gz, mx, my, mz])
        except struct.error as e:
            print(f"Error unpacking 9-axis sensor data: {e}")

    # 2. Short version (float values): used in testing/simplified packets
    def data_handler_for_sensor_readings_short(self, sender, data):
        """
        Handles simplified float sensor data (e.g., ax, gx, mx as 3 x float32).
        Expected BLE packet structure: 3 x float -> 12 bytes total
        Format: <fff
        """
        try:
            print("hey")
            ax, gx, mx = struct.unpack("<fff", data)
            sensor_name = self.RFDUINO_UUID_TO_NAME[sender.uuid]
            self.sensor_readings.setdefault(sensor_name, []).append([ax, gx, mx])
        except struct.error as e:
            print(f"Error unpacking short float sensor data: {e}")

    # 3. Timestamping for drift/misalignment experiments
    async def data_handler_for_timestamping(self, sender, data):
        """
        Handles timestamped packets: includes 6-axis int16 + uint32 timestamp.
        Format: <hhhhhhI (6 x int16 + 1 x uint32) = 16 bytes
        Used to track packet timing and assess inter-sensor alignment.
        """
        try:
            ax, ay, az, gx, gy, gz, timestamp = struct.unpack("<hhhhhhI", data)
            t_received = time.time() * 1000 - self.connect_time
            self.receive_times.setdefault(sender.uuid, []).append(t_received)

            if not self.time_synced:
                if len(self.device_data) > 5:
                    self.time_synced = True
                self.syncing_intervals.setdefault(sender.uuid, int(timestamp - self.checkpoint))

            adjusted_timestamp = timestamp - self.syncing_intervals[sender.uuid]
            sensor_name = self.RFDUINO_UUID_TO_NAME[sender.uuid]
            self.device_data.setdefault(sensor_name, []).append(adjusted_timestamp)
        except struct.error as e:
            print(f"Error unpacking timestamped data: {e}")

    # 4. Extraction intervals for AccelGyro and Magnetometer separately
    def data_handler_for_sensor_interval_data(self, sender, data):
        """
        Handles data containing timing intervals (in microseconds) between:
        - Accel/Gyro extraction
        - Magnetometer extraction
        Format: <II -> 2 x uint32
        """
        try:
            accel_gyro_interval, mag_interval = struct.unpack("<II", data)
            sensor_name = self.RFDUINO_UUID_TO_NAME[sender.uuid]
            self.sensor_intervals.setdefault(sensor_name, []).append([accel_gyro_interval, mag_interval])
        except struct.error as e:
            print(f"Error unpacking interval data: {e}")

    # 5. Extraction interval for grouped sensors (used when only one interval per cycle is sent)
    def data_handler_for_sensor_interval_data_grouped(self, sender, data):
        """
        Handles grouped extraction interval data: 1 x uint32 per packet.
        Used in cases where only one timing value is sent per read cycle.
        Format: <I
        """
        try:
            group_interval = struct.unpack("<I", data)[0]
            sensor_name = self.RFDUINO_UUID_TO_NAME[sender.uuid]
            self.sensor_intervals.setdefault(sensor_name, []).append(group_interval)
        except struct.error as e:
            print(f"Error unpacking grouped interval data: {e}")

    # 6. Euler angles handler (formatted as a decoded UTF-8 string)
    def data_handler_for_euler_angles(self, sender, data):
        """
        Handles euler angle data in UTF-8 encoded string format: "x: value y: value z: value"
        Displays X and Y in GUI and stores all parts in device_data.
        """
        try:
            decoded_data = data.decode('utf-8')
            print(decoded_data)
            parts = decoded_data.split()
            self.status_var.set(f"x: {parts[1]}   y: {parts[3]}")  # Adjust index if format differs
            self.device_data.setdefault(sender.uuid, []).append(parts)
        except Exception as e:
            print(f"Error decoding euler angles: {e}")

    async def connect_to_rfduino(self, device):
        """Function to connect to a single RFduino device and set up notifications."""
        try:
            client = BleakClient(device)  # Create persistent BleakClient instance
            await client.connect()  # Explicitly connect

            if client.is_connected:
                self.connected_devices.append(client)  # Store the connected client
                self.connected_devices_names.append(device.name)
                self.status_var.set(f"Connected to {device.name} ({device.address})")
                print(f"Connected to {device.name} ({device.address})")

                # Map device address to characteristic UUID
                self.RFDUINO_ADDRESS_TO_UUID[device.address] = self.RFDUINO_NAME_TO_UUID[device.name]

            else:
                print(f"Failed to connect to {device.name} ({device.address})")
                self.status_var.set(f"Failed to connect to {device.name}")
        except Exception as e:
            self.status_var.set(f"Failed to connect to {device.name}: {e}")
            print(f"Failed to connect to {device.name}: {e}")

    async def main(self):
        # Discover BLE devices
        devices = await BleakScanner.discover(timeout=5)  # Searches devices for 5 seconds
        #[print(d.name) for d in devices if d.name]
        print(len(devices))
        rfduino_devices = [d for d in devices if d.name in self.RFDUINO_NAMES]

        if not rfduino_devices:
            self.status_var.set("No RFduinos detected")
            return

        self.status_var.set(f"Found {len(rfduino_devices)} RFduino devices")

        # Connect to each RFduino simultaneously
        tasks = [self.connect_to_rfduino(device) for device in rfduino_devices]
        await asyncio.gather(*tasks)  # Connect to all devices concurrently
        self.connect_time = time.time() * 1000  # Convert seconds to milliseconds

        # Print final connected devices
        connected_devices = "\nConnected RFduino devices:"
        for name in self.connected_devices_names:
            connected_devices += "\n" + name
        self.status_var.set(connected_devices)

    def run(self):
        if self.is_running:
            self.status_var.set("Connection is already running")
            return  # Exit if already running

        self.is_running = True  # Set the flag to indicate that scanning has started

        # Run the asyncio event loop in a separate thread
        def run_main():
            self.status_var.set("Connecting...")
            try:
                asyncio.run(self.main())
            finally:
                self.is_running = False  # Reset flag

        threading.Thread(target=run_main).start()

    async def stream(self):
        """Keep the streaming active for all connected devices."""
        try:
            t_now = time.time() * 1000
            self.checkpoint = int(t_now - self.connect_time)

            # Start streaming each RFduino simultaneously
            tasks = [client.start_notify(self.RFDUINO_ADDRESS_TO_UUID[client.address], self.data_handler_for_sensor_readings) for
                     client in self.connected_devices]
            await asyncio.gather(*tasks)

            # Ensure the streaming loop remains active
            while self.is_streaming:
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Error during streaming: {e}")
        finally:
            # Stop streaming each RFduino simultaneously
            tasks = [client.stop_notify(self.RFDUINO_ADDRESS_TO_UUID[client.address]) for client in
                     self.connected_devices]
            await asyncio.gather(*tasks)
            self.stop_time = int(time.time() * 1000) - self.connect_time
        self.device_data = {}

    def _run_streaming_loop(self):
        """Run the asyncio event loop for the stream method."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.stream())
        except Exception as e:
            print(f"Error in streaming loop: {e}")
        finally:
            loop.close()

    def start_streaming(self):
        self.is_streaming = True
        print("Streaming Started . . .")
        if self.connected_devices:
            # Start the streaming loop in a new thread
            threading.Thread(target=self._run_streaming_loop, daemon=True).start()
        else:
            self.status_var.set("Connect to devices first")

    def stop_streaming(self):
        self.is_streaming = False
        self.stop_time = int(time.time() * 1000 - self.connect_time)
        self.save_sensor_readings_as_csv()

    def plot_data(self):
        """
        Plots X, Y, and Z Euler angles over time for all connected sensors.
        Each sensor's data is extracted from `self.device_data`, which stores
        timestamped angle readings per UUID.
        """
        plt.figure(figsize=(12, 8))

        for uuid, values in self.device_data.items():
            name = self.RFDUINO_UUID_TO_NAME[uuid]

            # Extract timestamps and convert to seconds (relative to first reading)
            timestamps = [int(item[0]) for item in values]
            min_time = min(timestamps)
            timestamps_in_seconds = [(t - min_time) / 1000 for t in timestamps]

            # Extract X, Y, Z angles from data
            x_angles = [int(item[1]) for item in values]
            y_angles = [int(item[2]) for item in values]
            z_angles = [int(item[3]) for item in values]

            # Plot all three axes
            plt.plot(timestamps_in_seconds, x_angles, label=f"{name} - X Angle")
            plt.plot(timestamps_in_seconds, y_angles, label=f"{name} - Y Angle")
            plt.plot(timestamps_in_seconds, z_angles, label=f"{name} - Z Angle")

        plt.legend()
        plt.title("Comparison of Device Euler Angles (X, Y, Z)")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Angle (degrees)")
        plt.grid(True)
        plt.show()

    def plot_data2(self):
        """
        Plots only the Y Euler angle over time for all connected sensors.
        This is useful for focused analysis of a single axis, such as trunk rotation.
        """
        plt.figure(figsize=(12, 8))

        for uuid, values in self.device_data.items():
            name = self.RFDUINO_UUID_TO_NAME[uuid]

            # Time normalization
            timestamps = [int(item[0]) for item in values]
            min_time = min(timestamps)
            timestamps_in_seconds = [(t - min_time) / 1000 for t in timestamps]

            # Only plot Y angle
            y_angles = [int(item[2]) for item in values]
            plt.plot(timestamps_in_seconds, y_angles, label=f"{name} - Y Angle")

        plt.legend()
        plt.title("Y Angle Over Time")
        plt.xlabel("Time (seconds)")
        plt.ylabel("Y Angle (degrees)")
        plt.grid(True)
        plt.show()
        plt.savefig("_plot.png", dpi=300)

    def plot_data4(self):
        """
        Analyzes timing intervals between consecutive sensor data packets for each device.
        Useful for identifying sampling jitter and evaluating synchronization stability.
        Outputs:
            - Start and end times
            - Number of frames received
            - Max/min interval between packets
            - Frequency count of interval durations
        """
        for uuid, values in self.device_data.items():
            print("\n" + "=" * 60)
            print(f"Device: {uuid} ({self.RFDUINO_UUID_TO_NAME[uuid]})")

            # Extract timestamps from sensor data (assumes index 0 contains time)
            timestamps = [int(item[0]) for item in values]

            print(f"Starting time Sensor / Host: {timestamps[0]} / {int(self.checkpoint)}")
            print(f"Ending time   Sensor / Host: {timestamps[-1]} / {self.stop_time}")
            print(f"Number of frames received: {len(timestamps)}")

            # Compute time intervals between consecutive packets
            intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]

            print(f"Max interval: {max(intervals)} ms")
            print(f"Min interval: {min(intervals)} ms")
            print(f"Interval distribution: {Counter(intervals)}")

    def save_sensor_timestamps_as_csv(self, filename="sensor_timestamps_9.csv"):
        """
        Saves the collected timestamp data from all sensors into a CSV file.

        Args:
            filename (str): Name of the output CSV file.

        Output:
            CSV file where each column contains timestamps from one sensor.
        """
        # Get list of sensor UUIDs (keys in the device_data dictionary)
        sensor_names = list(self.device_data.keys())

        # Prepare column headers (human-readable sensor names)
        header = [f"{sensor}" for sensor in sensor_names]

        # Align data by transposing rows: zip() groups data from each sensor by index
        rows = zip(*[self.device_data[sensor] for sensor in sensor_names])

        # Write data to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Write the header row
            writer.writerows(rows)  # Write each row of aligned sensor timestamps

        print(f"CSV file saved: {filename}")

    def save_sensor_intervals_as_csv(self, filename="sensor_intervals_morning.csv"):
        """
        Saves sensor interval data (e.g., time between AccelGyro and Magnetometer readings)
        into a CSV file, aligning all sensors by the shortest list length.

        Args:
            filename (str): Output CSV file name.
        """

        #  Determine the shortest interval list length across all sensors
        min_len = min(len(values) for values in self.sensor_intervals.values())
        print(f"Minimum common length: {min_len}")

        #  Trim each sensor's interval list to match the shortest length
        trimmed_intervals = {
            sensor: values[:min_len] for sensor, values in self.sensor_intervals.items()
        }

        #  Prepare the CSV header with sensor names
        sensor_names = list(trimmed_intervals.keys())
        header = [f"{sensor}" for sensor in sensor_names]

        # Transpose data — each row represents one aligned time step across all sensors
        rows = zip(*[trimmed_intervals[sensor] for sensor in sensor_names])

        # Write to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Column names
            writer.writerows(rows)  # Sensor interval values

        print(f"CSV file saved: {filename}")

    def save_sensor_intervals_grouped_as_csv(self, filename="sensor_intervals_grouped.csv"):
        """
        Saves grouped sensor interval data (e.g., one interval per read cycle) to a CSV file.
        Trims all sensors' data to the shortest length for alignment.

        Args:
            filename (str): Desired output CSV filename.
        """

        # Find the shortest interval list across all sensors
        min_len = min(len(values) for values in self.sensor_intervals.values())
        print(f"Min Len: {min_len}")

        # Trim each sensor's interval list to this minimum length for alignment
        trimmed_intervals = {
            sensor: values[:min_len] for sensor, values in self.sensor_intervals.items()
        }

        #  Generate CSV headers using sensor names
        sensor_names = list(trimmed_intervals.keys())
        header = [f"{sensor}" for sensor in sensor_names]

        #  Prepare aligned rows (each row is one timestamped interval per sensor)
        rows = zip(*[trimmed_intervals[sensor] for sensor in sensor_names])

        #  Save to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Write header row
            writer.writerows(rows)  # Write data rows

        print(f"CSV file saved: {filename}")

    def save_sensor_readings_as_csv(self, filename="sensor_data2.csv"):
        """
        Saves synchronized 9-axis IMU data (Accel, Gyro, Mag) from multiple sensors into a CSV file.
        Ensures that all sensors contribute equally by trimming to the shortest length.

        Args:
            filename (str): Output file name.
        """

        # Define the expected order of sensors (must match self.sensor_readings structure)
        sensor_order = ["RArm", "RShank", "LShank", "Back", "RThigh", "LArm"]

        # Create column headers for each sensor (9 axes per sensor)
        column_names = []
        for sensor in sensor_order:
            column_names.extend([
                f"{sensor}_ax", f"{sensor}_ay", f"{sensor}_az",
                f"{sensor}_gx", f"{sensor}_gy", f"{sensor}_gz",
                f"{sensor}_mx", f"{sensor}_my", f"{sensor}_mz"
            ])

        #  Find the smallest number of samples to ensure synchronization
        num_samples = min(len(self.sensor_readings[sensor]) for sensor in sensor_order)

        #  Build the data row-by-row in sensor order
        data = []
        for i in range(num_samples):
            row = []
            for sensor in sensor_order:
                row.extend(self.sensor_readings[sensor][i])  # Append all 9 values from this sensor
            data.append(row)

        #  Create and export DataFrame
        df = pd.DataFrame(data, columns=column_names)
        df.to_csv(filename, index=False)

        print(f"Sensor data saved to {filename}")

    def print_out_sensor_data(self):
        print(self.sensor_readings)