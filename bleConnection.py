import asyncio
from bleak import BleakScanner, BleakClient
import threading


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.RFDUINO_NAME_PREFIX = "Head"  # Prefix for RFduino names
        self.is_running = False               # Flag for running function
        self.status_var = status_var          # Connection Status String

    async def connect_to_rfduino(self, device):
        """Function to connect to a single RFduino device."""
        try:
            async with BleakClient(device) as client:  # Connect device
                self.connected_devices.append(client)  # Store the connected client
                self.status_var.set(f"Connected to {device.name} ({device.address})")
                print(f"Connected to {device.name} ({device.address})")
                # Perform any specific operations here
        except Exception as e:
            self.status_var.set(f"Failed to connect to {device.name}: {e}")
            print(f"Failed to connect to {device.name}: {e}")

    async def main(self):
        # Discover BLE devices
        devices = await BleakScanner.discover(timeout=10)  # Searches devices for 5 seconds
        # Filter out devices that match the RFduino name prefix
        rfduino_devices = [d for d in devices if d.name and d.name.startswith(self.RFDUINO_NAME_PREFIX)]
        #rfduino_devices = devices

        if not rfduino_devices:
            self.status_var.set("No RFduinos detected")
            return

        self.status_var.set(f"Found {len(rfduino_devices)} RFduino devices")

        # Connect to each RFduino one by one
        for device in rfduino_devices:
            self.status_var.set(f"Attempting to connect to {device.name} ({device.address})")
            await self.connect_to_rfduino(device)

        # Print final connected devices
        connected_devices = "\nConnected RFduino devices:"
        for client in self.connected_devices:
            connected_devices += "\n"+client.address

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
