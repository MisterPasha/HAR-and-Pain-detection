import asyncio
import struct
import numpy as np
from bleak import BleakScanner, BleakClient
import threading
import matplotlib.pyplot as plt
from collections import Counter
import time


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.connected_devices_names = []     # Record names of connected devices
        self.RFDUINO_NAMES = ["Head", "RArm", "RShank", "RThigh", "Back", "LShank"]  # List of all RFduino names
        self.RFDUINO_NAME_TO_UUID = {         # Get uuid by device name
            "Head": "12340015-cbed-76db-9423-74ce6ab55dee",
            "RArm": "12340015-cbed-76db-9423-74ce6ab52dee",
            "RShank": "12340015-cbed-76db-9423-74ce6ab59dee",
            "LShank": "12340015-cbed-76db-9423-74ce6ab57dee",
            "Back": "12340015-cbed-76db-9423-74ce6ab56dee",
            "RThigh": "12340015-cbed-76db-9423-74ce6ab51dee"
        }
        self.RFDUINO_UUID_TO_NAME = {
            "12340015-cbed-76db-9423-74ce6ab55dee": "Head",
            "12340015-cbed-76db-9423-74ce6ab52dee": "RArm",
            "12340015-cbed-76db-9423-74ce6ab59dee": "RShank",
            "12340015-cbed-76db-9423-74ce6ab57dee": "LShank",
            "12340015-cbed-76db-9423-74ce6ab56dee": "Back",
            "12340015-cbed-76db-9423-74ce6ab51dee": "RThigh"
        }
        self.RFDUINO_ADDRESS_TO_UUID = {}     # Get uuid by BleakClient address
        self.is_running = False               # Flag for running function
        self.is_streaming = False
        self.status_var = status_var          # Connection Status String
        self.device_data = {}
        self.time_data = [0]
        self.time_intervals = []
        self.start_time = None
        self.end_time = None
        self.connect_time = None

    async def data_handler(self, sender, data):
        """Callback to handle incoming data from RFduino."""
        #print(f"Data packet Size: {len(data)}")
        # Unpack the received 20-byte data
        try:
            ax, ay, az, gx, gy, gz, timestamp = struct.unpack("<hhhhhhI", data)
            #print(f"Accelerometer: ax={ax}, ay={ay}, az={az}")
            #print(f"Timestamp: {timestamp} ms")
            #print(f"Gyroscope: gx={gx}, gy={gy}, gz={gz}")
            #self.time_intervals.append(timestamp - self.time_data[-1])
            #self.time_data.append(timestamp)
            self.device_data.setdefault(sender.uuid, []).append(timestamp)
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
        self.connect_time = time.time() * 1000  # Convert seconds to milliseconds
        await asyncio.gather(*tasks)  # Connect to all devices concurrently

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
            # Start streaming each RFduino simultaneously
            tasks = [client.start_notify(self.RFDUINO_ADDRESS_TO_UUID[client.address], self.data_handler) for
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
        if self.connected_devices:
            # Start the streaming loop in a new thread
            threading.Thread(target=self._run_streaming_loop, daemon=True).start()
        else:
            self.status_var.set("Connect to devices first")

    def stop_streaming(self):
        self.is_streaming = False
        self.plot_data4()

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
        for k, v in self.device_data.items():
            intervals = []
            print("")
            print(f"Device: {self.RFDUINO_UUID_TO_NAME[k]}")
            print(f"True Connection time: {self.connect_time}")
            print(f"Starting time: {v[0]}")
            print(f"Ending time: {v[-1]}")
            for i in range(0, len(v)-1):
                intervals.append(v[i+1] - v[i])
            print(f"Max/Min interval: {max(intervals)}/{min(intervals)}")
            print("")
