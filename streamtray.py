"""
StreamTray – RTSP → MJPEG con tray-icon e DB SQLite
Versione thread-safe: un thread per camera, chiusura auto quando non serve più
"""
from pathlib import Path
import sys, os, threading, time, signal, shutil, uuid, logging, webbrowser, sqlite3
from collections import deque

# ── librerie terze parti ────────────────────────────────────────────────────
from flask import Flask, Response, jsonify, abort
import cv2
from PIL import Image
import waitress
import tkinter as tk
from tkinter import ttk
from pystray import Icon, Menu, MenuItem

TARGET_FPS  = 30
BUF_LEN     = 4          # frame mantenuti in memoria per ogni cam

# ── percorsi e logging ──────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    RES_DIR  = Path(sys._MEIPASS)
    DATA_DIR = Path(sys.executable).parent
else:
    RES_DIR  = Path(__file__).resolve().parent
    DATA_DIR = RES_DIR

ICON_FILE, IMAGE_FILE = RES_DIR / "app.ico", RES_DIR / "app.png"
DB_FILE               = DATA_DIR / "rtsp_streams.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("streamtray")

# ── DB helpers ───────────────────────────────────────────────────────────────
def get_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE); conn.row_factory = sqlite3.Row; return conn

def q(sql, args=()):
    with get_db() as c:
        cur = c.execute(sql, args); c.commit(); return cur.fetchall()

q("""CREATE TABLE IF NOT EXISTS rtsp_streams (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       camera_id TEXT, rtsp_url TEXT)""")

# ── CameraWorker: un thread di cattura per cam ──────────────────────────────
class CameraWorker:
    def __init__(self, url: str):
        self.url  = url
        self.buf  = deque(maxlen=BUF_LEN)
        self.lock = threading.Lock()
        self.views = 0
        self.stop = threading.Event()
        self.th   = None

    def _loop(self):
        delay = 1 / TARGET_FPS
        # forza TCP e 1 MB di buffer
        url = f"{self.url}?rtsp_transport=tcp&buffer_size=1048576"

        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            log.error("Impossibile aprire %s", url); return

        while not self.stop.is_set():
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                log.warning("Frame perso su %s", url)
                continue  # mantiene vivo il loop

            self.buf.append(frame)
            s = delay - (time.time() - t0)
            if s > 0: time.sleep(s)

        cap.release()

    # API --------------------------------------------------------------------
    def start(self):
        if not self.th or not self.th.is_alive():
            self.stop.clear()
            self.th = threading.Thread(target=self._loop, daemon=True); self.th.start()

    def subscribe(self):
        with self.lock:
            self.views += 1
            self.start()

    def unsubscribe(self):
        with self.lock:
            self.views = max(0, self.views - 1)
            if self.views == 0:
                self.stop.set()

    def latest(self):
        return self.buf[-1] if self.buf else None

# ── registry {camera_id: worker} ────────────────────────────────────────────
_workers, _workers_lock = {}, threading.Lock()

def worker_for(cam_id: str, rtsp_url: str):
    with _workers_lock:
        w = _workers.get(cam_id)
        if not w:
            w = _workers[cam_id] = CameraWorker(rtsp_url)
        return w

# ── Flask app ───────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/api/streams")
def api_streams():
    rows = q("SELECT camera_id FROM rtsp_streams")
    return jsonify({"streams": [{"id": r["camera_id"], "name": r["camera_id"]} for r in rows]})

@app.route("/video_feed/<cam_id>")
def video_feed(cam_id):
    row = q("SELECT rtsp_url FROM rtsp_streams WHERE camera_id=?", (cam_id,))
    if not row: abort(404, "Camera not found")

    w = worker_for(cam_id, row[0]["rtsp_url"])
    w.subscribe()

    def stream():
        try:
            while True:
                frame = w.latest()
                if frame is None: time.sleep(0.02); continue
                _, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                       buf.tobytes() + b"\r\n")
        except GeneratorExit:
            pass
        finally:
            w.unsubscribe()

    return Response(stream(), mimetype="multipart/x-mixed-replace; boundary=frame")

# ----------------------------------------------------------------------------
# Cache dict {camera_id: rtsp_url}
# ----------------------------------------------------------------------------
rtsp_urls: dict[str, str] = {}

def load_rtsp_streams_from_db():
    rtsp_urls.clear()
    for r in q("SELECT camera_id, rtsp_url FROM rtsp_streams"):
        rtsp_urls[r["camera_id"]] = r["rtsp_url"]

load_rtsp_streams_from_db()

# ----------------------------------------------------------------------------
# GUI Tk per gestire RTSP
# ----------------------------------------------------------------------------

