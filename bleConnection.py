import asyncio
from bleak import BleakScanner, BleakClient
import threading
import matplotlib.pyplot as plt
import time


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.connected_devices_names = []     # Record names of connected devices
        self.RFDUINO_NAMES = ["Head", "RArm"]               # List of all RFduino names
        self.RFDUINO_NAME_TO_UUID = {         # Get uuid by device name
            "Head": "12340015-cbed-76db-9423-74ce6ab55dee",
            "RArm": "12340015-cbed-76db-9423-74ce6ab52dee"
        }
        self.RFDUINO_UUID_TO_NAME = {
            "12340015-cbed-76db-9423-74ce6ab55dee": "Head",
            "12340015-cbed-76db-9423-74ce6ab52dee": "RArm"
        }
        self.RFDUINO_ADDRESS_TO_UUID = {}     # Get uuid by BleakClient address
        self.is_running = False               # Flag for running function
        self.is_streaming = False
        self.status_var = status_var          # Connection Status String
        self.device_data = {}
        self.start_time = None
        self.end_time = None

    async def data_handler(self, sender, data):
        """Callback to handle incoming data from RFduino."""
        decoded_data = data.decode('utf-8')
        parts = decoded_data.split()
        self.status_var.set(f"x: {parts[1]}   y: {parts[2]}   z: {parts[3]}")
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
        rfduino_devices = [d for d in devices if d.name in self.RFDUINO_NAMES]

        if not rfduino_devices:
            self.status_var.set("No RFduinos detected")
            return

        self.status_var.set(f"Found {len(rfduino_devices)} RFduino devices")

        # Connect to each RFduino simultaneously
        tasks = [self.connect_to_rfduino(device) for device in rfduino_devices]
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
        self.plot_data2()

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
            start.append(timestamps[0])
            end.append(timestamps[-1])
            print(f"{name} start: {timestamps[0]}    finish: {timestamps[-1]}")
            x_angles = [int(item[1]) for item in values]
            y_angles = [int(item[2]) for item in values]
            z_angles = [int(item[3]) for item in values]

            # Plot x angles
            plt.plot(timestamps, x_angles, label=f"{name} - X Angle", linestyle='-')
            # Plot y angles
            #plt.plot(timestamps, y_angles, label=f"{name} - Y Angle", linestyle='-')
            # Plot z angles
            #plt.plot(timestamps, z_angles, label=f"{name} - Z Angle", linestyle='-')

        print(f"interval between starts: {start[0] - start[1]}")
        print(f"interval between ends: {end[0] - end[1]}")

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