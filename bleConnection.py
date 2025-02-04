import asyncio
import struct
import numpy as np
from bleak import BleakScanner, BleakClient
import threading
import matplotlib.pyplot as plt
from collections import Counter
import time
import csv


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.connected_devices_names = []     # Record names of connected devices
        self.RFDUINO_NAMES = ["Head", "RArm", "RShank", "RThigh", "Back", "LShank", "LArm"]  # List of all RFduino names
        self.RFDUINO_NAME_TO_UUID = {         # Get uuid by device name
            "Head": "12340015-cbed-76db-9423-74ce6ab55dee",
            "RArm": "12340015-cbed-76db-9423-74ce6ab52dee",
            "RShank": "12340015-cbed-76db-9423-74ce6ab59dee",
            "LShank": "12340015-cbed-76db-9423-74ce6ab57dee",
            "Back": "12340015-cbed-76db-9423-74ce6ab56dee",
            "RThigh": "12340015-cbed-76db-9423-74ce6ab51dee",
            "LArm": "12340015-cbed-76db-9423-74ce6ab53dee"
        }
        self.RFDUINO_UUID_TO_NAME = {
            "12340015-cbed-76db-9423-74ce6ab55dee": "Head",
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

    async def data_handler_for_timestamping(self, sender, data):
        """Callback to handle incoming data from RFduino."""
        # print(f"Data packet Size: {len(data)}")
        # Unpack received data 20 bytes
        try:
            ax, ay, az, gx, gy, gz, timestamp = struct.unpack("<hhhhhhI", data)
            t_received = time.time()*1000 - self.connect_time
            self.receive_times.setdefault(sender.uuid, []).append(t_received)
            if not self.time_synced:
                if len(self.device_data.keys()) > 5:
                    self.time_synced = True
                self.syncing_intervals.setdefault(sender.uuid, int(timestamp - self.checkpoint))

            self.device_data.setdefault(self.RFDUINO_UUID_TO_NAME[sender.uuid], []).append(timestamp - self.syncing_intervals[sender.uuid])
        except struct.error as e:
            print(f"Error unpacking data: {e}")

    def data_handler_for_sensor_interval_data(self, sender, data):
        try:
            accel_gyro_interval, mag_interval = struct.unpack("<II", data)
            self.sensor_intervals.setdefault(self.RFDUINO_UUID_TO_NAME[sender.uuid], []).append([accel_gyro_interval, mag_interval])
        except struct.error as e:
            print(f"Error unpacking data: {e}")

    def data_handler_for_sensor_interval_data_grouped(self, sender, data):
        try:
            group_interval = struct.unpack("<I", data)
            self.sensor_intervals.setdefault(self.RFDUINO_UUID_TO_NAME[sender.uuid], []).append(group_interval)
        except struct.error as e:
            print(f"Error unpacking data: {e}")

    def data_handler_for_euler_angles(self, sender, data):
        decoded_data = data.decode('utf-8')
        print(decoded_data)
        parts = decoded_data.split()
        self.status_var.set(f"x: {parts[1]}   y: {parts[2]}")
        self.device_data.setdefault(sender.uuid, []).append(parts)

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
            tasks = [client.start_notify(self.RFDUINO_ADDRESS_TO_UUID[client.address], self.data_handler_for_timestamping) for
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
        self.save_sensor_timestamps_as_csv()

    def align_sensor_data_by_timestamp(self, sensor_data, truth_timestamps):
        # Extract timestamps and data values
        timestamps = np.array([ts for ts, _ in sensor_data])
        values = np.array([val for _, val in sensor_data])

        # Create an aligned array to hold the final values
        aligned_values = []

        # For each ground truth timestamp, find the closest sensor timestamp
        for t in truth_timestamps:
            # Find the index of the closest timestamp in sensor data
            closest_index = np.argmin(np.abs(timestamps - t))
            closest_time = timestamps[closest_index]

            # Check if the closest timestamp is within a reasonable range
            if abs(closest_time - t) <= 5:  # Allowable deviation (e.g., within 5 ms)
                aligned_values.append(values[closest_index])
                # Remove this timestamp and value to avoid duplicates in the future
                timestamps = np.delete(timestamps, closest_index)
                values = np.delete(values, closest_index)
            else:
                # If no close timestamp found, interpolate the value
                if closest_index == 0:
                    # If the closest index is the first element, use it directly
                    aligned_values.append(values[closest_index])
                elif closest_index == len(timestamps) - 1:
                    # If the closest index is the last element, use it directly
                    aligned_values.append(values[closest_index])
                else:
                    # Interpolate between the two nearest points
                    t1, t2 = timestamps[closest_index - 1], timestamps[closest_index]
                    v1, v2 = values[closest_index - 1], values[closest_index]
                    interpolated_value = np.interp(t, [t1, t2], [v1, v2])
                    aligned_values.append(interpolated_value)

        return aligned_values

    def plot_data(self):
        # Create a figure
        plt.figure(figsize=(12, 8))

        # Iterate through the dictionary and plot data for each UUID
        for uuid, values in self.device_data.items():
            name = self.RFDUINO_UUID_TO_NAME[uuid]
            # Extract timestamp, x angle, and y angle
            timestamps = [int(item[0]) for item in values]
            min_time = min(timestamps)
            timestamps_in_seconds = [(t - min_time) / 1000 for t in timestamps]  # Convert to seconds
            x_angles = [int(item[1]) for item in values]
            y_angles = [int(item[2]) for item in values]
            z_angles = [int(item[3]) for item in values]

            # Plot x angles
            plt.plot(timestamps_in_seconds, x_angles, label=f"{name} - X Angle", linestyle='-')
            # Plot y angles
            plt.plot(timestamps_in_seconds, y_angles, label=f"{name} - Y Angle", linestyle='-')
            # Plot z angles
            plt.plot(timestamps_in_seconds, z_angles, label=f"{name} - Z Angle", linestyle='-')

        # Add legend
        plt.legend()

        # Add titles and labels
        plt.title("Comparison of two devices")
        plt.xlabel("Seconds")
        plt.ylabel("Angles (degrees)")

        # Show grid for better readability
        plt.grid(True)

        # Show the plot
        plt.show()

    def plot_data2(self):
        # Create a figure
        plt.figure(figsize=(12, 8))

        start = []
        end = []

        # Iterate through the dictionary and plot data for each UUID
        for uuid, values in self.device_data.items():
            name = self.RFDUINO_UUID_TO_NAME[uuid]
            # Extract timestamp, x angle, and y angle
            timestamps = [int(item[0]) for item in values]
            min_time = min(timestamps)
            timestamps_in_seconds = [(t - min_time) / 1000 for t in timestamps]  # Convert to seconds
            x_angles = [int(item[1]) for item in values]
            y_angles = [int(item[2]) for item in values]
            #z_angles = [int(item[3]) for item in values]

            # Plot x angles
            #plt.plot(timestamps_in_seconds, x_angles, label=f"Trunk - X Angle", linestyle='-')
            # Plot y angles
            plt.plot(timestamps_in_seconds, y_angles, label=f"Trunk - Y Angle", linestyle='-')
            # Plot z angles
            #plt.plot(timestamps, z_angles, label=f"{name} - Z Angle", linestyle='-')


        # Add legend
        plt.legend()

        # Add titles and labels
        plt.title("Y Angle Over Time")
        plt.xlabel("Seconds")
        plt.ylabel("Angles (degrees)")

        # Show grid for better readability
        plt.grid(True)

        # Show the plot
        plt.show()

    def plot_data3(self):
        plt.figure(figsize=(12, 8))
        intervals = self.time_intervals
        del intervals[0]
        indexes = [i for i in range(len(intervals))]
        plt.plot(indexes, intervals, linestyle='-')
        counter = Counter(intervals)
        most_common = counter.most_common(1)[0]
        print()
        print(f"Minimum Interval: {min(intervals)}")
        print(f"Maximum Interval: {max(intervals)}")
        print(f"Mean Interval: {sum(intervals) / len(intervals)}")
        print(f"Most often Interval: {most_common[0]}")
        # Add legend
        plt.legend()
        # Add titles and labels
        plt.title("Intervals")
        plt.xlabel("Sequence")
        plt.ylabel("Interval")

        # Show grid for better readability
        plt.grid(True)

        # Show the plot
        plt.show()

    def plot_data4(self):
        differences = {}
        min_len = min([len(v) for _, v in self.receive_times.items()])
        x_axis = self.device_data["12340015-cbed-76db-9423-74ce6ab52dee"]
        for k, v in self.device_data.items():
            intervals = []
            print("")
            print(f"Device: {self.RFDUINO_UUID_TO_NAME[k]}")
            print(f"Starting time Sensor/Host: {v[0]} / {int(self.checkpoint)}")
            print(f"Ending time Sensor/Host: {v[-1]} / {self.stop_time}")
            print(f"Number of frames: {len(v)}")
            for i in range(0, len(v)-1):
                intervals.append(v[i+1] - v[i])
            print(f"Max/Min interval: {max(intervals)}/{min(intervals)}")
            differences.setdefault(self.RFDUINO_UUID_TO_NAME[k], [a - b for a, b in zip(self.receive_times[k], v)])
            print(f"Max/Min Diffs: {max(differences[self.RFDUINO_UUID_TO_NAME[k]])} / {min(differences[self.RFDUINO_UUID_TO_NAME[k]])}")
            print("")

        all_diffs = list(differences.values())
        mean_values = [sum(t) / len(t) for t in zip(*all_diffs)]

        plt.plot(x_axis[:min_len], mean_values, label=f"All sensors mean", linestyle='-')

        # Add legend
        plt.legend()

        # Add titles and labels
        plt.title("Send-Receive delays")
        plt.xlabel("ms")
        plt.ylabel("Mean Delay")

        # Show grid for better readability
        plt.grid(True)

        # Show the plot
        plt.show()

    def save_sensor_timestamps_as_csv(self, filename="sensor_timestamps.csv"):

        sensor_names = list(self.device_data.keys())
        header = []
        for sensor in sensor_names:
            header.append(f"{sensor}")

        rows = zip(*[self.device_data[sensor] for sensor in sensor_names])

        # Save to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Write header
            writer.writerows(rows)  # Write sensor data rows

        print(f"CSV file saved: {filename}")

    def save_sensor_intervals_as_csv(self, filename="sensor_intervals_morning.csv"):
        # Step 1: Find the minimum list length among all sensors
        min_len = min(len(values) for values in self.sensor_intervals.values())
        print(f"Min Len: {min_len}")

        # Step 2: Trim all sensor lists to the minimum length
        trimmed_intervals = {sensor: values[:min_len] for sensor, values in self.sensor_intervals.items()}

        # Step 3: Prepare CSV header (sensor names)
        sensor_names = list(trimmed_intervals.keys())
        header = []
        for sensor in sensor_names:
            header.append(f"{sensor}")

        # Step 4: Transpose data to align rows properly
        rows = zip(*[trimmed_intervals[sensor] for sensor in sensor_names])

        # Step 5: Save to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Write header
            writer.writerows(rows)  # Write sensor data rows

        print(f"CSV file saved: {filename}")

    def save_sensor_intervals_grouped_as_csv(self, filename="sensor_intervals_grouped.csv"):
        # Step 1: Find the minimum list length among all sensors
        min_len = min(len(values) for values in self.sensor_intervals.values())
        print(f"Min Len: {min_len}")

        # Step 2: Trim all sensor lists to the minimum length
        trimmed_intervals = {sensor: values[:min_len] for sensor, values in self.sensor_intervals.items()}

        # Step 3: Prepare CSV header (sensor names)
        sensor_names = list(trimmed_intervals.keys())
        header = []
        for sensor in sensor_names:
            header.append(f"{sensor}")

        # Step 4: Transpose data to align rows properly
        rows = zip(*[trimmed_intervals[sensor] for sensor in sensor_names])

        # Step 5: Save to CSV
        with open(filename, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header)  # Write header
            writer.writerows(rows)  # Write sensor data rows

        print(f"CSV file saved: {filename}")
