import asyncio
from bleak import BleakScanner, BleakClient
import threading


class BLE:
    def __init__(self, status_var):
        self.connected_devices = []           # List to store connected RFduino devices
        self.RFDUINO_NAME_PREFIX = "Head"     # Prefix for RFduino names
        self.RFDUINO_NAMES = ["Head"]               # List of all RFduino names
        self.is_running = False               # Flag for running function
        self.status_var = status_var          # Connection Status String

    async def data_handler(self, sender, data):
        """Callback to handle incoming data from RFduino."""
        print(data.decode('utf-8') if isinstance(data, bytes) else data)
        #print(data)

    async def connect_to_rfduino(self, device):
        """Function to connect to a single RFduino device."""
        try:
            async with BleakClient(device) as client:  # Connect device
                self.connected_devices.append(client)  # Store the connected client
                self.status_var.set(f"Connected to {device.name} ({device.address})")
                print(f"Connected to {device.name} ({device.address})")

                # Get a list of characteristics
                services = await client.get_services()
                for service in services:
                    print(f"[Service] {service.uuid}")
                    for char in service.characteristics:
                        print(f"  [Characteristic] {char.uuid} (Properties: {char.properties})")

                # Replace this with the correct UUID for RFduino's data stream
                target_characteristic_uuid = "2340015-cbed-76db-9423-74ce6ab55dee"  # Head UUID

                # Subscribe to the characteristic
                await client.start_notify(target_characteristic_uuid, self.data_handler)
                self.status_var.set(f"Subscribed to data on {target_characteristic_uuid}")
                # Keep the connection alive to receive data
                await asyncio.sleep(30)  # Keep subscribed for 30 seconds (adjust as needed)
                await client.stop_notify(target_characteristic_uuid)

        except Exception as e:
            self.status_var.set(f"Failed to connect to {device.name}: {e}")
            print(f"Failed to connect to {device.name}: {e}")

    async def main(self):
        # Discover BLE devices
        devices = await BleakScanner.discover(timeout=5)  # Searches devices for 5 seconds
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
