"""AgriDrone backend (Flask).
/api/analyze  - receives a leaf image, analyses it, saves the result to SQLite
/api/chat     - chatbot replies (English / Hindi / Marathi) from kb.json
/api/scans    - saved scan history + totals
Later: replace analyse() with your trained model (YOLO / CNN); nothing else changes.
"""
import os, io, re, json, time, uuid, sqlite3, math, threading
import requests
from datetime import datetime
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(BASE, "static"))
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
UP = os.path.join(BASE, "uploads"); os.makedirs(UP, exist_ok=True)
DB = os.path.join(BASE, "agridrone.db")
KB = json.load(open(os.path.join(BASE, "kb.json"), encoding="utf-8"))
RX = {k: re.compile(v, re.I) for k, v in KB["RX"].items()}
LI = {"en": 0, "hi": 1, "mr": 2}
SOURCES = {"Upload", "Camera", "Drone"}
HELLO = ["Hello! How can I help you? Upload a leaf photo and tap a red area, or ask me about your crop.",
         "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ? पत्ते की फोटो डालें और लाल हिस्से पर टैप करें, या फसल के बारे में पूछें।",
         "नमस्कार! मी तुमची कशी मदत करू? पानाचा फोटो टाका व लाल भागावर टॅप करा, किंवा पिकाबद्दल विचारा."]


def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c


with db() as c:
    c.execute("CREATE TABLE IF NOT EXISTS scans(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,"
              " source TEXT, cond TEXT, affected REAL, severity TEXT, file TEXT)")


CFG_PATH = os.path.join(BASE, "config.json")
CFG = {"url": "", "mode": "landed", "interval": 5, "farm": ""}
try: CFG.update(json.load(open(CFG_PATH)))
except Exception: pass
STATE = {"last_ok": 0, "frames": 0, "last": "", "found": 0}


def save_cfg():
    json.dump(CFG, open(CFG_PATH, "w"))


try:
    with db() as c: c.execute("ALTER TABLE scans ADD COLUMN data TEXT")
except sqlite3.OperationalError:
    pass


