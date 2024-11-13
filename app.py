import customtkinter as ctk
from mainFrame import MainFrame


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Set appearance and theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.geometry("350x600+1200+20")
        self.title("Project App")
        self.resizable(False, False)

        # Add the main frame or other UI elements
        self.main_frame = MainFrame(self)
        self.main_frame.pack(fill="both", expand=True)

