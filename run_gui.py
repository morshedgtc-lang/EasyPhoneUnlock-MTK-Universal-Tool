import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from src.core.scatter.scatter_parser import ScatterParser

class EasyPhoneUnlockGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Easy Phone Unlock - MTK Universal Tool v1.0")
        self.root.geometry("850x580")
        self.root.configure(bg="#1e1e2e")

        self.scatter_partitions = []
        self._setup_style()
        self._create_widgets()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#282a36", foreground="#f8f8f2", fieldbackground="#282a36")
        style.configure("Treeview.Heading", background="#44475a", foreground="#ffffff")
        style.configure("TButton", font=("Segoe UI", 9, "bold"))

    def _create_widgets(self):
        # Header
        header = tk.Label(
            self.root,
            text="EASY PHONE UNLOCK - MTK ALL CPU UNIVERSAL TOOL",
            font=("Segoe UI", 14, "bold"),
            bg="#bd93f9",
            fg="#282a36",
            pady=10
        )
        header.pack(fill=tk.X)

        # Control Frame (Scatter / DA / Port)
        ctrl_frame = tk.Frame(self.root, bg="#1e1e2e", padx=10, pady=10)
        ctrl_frame.pack(fill=tk.X)

        tk.Label(ctrl_frame, text="Scatter File:", bg="#1e1e2e", fg="#ffffff", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w")
        self.scatter_entry = tk.Entry(ctrl_frame, width=65, bg="#282a36", fg="#50fa7b", insertbackground="white")
        self.scatter_entry.grid(row=0, column=1, padx=5, pady=5)
        
        btn_browse = tk.Button(ctrl_frame, text="Choose Scatter", bg="#6272a4", fg="white", command=self.load_scatter)
        btn_browse.grid(row=0, column=2, padx=5)

        # Partition Treeview
        tree_frame = tk.Frame(self.root, padx=10, pady=5, bg="#1e1e2e")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Select", "Partition", "File Name", "Start Address", "Size")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120)
        self.tree.column("Partition", width=140)
        self.tree.column("File Name", width=220)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Action Buttons Frame
        btn_frame = tk.Frame(self.root, bg="#1e1e2e", pady=10)
        btn_frame.pack(fill=tk.X)

        self.btn_flash = tk.Button(btn_frame, text="⚡ Start Flash", bg="#50fa7b", fg="#282a36", font=("Segoe UI", 10, "bold"), width=14, command=self.start_flash)
        self.btn_flash.pack(side=tk.LEFT, padx=10)

        self.btn_bypass = tk.Button(btn_frame, text="🔓 SLA/DAA Bypass", bg="#ffb86c", fg="#282a36", font=("Segoe UI", 10, "bold"), width=16, command=self.start_bypass)
        self.btn_bypass.pack(side=tk.LEFT, padx=5)

        self.btn_frp = tk.Button(btn_frame, text="🗑️ Reset FRP / Misc", bg="#ff5555", fg="white", font=("Segoe UI", 10, "bold"), width=16, command=self.start_frp_reset)
        self.btn_frp.pack(side=tk.LEFT, padx=5)

        # Progress bar & Status
        self.status_lbl = tk.Label(self.root, text="Status: Ready. Connect device with Vol- / Vol+.", bg="#1e1e2e", fg="#8be9fd", font=("Segoe UI", 9))
        self.status_lbl.pack(anchor="w", padx=10, pady=2)

        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.pack(fill=tk.X, padx=10, pady=5)

    def load_scatter(self):
        file_path = filedialog.askopenfilename(filetypes=[("Scatter Files", "*scatter*.txt;*.xml;*.yaml"), ("All Files", "*.*")])
        if file_path:
            self.scatter_entry.delete(0, tk.END)
            self.scatter_entry.insert(0, file_path)
            try:
                self.scatter_partitions = ScatterParser.parse_file(file_path)
                self.tree.delete(*self.tree.get_children())
                for p in self.scatter_partitions:
                    self.tree.insert("", tk.END, values=(
                        "✓" if p.is_download else "✗",
                        p.name,
                        p.file_name,
                        f"0x{p.linear_start:010X}",
                        f"0x{p.partition_size:08X}"
                    ))
                self.status_lbl.config(text=f"Loaded {len(self.scatter_partitions)} partitions from scatter.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to parse scatter file: {e}")

    def start_flash(self):
        self.status_lbl.config(text="Searching for MediaTek device (Hold Vol- / Vol+)...")

    def start_bypass(self):
        self.status_lbl.config(text="Initiating SLA / DAA Auth Bypass...")

    def start_frp_reset(self):
        self.status_lbl.config(text="Erasing FRP partition blocks...")

if __name__ == "__main__":
    root = tk.Tk()
    app = EasyPhoneUnlockGUI(root)
    root.mainloop()