def manage_rtsp_streams(icon=None, item=None):

    def refresh_tree():
        tree.delete(*tree.get_children())
        for r in q("SELECT camera_id, rtsp_url FROM rtsp_streams"):
            tree.insert("", "end", values=(r["camera_id"], r["rtsp_url"]))
        load_rtsp_streams_from_db()

    def add_stream():
        url = entry_url.get().strip()
        if url:
            cam = str(uuid.uuid4())
            q("INSERT INTO rtsp_streams (camera_id, rtsp_url) VALUES (?,?)", (cam, url))
            entry_url.delete(0, tk.END)
            refresh_tree()

    def update_stream():
        sel = tree.selection()
        if sel:
            cam_id = tree.item(sel[0], "values")[0]
            new_url = entry_url.get().strip()
            if new_url:
                q("UPDATE rtsp_streams SET rtsp_url=? WHERE camera_id=?", (new_url, cam_id))
                refresh_tree()

    def remove_selected():
        for item_id in tree.selection():
            cam_id = tree.item(item_id, "values")[0]
            q("DELETE FROM rtsp_streams WHERE camera_id=?", (cam_id,))
        refresh_tree()

    def on_tree_select(_):
        sel = tree.selection()
        if sel:
            entry_url.delete(0, tk.END)
            entry_url.insert(0, tree.item(sel[0], "values")[1])

    def copy_url(_=None):
        sel = tree.selection()
        if sel:
            root.clipboard_clear()
            root.clipboard_append(tree.item(sel[0], "values")[1])

    root = tk.Tk(); root.title("Gestione RTSP Streams"); root.resizable(False, False)
    if ICON_FILE.exists():
        root.iconbitmap(str(ICON_FILE))

    cols = ("Camera ID", "RTSP URL")
    frame_tree = ttk.Frame(root); frame_tree.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
    tree = ttk.Treeview(frame_tree, columns=cols, show="headings", displaycolumns=("RTSP URL",), height=10)
    tree.heading("RTSP URL", text="RTSP URL")
    tree.column("Camera ID", width=0, stretch=False)
    tree.column("RTSP URL", width=450, anchor=tk.W)
    vsb = ttk.Scrollbar(frame_tree, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew"); vsb.grid(row=0, column=1, sticky="ns")
    frame_tree.grid_rowconfigure(0, weight=1); frame_tree.grid_columnconfigure(0, weight=1)

    tree.bind("<<TreeviewSelect>>", on_tree_select)
    tree.bind("<Double-1>", copy_url); root.bind_all("<Control-c>", copy_url)

    frame_ctrl = ttk.Frame(root); frame_ctrl.pack(padx=10, pady=(0,10), fill=tk.X)
    ttk.Label(frame_ctrl, text="RTSP URL:").grid(row=0, column=0, sticky=tk.W)
    entry_url = ttk.Entry(frame_ctrl, width=60); entry_url.grid(row=0, column=1, padx=(0,10))
    ttk.Button(frame_ctrl, text="Aggiungi", command=add_stream).grid(row=0, column=2, padx=(0,5))
    ttk.Button(frame_ctrl, text="Aggiorna selezionato", command=update_stream).grid(row=0, column=3, padx=(0,5))
    ttk.Button(frame_ctrl, text="Rimuovi selezionato", command=remove_selected).grid(row=0, column=4)

    refresh_tree(); root.mainloop()

# ----------------------------------------------------------------------------
# Tray + server thread
# ----------------------------------------------------------------------------

def open_first_stream(icon=None, item=None):
    row = q("SELECT camera_id FROM rtsp_streams ORDER BY id LIMIT 1")
    url = f"http://localhost:5000/video_feed/{row[0]['camera_id']}" if row else "http://localhost:5000/"
    webbrowser.open(url)


def start_server(icon=None, item=None):
    def run_flask():
        waitress.serve(app, host="0.0.0.0", port=5000, expose_tracebacks=True, threads=4)
    threading.Thread(target=run_flask, daemon=True).start()
    icon.notify("StreamTray avviato", "StreamTray")
    log.info("Waitress listening on 0.0.0.0:5000")


def exit_all(icon=None, item=None):
    icon.stop(); os.kill(os.getpid(), signal.SIGTERM)

def start_server(icon=None, item=None):
    threading.Thread(
        target=lambda: waitress.serve(app, host="0.0.0.0", port=5000,
                                      expose_tracebacks=True, threads=4),
        daemon=True).start()
    icon.notify("StreamTray avviato", "StreamTray")
    log.info("Waitress listening on 0.0.0.0:5000")

# ── bootstrap (tray oppure debug senza tray) ─────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--debug":
        app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
    else:
        Icon("StreamTray", Image.open(IMAGE_FILE), "StreamTray", Menu(
            MenuItem("Start server", start_server),
            MenuItem("Gestisci RTSP Streams", manage_rtsp_streams),
            MenuItem("Chiudi", lambda i, _: (i.stop(), os.kill(os.getpid(), signal.SIGTERM)))
        )).run()