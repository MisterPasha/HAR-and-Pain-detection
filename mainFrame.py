import customtkinter as ctk
from bleConnection import BLE
import tkinter as tk


class MainFrame(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.connection_status = tk.StringVar(value="Ready to connect")
        self.make_labels()
        self.ble = BLE(self.connection_status)

        self.make_buttons()

    def make_buttons(self):
        w = self.master.winfo_width()
        h = self.master.winfo_height()

        button_connect = ctk.CTkButton(self, text="Connect to Sensors", width=int(w / 2.8), height=int(h / 15),
                                       command=self.ble.run)
        button_connect.pack(pady=(10, 50), padx=20, side="bottom")

        button_start_streaming = ctk.CTkButton(self, text="Start Streaming", width=int(w / 2.8), height=int(h / 15),
                                               command=self.ble.start_streaming)
        button_start_streaming.pack(pady=(50, 0), padx=20, side="bottom")

    def make_labels(self):
        status_label = ctk.CTkLabel(self, textvariable=self.connection_status)
        status_label.pack(pady=100)