def analyse(img):
    """Colour-based leaf analysis on a 10-column grid. Returns dict or None (no leaf)."""
    W, H = img.size
    hsv = np.asarray(img.convert("HSV")).astype(np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    ok = v >= .22
    w = ok & (s < .18) & (v > .8)
    g = ok & ~w & (h >= 70) & (h <= 165) & (s > .25)
    y = ok & ~w & ~g & (h >= 42) & (h < 70) & (s > .4) & (v > .5)
    b = ok & ~w & ~g & ~y & (h >= 8) & (h < 42) & (s > .3) & (v < .7)
    if g.sum() / (W * H) < .03:
        return None
    cols = 10; cw = W / cols; rw = max(1, math.ceil(H / cw)); ch = H / rw; n = cols * rw
    cx = np.minimum(cols - 1, (np.arange(W) / cw).astype(int))
    cy = np.minimum(rw - 1, (np.arange(H) / ch).astype(int))
    idx = (cy[:, None] * cols + cx[None, :]).ravel()
    cnt = lambda m: np.bincount(idx, weights=m.ravel().astype(float), minlength=n)
    N, G, B, Y, Wt = cnt(np.ones((H, W))), cnt(g), cnt(b), cnt(y), cnt(w)
    P = B + Y + Wt; Lg = G + P
    # leaf-only: a cell counts only if it is green itself or surrounded by green (ignores soil / background)
    gf = (G / N).reshape(rw, cols); pad = np.pad(gf, 1)
    nb = (sum(pad[i:i + rw, j:j + cols] for i in range(3) for j in range(3)) / 9).ravel()
    leaf = (G / N > .12) | ((Lg / N > .25) & (nb > .3))
    flag = leaf & (P / np.maximum(Lg, 1) > .2) & (G / N > .06) & (nb > .25)
    names = ["spot", "yellow", "powdery"]
    ck = np.where((B >= Y) & (B >= Wt), 0, np.where(Y >= Wt, 1, 2))
    nf, nl = int(flag.sum()), int(leaf.sum())
    key = "healthy" if not nf else names[int(np.argmax([B[flag].sum(), Y[flag].sum(), Wt[flag].sum()]))]
    aff = nf / nl * 100 if nl else 0
    sev = "ok" if not nf else "med" if aff < 15 else "high"
    return dict(cols=cols, rw=rw, cells=[names[ck[i]] if flag[i] else None for i in range(n)],
                flag=nf, leaf=nl, aff=round(aff, 1), key=key, sev=sev)


def process(img, src, auto):
    """Analyse one frame. Auto frames are stored only when a problem is found (Problem Gallery)."""
    t0 = time.perf_counter(); img = img.copy(); img.thumbnail((640, 640))
    if auto:
        STATE["frames"] += 1; STATE["last"] = datetime.now().strftime("%H:%M:%S")
    res = analyse(img)
    if res is None:
        return None
    res["ms"] = round((time.perf_counter() - t0) * 1000)
    if auto and res["key"] == "healthy":
        return res
    if auto: STATE["found"] += 1
    fn = uuid.uuid4().hex[:10] + ".jpg"; img.save(os.path.join(UP, fn), quality=88)
    with db() as c:
        cur = c.execute("INSERT INTO scans(ts,source,cond,affected,severity,file,data) VALUES(?,?,?,?,?,?,?)",
                        (datetime.now().isoformat(sep=" ", timespec="seconds"), src, res["key"], res["aff"], res["sev"], fn, json.dumps(res)))
        res["id"] = cur.lastrowid
    return res


@app.post("/api/analyze")
def api_analyze():
    f = request.files.get("image")
    if not f:
        return jsonify(error="no_file", message="No image received"), 400
    try:
        img = Image.open(f.stream).convert("RGB")
    except Exception:
        return jsonify(error="bad_image", message="Could not read this image"), 400
    src = request.form.get("source", "Upload"); src = src if src in SOURCES else "Upload"
    res = process(img, src, request.form.get("auto") == "1")
    if res is None:
        return jsonify(error="no_leaf", message="No clear leaf found. Try a closer photo of the leaf."), 422
    return jsonify(res)


def worker():
    """Pulls a photo from the drone camera every few seconds and checks it."""
    while True:
        url = CFG.get("url")
        if url:
            try:
                r = requests.get(f"http://{url}/capture", timeout=5); r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                STATE["last_ok"] = time.time()
                process(img, "Drone", True)
            except Exception:
                pass
        time.sleep(max(3, int(CFG.get("interval", 5))))


@app.post("/api/config")
def api_config():
    d = request.get_json(force=True, silent=True) or {}
    if "url" in d:
        CFG["url"] = re.sub(r"^https?://|/.*$", "", str(d["url"]).strip()); STATE["last_ok"] = 0
    if "interval" in d:
        try: CFG["interval"] = min(60, max(3, int(d["interval"])))
        except (TypeError, ValueError): pass
    if "farm" in d:
        CFG["farm"] = str(d["farm"])[:60]
    if d.get("mode") in ("landed", "flying"):
        CFG["mode"] = d["mode"]
    save_cfg(); return jsonify(CFG)


@app.get("/api/status")
def api_status():
    with db() as c:
        p = c.execute("SELECT COUNT(*) FROM scans WHERE cond != 'healthy'").fetchone()[0]
    return jsonify(url=CFG["url"], mode=CFG["mode"], connected=time.time() - STATE["last_ok"] < 15,
                   frames=STATE["frames"], last=STATE["last"], problems=p,
                   found=STATE["found"], interval=CFG["interval"], farm=CFG["farm"])


@app.get("/api/stream")
def api_stream():
    host = CFG.get("url", "").split(":")[0]
    if not host:
        return "", 404
    try:
        r = requests.get(f"http://{host}:81/stream", stream=True, timeout=5)
    except Exception:
        return "", 502
    return Response(stream_with_context(r.iter_content(4096)), content_type=r.headers.get("Content-Type", "multipart/x-mixed-replace"))


@app.get("/api/gallery")
def api_gallery():
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT id,ts,source,cond,affected,severity,file,data FROM scans WHERE cond != 'healthy' ORDER BY id DESC LIMIT 24")]
    for r in rows: r["data"] = json.loads(r["data"] or "{}")
    return jsonify(rows=rows)


@app.get("/uploads/<path:f>")
def uploads(f):
    return send_from_directory(UP, f)


def compose(lang, key, topics):
    i = LI.get(lang, 0); L = KB["L"]; e = KB["KB"][key or "healthy"]
    head = "" if key else L["nc"][i] + "\n"
    body = "\n".join(f"{L[k][i]}: {e[k][i]}" for k in topics)
    return head + e["n"][i] + "\n" + body + "\n\n" + L["note"][i]


@app.post("/api/chat")
def api_chat():
    d = request.get_json(force=True, silent=True) or {}
    text = str(d.get("text") or "")[:300]; lang = d.get("lang", "en"); key = d.get("key")
    topics = [t for t in (d.get("topics") or []) if t in ("why", "fix", "org", "prev")]
    key = key if key in KB["KB"] else None
    if not topics:
        if re.match(r"\s*(hi|hello|hey|help|namaste|नमस्ते|नमस्कार|मदद|मदत)", text, re.I):
            return jsonify(reply=HELLO[LI.get(lang, 0)])
        topics = [k for k in RX if RX[k].search(text)] or ["why", "fix", "org", "prev"]
    return jsonify(reply=compose(lang, key, topics))


@app.get("/api/scans")
def api_scans():
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT id,ts,source,cond,affected,severity FROM scans ORDER BY id DESC LIMIT 8")]
        t = c.execute("SELECT COUNT(*), SUM(cond != 'healthy') FROM scans").fetchone()
    return jsonify(rows=rows, total=t[0], problems=t[1] or 0)


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    print("AgriDrone running at http://127.0.0.1:5000")
    app.run(port=5000, threaded=True)
