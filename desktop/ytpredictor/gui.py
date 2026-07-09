"""Minimal Tkinter GUI: configure the API key/port, start the local server,
watch your history and interest profile, and trigger model training.

Tkinter is stdlib, which keeps the PyInstaller build small and avoids mixing
Qt (used by the unrelated PyBrowser app in this repo) into this app.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

from . import config as config_mod
from .db import init_db, session_scope
from .runtime import ServerThread


class LogQueueHandler:
    """Simple thread-safe log sink the GUI polls from the Tk main loop."""

    def __init__(self):
        self.queue: queue.Queue[str] = queue.Queue()

    def write(self, message: str) -> None:
        self.queue.put(message)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Watch-Completion Predictor")
        self.geometry("720x560")
        self.minsize(640, 480)

        self.settings = config_mod.load_settings()
        init_db()

        self.server_thread: ServerThread | None = None
        self.log_sink = LogQueueHandler()

        self._build_ui()
        self._poll_log_queue()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start the server so the extension works immediately.
        self.after(200, self.start_server)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_status_tab(notebook)
        self._build_settings_tab(notebook)
        self._build_history_tab(notebook)
        self._build_profile_tab(notebook)

    def _build_status_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Status")

        self.status_var = tk.StringVar(value="Server stopped")
        ttk.Label(frame, textvariable=self.status_var, font=("Segoe UI", 12, "bold")).pack(
            anchor="w", padx=10, pady=(10, 4)
        )

        btns = ttk.Frame(frame)
        btns.pack(anchor="w", padx=10, pady=4)
        self.start_btn = ttk.Button(btns, text="Start server", command=self.start_server)
        self.start_btn.grid(row=0, column=0, padx=(0, 6))
        self.stop_btn = ttk.Button(btns, text="Stop server", command=self.stop_server, state="disabled")
        self.stop_btn.grid(row=0, column=1, padx=(0, 6))
        ttk.Button(btns, text="Train model now", command=self.train_now).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(btns, text="Open API docs", command=self._open_docs).grid(row=0, column=3)

        self.train_status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.train_status_var).pack(anchor="w", padx=10, pady=(4, 8))

        ttk.Label(frame, text="Log:").pack(anchor="w", padx=10)
        self.log_text = tk.Text(frame, height=18, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_settings_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Settings")

        pad = {"padx": 10, "pady": 6}

        ttk.Label(frame, text="YouTube Data API key:").grid(row=0, column=0, sticky="w", **pad)
        self.api_key_var = tk.StringVar(value=self.settings.youtube_api_key)
        ttk.Entry(frame, textvariable=self.api_key_var, width=48, show="*").grid(row=0, column=1, **pad)

        ttk.Label(frame, text="Server port:").grid(row=1, column=0, sticky="w", **pad)
        self.port_var = tk.StringVar(value=str(self.settings.server_port))
        ttk.Entry(frame, textvariable=self.port_var, width=10).grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(frame, text='"Interesting" threshold (%):').grid(row=2, column=0, sticky="w", **pad)
        self.threshold_var = tk.StringVar(value=str(self.settings.interesting_threshold))
        ttk.Entry(frame, textvariable=self.threshold_var, width=10).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frame, text="Min. watch events before ML model kicks in:").grid(
            row=3, column=0, sticky="w", **pad
        )
        self.min_samples_var = tk.StringVar(value=str(self.settings.min_training_samples))
        ttk.Entry(frame, textvariable=self.min_samples_var, width=10).grid(row=3, column=1, sticky="w", **pad)

        ttk.Button(frame, text="Save (restarts server)", command=self._save_settings).grid(
            row=4, column=0, columnspan=2, pady=16
        )

        help_text = (
            "Get a free API key: Google Cloud Console -> APIs & Services -> \n"
            "Credentials -> Create API key, with the 'YouTube Data API v3' enabled."
        )
        ttk.Label(frame, text=help_text, foreground="#555").grid(row=5, column=0, columnspan=2, sticky="w", **pad)

    def _build_history_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Watch history")

        ttk.Button(frame, text="Refresh", command=self._refresh_history).pack(anchor="w", padx=10, pady=6)

        columns = ("title", "channel", "percent", "when")
        self.history_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col, label, width in (
            ("title", "Title", 320),
            ("channel", "Channel", 160),
            ("percent", "% watched", 80),
            ("when", "When", 160),
        ):
            self.history_tree.heading(col, text=label)
            self.history_tree.column(col, width=width, anchor="w")
        self.history_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_profile_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Interest profile")

        ttk.Button(frame, text="Refresh", command=self._refresh_profile).pack(anchor="w", padx=10, pady=6)

        columns = ("channel", "avg_percent", "count")
        self.profile_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for col, label, width in (("channel", "Channel", 320), ("avg_percent", "Avg % watched", 120), ("count", "Videos", 80)):
            self.profile_tree.heading(col, text=label)
            self.profile_tree.column(col, width=width, anchor="w")
        self.profile_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    # ------------------------------------------------------------ actions --
    def _log(self, message: str) -> None:
        self.log_sink.write(message)

    def _poll_log_queue(self) -> None:
        try:
            while True:
                message = self.log_sink.queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(300, self._poll_log_queue)

    def start_server(self) -> None:
        if self.server_thread is not None:
            return
        self.settings = config_mod.load_settings()
        try:
            self.server_thread = ServerThread(self.settings)
            self.server_thread.start()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed to start server", str(exc))
            self.server_thread = None
            return

        self.status_var.set(
            f"Server running at http://{self.settings.server_host}:{self.settings.server_port}"
        )
        self._log(f"Server started on port {self.settings.server_port}")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def stop_server(self) -> None:
        if self.server_thread is None:
            return
        self.server_thread.stop()
        self.server_thread = None
        self.status_var.set("Server stopped")
        self._log("Server stopped")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _save_settings(self) -> None:
        try:
            port = int(self.port_var.get())
            threshold = float(self.threshold_var.get())
            min_samples = int(self.min_samples_var.get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Port / threshold / min samples must be numbers.")
            return

        self.settings.youtube_api_key = self.api_key_var.get().strip()
        self.settings.server_port = port
        self.settings.interesting_threshold = threshold
        self.settings.min_training_samples = min_samples
        config_mod.save_settings(self.settings)
        self._log("Settings saved.")

        if self.server_thread is not None:
            self.stop_server()
            self.start_server()

    def train_now(self) -> None:
        """Retrain and, if the server is running, hot-reload its in-memory model."""

        def worker():
            from .model import WatchPredictor
            import ytpredictor.server as server_mod

            with session_scope() as session:
                wp = WatchPredictor()
                wp.load()
                n = wp.train(session, min_samples=self.settings.min_training_samples)

            self.train_status_var.set(
                f"Trained on {n} watch events. Model active: {n >= self.settings.min_training_samples}"
            )
            self._log(f"Training complete: {n} samples used.")

            if self.server_thread is not None and server_mod.state is not None:
                server_mod.state.predictor.load()

        threading.Thread(target=worker, daemon=True).start()
        self.train_status_var.set("Training...")

    def _refresh_history(self) -> None:
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        with session_scope() as session:
            from .db import Video, WatchEvent

            rows = (
                session.query(WatchEvent, Video)
                .join(Video, Video.video_id == WatchEvent.video_id)
                .order_by(WatchEvent.watched_at.desc())
                .limit(200)
                .all()
            )
            for e, v in rows:
                self.history_tree.insert(
                    "",
                    "end",
                    values=(
                        v.title,
                        v.channel_title,
                        f"{e.percent_watched:.0f}%",
                        e.watched_at.strftime("%Y-%m-%d %H:%M") if e.watched_at else "",
                    ),
                )

    def _refresh_profile(self) -> None:
        for row in self.profile_tree.get_children():
            self.profile_tree.delete(row)
        with session_scope() as session:
            from .model import recompute_interest_profile

            profile = recompute_interest_profile(session)
            for cid, avg in sorted(profile.channel_avg_percent.items(), key=lambda kv: -kv[1]):
                n = profile.channel_watch_count.get(cid, 0)
                self.profile_tree.insert("", "end", values=(cid, f"{avg:.0f}%", n))

    def _open_docs(self) -> None:
        if self.server_thread is not None:
            webbrowser.open(f"http://{self.settings.server_host}:{self.settings.server_port}/docs")
        else:
            messagebox.showinfo("Server not running", "Start the server first.")

    def _on_close(self) -> None:
        self.stop_server()
        self.destroy()


def main() -> int:
    app = App()
    app.mainloop()
    return 0
