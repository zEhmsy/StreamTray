from pathlib import Path
import sys, os, threading, time, signal, shutil, uuid, logging, webbrowser, sqlite3
from collections import deque

# ── librerie terze parti ────────────────────────────────────────────────────
from flask import Flask, Response, jsonify, abort, request, redirect, url_for
import cv2
from PIL import Image
import waitress
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
        # Update URL if changed (basic support)
        if w.url != rtsp_url:
            w.url = rtsp_url
        return w

def reload_workers():
    """Ricarica la cache degli URL dal DB per essere sicuri."""
    load_rtsp_streams_from_db()

# ── Flask app ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# Cache dict {camera_id: rtsp_url}
rtsp_urls: dict[str, str] = {}

def load_rtsp_streams_from_db():
    rtsp_urls.clear()
    for r in q("SELECT camera_id, rtsp_url FROM rtsp_streams"):
        rtsp_urls[r["camera_id"]] = r["rtsp_url"]

load_rtsp_streams_from_db()

@app.route("/")
def index():
    if not rtsp_urls:
         # Se non ci sono stream, ricarica per sicurezza
         load_rtsp_streams_from_db()
    # Passiamo la lista direttamente al template
    streams = [{"id": k, "url": v} for k, v in rtsp_urls.items()]
    return flask_render_template("index.html", rtsp_urls=streams)

# Helper per renderizzare template senza import render_template se non necessario o per chiarezza
from flask import render_template as flask_render_template

@app.route("/api/streams", methods=["GET"])
def api_get_streams():
    load_rtsp_streams_from_db()
    return jsonify([{"id": k, "url": v} for k, v in rtsp_urls.items()])

@app.route("/api/streams", methods=["POST"])
def api_add_stream():
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url'"}), 400

    url = data["url"].strip()
    if not url:
        return jsonify({"error": "Empty URL"}), 400

    cam_id = str(uuid.uuid4())
    q("INSERT INTO rtsp_streams (camera_id, rtsp_url) VALUES (?,?)", (cam_id, url))
    load_rtsp_streams_from_db()
    return jsonify({"id": cam_id, "url": url}), 201

@app.route("/api/streams/<cam_id>", methods=["DELETE"])
def api_delete_stream(cam_id):
    q("DELETE FROM rtsp_streams WHERE camera_id=?", (cam_id,))
    load_rtsp_streams_from_db()
    # Fermiamo eventuali worker attivi
    with _workers_lock:
        if cam_id in _workers:
            # Forziamo stop se necessario, o lasciamo che il GC/unsubscribe faccia il suo corso
            # Qui ci limitiamo a rimuoverlo dalla mappa per evitare riutilizzo errato
            _workers.pop(cam_id, None)

    return jsonify({"status": "deleted"})

@app.route("/api/streams/<cam_id>", methods=["PUT"])
def api_update_stream(cam_id):
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "Missing 'url'"}), 400

    new_url = data["url"].strip()
    q("UPDATE rtsp_streams SET rtsp_url=? WHERE camera_id=?", (new_url, cam_id))
    load_rtsp_streams_from_db()

    # Aggiorna worker esistente se c'è
    with _workers_lock:
        if cam_id in _workers:
            _workers[cam_id].url = new_url

    return jsonify({"id": cam_id, "url": new_url})


@app.route("/api/snapshot/<cam_id>")
def api_snapshot(cam_id):
    # Se non è in cache, riprova a caricare
    if cam_id not in rtsp_urls:
        load_rtsp_streams_from_db()

    if cam_id not in rtsp_urls:
        abort(404, "Camera not found")

    w = worker_for(cam_id, rtsp_urls[cam_id])
    # Assicuriamo che il worker sia attivo per almeno un frame
    # (In uno scenario reale snapshot-only, servirebbe una logica di "keep-alive" meno aggressiva,
    # ma qui usiamo subscribe/unsubscribe rapido o ci affidiamo al fatto che se è "latest" lo prendiamo)

    # Per semplicità: se il worker non sta girando, lo avviamo un attimo?
    # Meglio: se vogliamo snapshot periodici, i worker dovrebbero essere sempre attivi
    # o attivati on-demand. Dato il requisito "microserver", attiviamolo se spento via subscribe.

    # Nota: se usiamo snapshot per la griglia, il worker deve restare attivo per aggiornare il buffer.
    # Quindi la griglia farà "keep-alive" implicitamente chiedendo snapshot.
    # Tuttavia CameraWorker ha un timeout o logica di stop?
    # Nel codice attuale: unsubscribe() ferma se views==0.
    # Dobbiamo gestire questo. Per ora facciamo una subscribe "temporanea".

    w.subscribe()
    try:
        # Attendiamo un attimo se il buffer è vuoto (worker appena partito)
        for _ in range(20):
            frame = w.latest()
            if frame is not None: break
            time.sleep(0.05)

        if frame is None:
            abort(503, "No frame available")

        _, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        return Response(buf.tobytes(), mimetype="image/jpeg")
    finally:
        w.unsubscribe()

@app.route("/video_feed/<cam_id>")
def video_feed(cam_id):
    # Se non è in cache, riprova a caricare
    if cam_id not in rtsp_urls:
        load_rtsp_streams_from_db()

    if cam_id not in rtsp_urls:
        abort(404, "Camera not found")

    w = worker_for(cam_id, rtsp_urls[cam_id])
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


# ── Tray + server thread ────────────────────────────────────────────────────

def open_dashboard(icon=None, item=None):
    webbrowser.open("http://localhost:5050/")

def run_flask():
    waitress.serve(app, host="0.0.0.0", port=5050, expose_tracebacks=True, threads=6)

def start_background_server():
    t = threading.Thread(target=run_flask, daemon=True)
    t.start()
    return t

# ── bootstrap ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Avvia subito il server in background
    start_background_server()
    log.info("Server started on http://localhost:5050")

    if len(sys.argv) > 1 and sys.argv[1] == "--no-tray":
        # Modalità solo server (utile per debug o docker)
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            pass
    else:
        # Modalità Tray
        Icon("StreamTray", Image.open(IMAGE_FILE), "StreamTray", Menu(
            MenuItem("Open Dashboard", open_dashboard),
            MenuItem("Quit", lambda i, _: (i.stop(), os.kill(os.getpid(), signal.SIGTERM)))
        )).run()
