# server.py (diagnostic-friendly: /sms accepts GET & POST)
import os, re, json
from datetime import datetime
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv
from twilio.rest import Client

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
TWILIO_FROM        = os.getenv("TWILIO_FROM", "").strip()

_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else None

def send_sms(to: str, body: str):
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
    return s

# -----------------------------
# Signup: create/update user + immediate SMS
# -----------------------------
@app.post("/signup")
def signup():
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
    record = {
        "name": name,
        "phone": phone,
        "track": track,
        "per_day": max(1, min(3, per_day)),
        "timezone": timezone,
        "consent": consent,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    existing = next((u for u in users if u.get("phone") == phone), None)
    if existing:
        record["created_at"] = existing.get("created_at") or datetime.utcnow().isoformat() + "Z"
        for k in ("stats", "open", "daily_schedule", "subscribed", "next_delivery"):
            if k in existing and k not in record:
                record[k] = existing[k]
        users[users.index(existing)] = record
    else:
        record["created_at"] = datetime.utcnow().isoformat() + "Z"
        users.append(record)

    save_users(users)

    # Immediate welcome + first question
    instructions = (
        "Welcome to BrainTrain Daily!\n"
        "How it works:\n"
        "• We’ll text you practice questions.\n"
        "• Reply with your answer for instant feedback.\n"
        "• Text STOP any time to unsubscribe."
    )
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
        try:
            mq = make_math_question(track) or make_math_question("General")
            first_q_text = mq["question"]
        except Exception:
            first_q_text = "First question coming up—reply NEXT if you don’t see it."

    send_sms(phone, instructions + "\n\n" + first_q_text)
    return jsonify({"ok": True})

# -----------------------------
# Basic prefs endpoints (unchanged)
# -----------------------------
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
    for key in ("name", "track", "per_day", "timezone"):
        if key in data and data[key] is not None:
            u[key] = data[key]
    u["updated_at"] = datetime.utcnow().isoformat() + "Z"
    save_users(users)
    return jsonify({"ok": True})

# -----------------------------
# Twilio SMS webhook
# -----------------------------
def reply_twiml(*messages):
    parts = [f"<Message>{m}</Message>" for m in messages if m]
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{"".join(parts)}</Response>'
    return Response(xml, status=200, mimetype="application/xml")

# Allow GET temporarily so you can visit /sms in a browser and see "OK".
@app.route("/sms", methods=["GET", "POST"])
def sms_webhook():
    if request.method == "GET":
        # Diagnostic response so you know this service is the one Twilio should hit.
        return Response("OK: /sms endpoint is reachable (GET). Twilio must use POST.", mimetype="text/plain", status=200)

    # POST (from Twilio)
    from_phone = (request.values.get("From") or "").strip()
    body = (request.values.get("Body") or "").strip().upper()

    if body == "HELP":
        return reply_twiml(
            "Commands:",
            "NEXT - get a new question now",
            "STOP - unsubscribe"
        )

    if body == "NEXT" or body == "":
        # Simple placeholder; you can wire this to tracks.py if desired.
        return reply_twiml("Here’s your next question!")

    return reply_twiml("Reply NEXT for a question, or HELP for commands.")

# -----------------------------
# Dev server
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)
