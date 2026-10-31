"""Desktop GUI (CustomTkinter)."""
import csv
import queue
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from .backends import DemoBackend, DiscordBackend
from .engine import CheckEngine
from . import settings
from .models import Status
from .validation import parse_names

COLORS = {
    Status.AVAILABLE: "#3ba55d",
    Status.TAKEN: "#ed4245",
    Status.INVALID: "#faa61a",
    Status.RATE_LIMITED: "#faa61a",
    Status.ERROR: "#faa61a",
}


def make_backend():
    return DiscordBackend()  # use DemoBackend() for offline UI testing


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Discord Name Checker")
        self.geometry("980x620")
        self.minsize(820, 520)

        self.engine: CheckEngine | None = None
        self.results = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_left()
        self._build_right()
        self._load_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll)

    def _load_settings(self):
        cfg = settings.load()
        if "delay" in cfg:
            self.delay.set(min(10, max(0.5, float(cfg["delay"]))))
            self._delay_changed(self.delay.get())
        if cfg.get("names"):
            self.names_box.insert("1.0", cfg["names"])

    def _on_close(self):
        settings.save({"delay": self.delay.get(),
                       "names": self.names_box.get("1.0", "end").strip()})
        if self.engine:
            self.engine.stop()
        self.destroy()

    # ---------------------------------------------------------- layout
    def _build_left(self):
        f = ctk.CTkFrame(self, width=300)
        f.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)
        f.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Usernames", font=ctk.CTkFont(size=16, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        self.names_box = ctk.CTkTextbox(f, width=270)
        self.names_box.grid(row=1, column=0, sticky="nsew", padx=12)
        ctk.CTkLabel(f, text="One per line (commas/spaces also work)",
                     text_color="gray").grid(row=2, column=0, sticky="w", padx=12)

        ctk.CTkButton(f, text="Import .txt", fg_color="transparent", border_width=1,
                      command=self._import).grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 4))

        self.delay_label = ctk.CTkLabel(f, text="Delay between checks: 1.5 s")
        self.delay_label.grid(row=4, column=0, sticky="w", padx=12, pady=(8, 0))
        self.delay = ctk.CTkSlider(f, from_=0.5, to=10, number_of_steps=19,
                                   command=self._delay_changed)
        self.delay.set(1.5)
        self.delay.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))

        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 12))
        btns.grid_columnconfigure((0, 1, 2), weight=1)
        self.start_btn = ctk.CTkButton(btns, text="Start", command=self._start)
        self.pause_btn = ctk.CTkButton(btns, text="Pause", command=self._pause,
                                       state="disabled", fg_color="#4f545c")
        self.stop_btn = ctk.CTkButton(btns, text="Stop", command=self._stop,
                                      state="disabled", fg_color="#ed4245", hover_color="#c03537")
        self.start_btn.grid(row=0, column=0, padx=2, sticky="ew")
        self.pause_btn.grid(row=0, column=1, padx=2, sticky="ew")
        self.stop_btn.grid(row=0, column=2, padx=2, sticky="ew")

    def _build_right(self):
        f = ctk.CTkFrame(self)
        f.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
        f.grid_columnconfigure(0, weight=1)
        f.grid_rowconfigure(2, weight=1)

        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        ctk.CTkLabel(top, text="Results", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        self.filter = ctk.CTkSegmentedButton(
            top, values=["All", "Available", "Taken", "Other"], command=lambda _: self._refresh())
        self.filter.set("All")
        self.filter.pack(side="right")

        self.progress = ctk.CTkProgressBar(f)
        self.progress.set(0)
        self.progress.grid(row=1, column=0, sticky="ew", padx=12, pady=4)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b",
                        foreground="white", rowheight=26, borderwidth=0)
        style.configure("Treeview.Heading", background="#3a3a3a", foreground="white", relief="flat")
        style.map("Treeview", background=[("selected", "#1f6aa5")])

        self.tree = ttk.Treeview(f, columns=("name", "status", "detail"), show="headings")
        for col, w in (("name", 220), ("status", 110), ("detail", 260)):
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=w, anchor="w")
        for st, c in COLORS.items():
            self.tree.tag_configure(st.value, foreground=c)
        self.tree.grid(row=2, column=0, sticky="nsew", padx=12, pady=4)

        bottom = ctk.CTkFrame(f, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 12))
        self.status = ctk.CTkLabel(bottom, text="Ready", text_color="gray")
        self.status.pack(side="left")
        ctk.CTkButton(bottom, text="Export CSV", width=100, command=self._export_csv
                      ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bottom, text="Save available .txt", width=140, command=self._export_txt
                      ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(bottom, text="Copy available", width=120, command=self._copy_available
                      ).pack(side="right")

    # --------------------------------------------------------- actions
    def _delay_changed(self, v):
        self.delay_label.configure(text=f"Delay between checks: {v:.1f} s")

    def _import(self):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                self.names_box.insert("end", "\n" + fh.read())

    def _start(self):
        names = parse_names(self.names_box.get("1.0", "end"))
        if not names:
            messagebox.showinfo("Name Checker", "Enter at least one username.")
            return
        self.results.clear()
        self._refresh()
        self.progress.set(0)
        self.engine = CheckEngine(make_backend(), delay=self.delay.get())
        self.engine.start(names)
        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="Pause")
        self.stop_btn.configure(state="normal")
        self.status.configure(text=f"Checking {len(names)} names...")

    def _pause(self):
        if not self.engine:
            return
        if self.pause_btn.cget("text") == "Pause":
            self.engine.pause()
            self.pause_btn.configure(text="Resume")
            self.status.configure(text="Paused")
        else:
            self.engine.resume()
            self.pause_btn.configure(text="Pause")
            self.status.configure(text="Checking...")

    def _stop(self):
        if self.engine:
            self.engine.stop()

    def _finish(self, stopped: bool):
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="Pause")
        self.stop_btn.configure(state="disabled")
        avail = sum(r.status is Status.AVAILABLE for r in self.results)
        self.status.configure(
            text=f"{'Stopped' if stopped else 'Done'} - {avail} available / {len(self.results)} checked")

    # --------------------------------------------------------- results
    def _poll(self):
        if self.engine:
            try:
                while True:
                    ev = self.engine.events.get_nowait()
                    if ev[0] == "result":
                        self.results.append(ev[1])
                        self._refresh()
                    elif ev[0] == "progress":
                        self.progress.set(ev[1] / ev[2])
                        avail = sum(r.status is Status.AVAILABLE for r in self.results)
                        self.status.configure(text=f"{ev[1]}/{ev[2]} checked - {avail} available")
                    elif ev[0] == "info":
                        self.status.configure(text=ev[1])
                    elif ev[0] == "done":
                        self._finish(ev[1])
            except queue.Empty:
                pass
        self.after(100, self._poll)

    def _refresh(self):
        mode = self.filter.get()

        def keep(r):
            if mode == "All":
                return True
            if mode == "Available":
                return r.status is Status.AVAILABLE
            if mode == "Taken":
                return r.status is Status.TAKEN
            return r.status not in (Status.AVAILABLE, Status.TAKEN)

        self.tree.delete(*self.tree.get_children())
        for r in filter(keep, self.results):
            self.tree.insert("", "end", values=(r.name, r.status.value, r.detail), tags=(r.status.value,))

    def _copy_available(self):
        names = [r.name for r in self.results if r.status is Status.AVAILABLE]
        self.clipboard_clear()
        self.clipboard_append("\n".join(names))
        self.status.configure(text=f"Copied {len(names)} available names")

    def _export_txt(self):
        names = [r.name for r in self.results if r.status is Status.AVAILABLE]
        if not names:
            messagebox.showinfo("Name Checker", "No available names to save yet.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(names) + "\n")

    def _export_csv(self):
        if not self.results:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["name", "status", "detail"])
                for r in self.results:
                    w.writerow([r.name, r.status.value, r.detail])


def run():
    App().mainloop()
