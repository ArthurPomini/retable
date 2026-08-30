from typing import List
from tkinter import ttk


class PreviewTable(ttk.Frame):
    def __init__(self, parent, height: int = 8, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.tree = ttk.Treeview(self, show="headings", height=height)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def clear(self):
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = []

    def update_data(self, columns: List[str], rows: List[List[str]]):
        self.clear()
        self.tree["columns"] = columns
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, stretch=False)

        for row in rows:
            self.tree.insert("", "end", values=row)
