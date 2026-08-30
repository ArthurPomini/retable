import tkinter as tk
from tkinter import ttk
from app_window import MainWindow


class RedutorApp:
    def __init__(self):
        self.root = tk.Tk()
        self._apply_theme()
        self.window = MainWindow(self.root)

    def _apply_theme(self):
        try:
            style = ttk.Style()
            if "clam" in style.theme_names():
                style.theme_use("clam")
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    app = RedutorApp()
    app.run()


if __name__ == "__main__":
    main()
