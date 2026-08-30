from typing import List, Set, Tuple
import tkinter as tk
from tkinter import ttk


class ColumnSelector(ttk.Frame):
    def __init__(self, parent, height: int = 140, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, height=height, highlightthickness=0)
        self.vscroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscroll.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.vscroll.pack(side="right", fill="y")

        self.checkbox_container = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.checkbox_container, anchor="nw")

        self.checkbox_container.bind("<Configure>", self._on_container_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

        self._items: List[Tuple[str, tk.BooleanVar, ttk.Checkbutton]] = []

    def _on_container_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)

    def _on_mousewheel(self, event):
        delta = -1 * (event.delta // 120) if event.delta else (-1 if event.num == 4 else 1)
        self.canvas.yview_scroll(int(delta), "units")

    def _bind_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def clear(self):
        for _, _, chk in self._items:
            chk.destroy()
        self._items.clear()
        self.canvas.configure(scrollregion=(0, 0, 0, 0))

    def set_columns(self, columns: List[str]):
        self.clear()
        for idx, col_name in enumerate(columns):
            var = tk.BooleanVar(value=False)
            chk = ttk.Checkbutton(
                self.checkbox_container,
                text=col_name,
                variable=var,
            )
            chk.grid(row=idx, column=0, sticky="w", padx=4, pady=2)
            self._items.append((col_name, var, chk))

        self.checkbox_container.update_idletasks()
        self._on_container_configure()

    def get_selected_indices(self) -> Set[int]:
        return {idx for idx, (_, var, _) in enumerate(self._items) if var.get()}

    def select_all(self):
        for _, var, _ in self._items:
            var.set(True)

    def deselect_all(self):
        for _, var, _ in self._items:
            var.set(False)

    def toggle_all(self):
        if not self._items:
            return
        all_selected = all(var.get() for _, var, _ in self._items)
        new_value = not all_selected
        for _, var, _ in self._items:
            var.set(new_value)
