import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

root = ctk.CTk()
root.geometry("350x600")

# Some comment
w = root.winfo_width()
h = root.winfo_height()

button = ctk.CTkButton(root, text="Connect to Sensors").pack(pady=20)

root.mainloop()