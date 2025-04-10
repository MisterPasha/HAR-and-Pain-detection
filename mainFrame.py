import customtkinter as ctk
from bleConnection import BLE
import tkinter as tk

class MainFrame(ctk.CTkFrame):
    def __init__(self, parent):
        """
        Initializes the main control frame of the GUI.

        Args:
            parent: The root tkinter window or parent frame.
        """
        super().__init__(parent)

        # Shared variable to display status updates (e.g., "Connected", "Streaming...")
        self.connection_status = tk.StringVar(value="Ready to connect")

        # Set up label and BLE instance
        self.make_labels()
        self.ble = BLE(self.connection_status)

        # Add control buttons
        self.make_buttons()

    def make_buttons(self):
        """
        Creates and arranges GUI buttons to control BLE connection and streaming.
        """
        # Get dimensions of the master window to scale buttons proportionally
        w = self.master.winfo_width()
        h = self.master.winfo_height()

        # Button to stop BLE streaming
        button_stop_streaming = ctk.CTkButton(
            self,
            text="Stop Streaming",
            width=int(w / 2.8),
            height=int(h / 15),
            command=self.ble.stop_streaming
        )
        button_stop_streaming.pack(pady=(10, 50), padx=20, side="bottom")

        # Button to start BLE streaming
        button_start_streaming = ctk.CTkButton(
            self,
            text="Start Streaming",
            width=int(w / 2.8),
            height=int(h / 15),
            command=self.ble.start_streaming
        )
        button_start_streaming.pack(pady=(10, 0), padx=20, side="bottom")

        # Button to initiate connection to BLE sensors
        button_connect = ctk.CTkButton(
            self,
            text="Connect to Sensors",
            width=int(w / 2.8),
            height=int(h / 15),
            command=self.ble.run
        )
        button_connect.pack(pady=(0, 0), padx=20, side="bottom")

    def make_labels(self):
        """
        Displays a dynamic label that reflects BLE connection status.
        """
        status_label = ctk.CTkLabel(self, textvariable=self.connection_status)
        status_label.pack(pady=100)
