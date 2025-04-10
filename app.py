import customtkinter as ctk
from mainFrame import MainFrame


class App(ctk.CTk):
    def __init__(self):
        """
        Initializes the main application window for the BLE-based sensor streaming GUI.
        Sets window appearance, size, and embeds the MainFrame for controls.
        """
        super().__init__()

        # Set global appearance and color theme
        ctk.set_appearance_mode("dark")         # Options: "dark", "light", "system"
        ctk.set_default_color_theme("green")    # Options: "blue", "green", "dark-blue", etc.

        # Configure window geometry: width x height + x_offset + y_offset
        self.geometry("350x600+1200+20")
        self.title("Project App")
        self.resizable(False, False)  # Disable window resizing

        # Add main control frame (with connect/start/stop buttons and status label)
        self.main_frame = MainFrame(self)
        self.main_frame.pack(fill="both", expand=True)


