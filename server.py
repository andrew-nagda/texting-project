# server.py (minimal changes: add TWILIO env + immediate SMS on signup)
import os, re, json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from twilio.rest import Client

# track/question logic
from tracks import (
    QUESTIONS,
    pick_sample_question,
    grade_answer,
    make_math_question,
    grade_math_q,
)

# -----------------------------
# App & static pages
# -----------------------------
app = Flask(__name__, static_url_path="", static_folder=".")
CORS(app)

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
# Env & Twilio
# -----------------------------
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM        = os.getenv("TWILIO_FROM", "").strip()  # <-- put your toll-free number here (E.164), e.g. +18885551234

_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else None

def send_sms(to: str, body: str):
    """Send an SMS via Twilio if creds are present."""
    if not (_twilio and TWILIO_FROM and to and body):
        return
    _twilio.messages.create(from_=TWILIO_FROM, to=to, body=body)

# -----------------------------
# Persistence
# -----------------------------
USERS_FILE = os.getenv("USERS_FILE", "users.json")

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            # if old format was a dict keyed by phone, normalize back to list
            return list(data.values())
    except Exception:
        return []

def save_users(users_list):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users_list, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USERS_FILE)

def normalize_phone(phone: str) -> str:
    s = (phone or "").strip()
    if not s:
        return ""
    if s.startswith("+"):
        return s
    digits = re.sub(r"\D", "", s)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return s  # fall back to original

# -----------------------------
# API: signup (minimal change: immediate SMS)
# -----------------------------
@app.post("/signup")
def signup():
    """
    Expected JSON body:
    { name, phone, track, per_day, timezone, consent }
    """
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = normalize_phone(data.get("phone") or "")
    track = (data.get("track") or "Consulting").strip()
    per_day = int(data.get("per_day") or 1)
    timezone = (data.get("timezone") or "").strip()
    consent = bool(data.get("consent"))

    if not phone:
        return jsonify({"error": "Phone required"}), 400

    users = load_users()
    # update if existing phone, else append
    record = {
        "name": name,
        "phone": phone,
        "track": track,
        "per_day": max(1, min(3, per_day)),
        "timezone": timezone,
        "consent": consent,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    # retain created_at if present
    existing = next((u for u in users if u.get("phone") == phone), None)
    if existing:
        record["created_at"] = existing.get("created_at") or datetime.utcnow().isoformat() + "Z"
        # preserve any stats/open if your original app stored them
        for k in ("stats", "open", "daily_schedule", "subscribed", "next_delivery"):
            if k in existing and k not in record:
                record[k] = existing[k]
        # replace
        idx = users.index(existing)
        users[idx] = record
    else:
        record["created_at"] = datetime.utcnow().isoformat() + "Z"
        users.append(record)

    save_users(users)

    # ---- Minimal addition: immediate SMS on signup ----
    instructions = (
        "Welcome to BrainTrain Daily!\n"
        "How it works:\n"
        "• We’ll text you practice questions.\n"
        "• Reply with your answer for instant feedback.\n"
        "• Text STOP any time to unsubscribe."
    )

    # Use existing track logic to craft first question text
    first_q_text = None
    try:
        q = pick_sample_question(track)
        if isinstance(q, dict) and q.get("q"):
            labels = "ABCDE"
            lines = [q["q"]]
            for i, choice in enumerate(q.get("choices") or []):
                if i >= len(labels): break
                lines.append(f"{labels[i]}. {choice}")
            if q.get("choices"):
                lines.append("Reply with A–E.")
            first_q_text = "\n".join(lines)
    except Exception:
        first_q_text = None

    if not first_q_text:
        # fallback to math
        try:
            mq = make_math_question(track) or make_math_question("General")
            first_q_text = mq["question"]
        except Exception:
            first_q_text = "First question coming up—reply NEXT if you don’t see it."

    send_sms(phone, instructions + "\n\n" + first_q_text)
    # ---------------------------------------------------

    return jsonify({"ok": True})

# Optional helper endpoints (left unchanged; included to avoid breaking existing pages)
@app.get("/me")
def me():
    phone = normalize_phone(request.args.get("phone") or "")
    if not phone:
        return ("Phone required", 400)
    users = load_users()
    u = next((u for u in users if u.get("phone") == phone), None)
    if not u:
        return ("Not found", 404)
    return jsonify(u)

@app.post("/update")
def update():
    data = request.get_json(force=True, silent=True) or {}
    phone = normalize_phone(data.get("phone") or "")
    if not phone:
        return jsonify({"error": "Phone required"}), 400
    users = load_users()
    u = next((u for u in users if u.get("phone") == phone), None)
    if not u:
        return jsonify({"error": "Not found"}), 404
    # allow updating basic prefs
    for key in ("name", "track", "per_day", "timezone"):
        if key in data and data[key] is not None:
            u[key] = data[key]
    u["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_users(users)
    return jsonify({"ok": True})

# -----------------------------
# Dev server
# -----------------------------
if __name__ == "__main__":
    # Flask will serve the static HTML files from current dir
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)
