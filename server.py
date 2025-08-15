# server.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, re, requests

# import track logic from separate module
from tracks import (
    QUESTIONS,
    pick_sample_question,
    grade_answer,
    make_math_question,
    grade_math_q,
)

app = Flask(__name__, static_url_path="", static_folder="static")
CORS(app)

# -----------------------------
# Storage & config
# -----------------------------
DATA_FILE = "users.json"

ALLOWED_TRACKS = set(QUESTIONS.keys()) | {
    "High Finance",  # included above but ensure set covers everything
    "CPA", "CMA",
    "CFA Level I", "CFA Level II", "CFA Level III",
}

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
BACKUP_RAW_URL = os.getenv("BACKUP_RAW_URL", "")
BACKUP_TOKEN = os.getenv("BACKUP_TOKEN", "")

# -----------------------------
# Startup: restore users.json from backup
# -----------------------------
def restore_from_backup():
    if not BACKUP_RAW_URL:
        print("[startup] No BACKUP_RAW_URL set; skipping restore.")
        return
    try:
        headers = {}
        if BACKUP_TOKEN:
            headers["Authorization"] = f"Bearer {BACKUP_TOKEN}"
        r = requests.get(BACKUP_RAW_URL, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"[startup] Restored {len(data)} users from backup.")
        else:
            print("[startup] Backup fetched but not a list; skipping write.")
    except Exception as e:
        print(f"[startup] Could not restore users: {e}")

restore_from_backup()

# -----------------------------
# Utilities
# -----------------------------
def load_users():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_users(users):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)

def get_user(phone):
    users = load_users()
    for u in users:
        if u.get("phone") == phone:
            return u, users
    return None, users

def valid_e164(p: str) -> bool:
    return bool(re.fullmatch(r"\+[1-9]\d{7,14}", p or ""))

# -----------------------------
# API: signup / profile
# -----------------------------
@app.post("/signup")
def signup():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    track = (data.get("track") or "").strip()
    per_day = int(data.get("per_day") or 1)
    timezone = (data.get("timezone") or "America/New_York").strip()
    consent = bool(data.get("consent"))

    if not name:
        return ("Name required", 400)
    if not valid_e164(phone):
        return ("Phone must be E.164 (e.g., +15551234567)", 400)
    if track not in ALLOWED_TRACKS:
        return ("Invalid track", 400)
    if per_day < 1 or per_day > 3:
        return ("per_day must be 1–3", 400)
    if not consent:
        return ("Consent is required", 400)

    users = load_users()
    existing = next((u for u in users if u["phone"] == phone), None)
    record = {
        "name": name,
        "phone": phone,
        "track": track,
        "per_day": per_day,
        "timezone": timezone,
        "consent": True,
        "stats": existing.get("stats") if existing else {"sent": 0, "answered": 0, "correct": 0},
    }
    if existing:
        existing.update(record)
    else:
        users.append(record)
    save_users(users)
    return jsonify({"ok": True})

@app.get("/me")
def me():
    phone = request.args.get("phone", "").strip()
    if not phone: return ("Phone required", 400)
    if not phone.startswith("+"):
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            phone = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            phone = "+" + digits
    if not valid_e164(phone):
        return ("Phone must be E.164 or 10-digit US", 400)
    u, _ = get_user(phone)
    if not u: return ("Not found", 404)
    return jsonify(u)

@app.post("/update")
def update():
    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get("phone") or "").strip()
    if not valid_e164(phone): return ("Phone must be E.164", 400)
    u, users = get_user(phone)
    if not u: return ("User not found", 404)

    name = (data.get("name") or u["name"]).strip()
    track = (data.get("track") or u["track"]).strip()
    per_day = int(data.get("per_day") or u["per_day"])
    timezone = (data.get("timezone") or u["timezone"]).strip()

    if track not in ALLOWED_TRACKS: return ("Invalid track", 400)
    if per_day < 1 or per_day > 3: return ("per_day must be 1–3", 400)

    u.update({"name": name, "track": track, "per_day": per_day, "timezone": timezone})
    save_users(users)
    return jsonify({"ok": True})

# -----------------------------
# Admin (read-only)
# -----------------------------
@app.get("/__admin/users")
def admin_users():
    token = request.args.get("token", "")
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        return ("Unauthorized", 401)
    return jsonify(load_users())

# -----------------------------
# Knowledge quiz endpoints
# -----------------------------
@app.get("/quiz/sample")
def quiz_sample():
    track = request.args.get("track", "").strip()
    if track not in ALLOWED_TRACKS:
        return ("Invalid track", 400)
    q = pick_sample_question(track)
    if not q:
        return jsonify({"message": "No questions yet for this track."})
    return jsonify({"qid": q["id"], "track": track, "question": q["q"], "choices": q.get("choices")})

@app.post("/quiz/grade")
def quiz_grade():
    data = request.get_json(force=True, silent=True) or {}
    track = (data.get("track") or "").strip()
    qid = (data.get("qid") or "").strip()
    answer = (data.get("answer") or "").strip()
    if track not in ALLOWED_TRACKS: return ("Invalid track", 400)
    if not qid or not answer: return ("qid and answer required", 400)
    result = grade_answer(track, qid, answer)
    return jsonify(result)

# -----------------------------
# Mental math endpoints
# -----------------------------
@app.get("/math/sample")
def math_sample():
    track = (request.args.get("track") or "General").strip()
    if track not in {"General", "Consulting", "Investment Banking"}:
        return ("Invalid track", 400)
    q = make_math_question(track)
    if not q:
        return jsonify({"message": "No math generator for this track yet."})
    return jsonify({"qid": q["qid"], "track": track, "question": q["question"], "units": q.get("units")})

@app.post("/math/grade")
def math_grade():
    data = request.get_json(force=True, silent=True) or {}
    track = (data.get("track") or "").strip()
    qid = (data.get("qid") or "").strip()
    answer = (data.get("answer") or "").strip()
    if track not in {"General", "Consulting", "Investment Banking"}: return ("Invalid track", 400)
    if not qid or not answer: return ("qid and answer required", 400)
    result = grade_math_q(track, qid, answer)
    return jsonify(result)

# -----------------------------
# Minimal SMS webhook (HELP)
# -----------------------------
@app.post("/sms")
def sms_inbound():
    body = (request.values.get("Body") or "").strip().upper()
    if body == "HELP":
        msg = (
            "Commands:\n"
            "- HELP : this list\n"
            "- QUIZ <Track> : knowledge Q\n"
            "- MATH GENERAL : quick arithmetic\n"
            "- MATH CONSULTING : breakeven/target volume\n"
            "- MATH IB : IRR-style mental math\n"
            "To grade: GRADE <qid> | <answer>"
        )
    else:
        msg = "Text HELP for available commands."
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{msg}</Message></Response>'
    return twiml, 200, {"Content-Type": "application/xml; charset=utf-8"}

# -----------------------------
# Static pages
# -----------------------------
@app.get("/")
def home_page():
    return app.send_static_file("home.html")

@app.get("/join")
def join_page():
    return app.send_static_file("signup.html")

@app.get("/preferences")
def preferences_page():
    return app.send_static_file("preferences.html")

@app.get("/how")
def how_page():
    return app.send_static_file("how.html")

# -----------------------------
# Local dev
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
