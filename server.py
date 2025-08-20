# server.py — randomized per-user scheduling, grading, tracks-aware
import os, re, json, html, random
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv

from apscheduler.schedulers.background import BackgroundScheduler
import pytz

from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

# Your track / question logic
from tracks import (
    QUESTIONS,              # dict of tracks
    pick_sample_question,   # returns {id, q, choices, ...}
    make_math_question,     # returns {qid, question, ...}
    grade_answer,           # (track, qid, user_answer) -> {correct, rationale, tip}
    grade_math_q,           # (qid, user_answer) -> {correct, expected, units, rationale}
)

# -----------------------------
# App & static hosting
# -----------------------------
load_dotenv()

# IMPORTANT: static files are in ./static
app = Flask(__name__, static_url_path="", static_folder="static")
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
# Config
# -----------------------------
DEFAULT_TZ = os.getenv("DEFAULT_TZ", "America/New_York")
WINDOW_START_HOUR = int(os.getenv("WINDOW_START_HOUR", "9"))   # 09:00 local
WINDOW_END_HOUR   = int(os.getenv("WINDOW_END_HOUR", "22"))    # 22:00 local

USERS_FILE = os.getenv("USERS_FILE", "users.json")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM        = os.getenv("TWILIO_FROM", "").strip()

_twilio = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else None

def send_sms(to: str, body: str):
    """Send an SMS via Twilio (no-op if creds missing)."""
    if not (_twilio and TWILIO_FROM and to and body):
        return
    _twilio.messages.create(from_=TWILIO_FROM, to=to, body=body)

# -----------------------------
# Persistence helpers
# -----------------------------
def _load_users():
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else list(data.values())
    except Exception:
        return []

def _save_users(users_list):
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(users_list, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USERS_FILE)

def _normalize_phone(phone: str) -> str:
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

def _list_tracks():
    return list(QUESTIONS.keys())

def _user_tz(user):
    tzname = (user.get("timezone") or DEFAULT_TZ).strip() or DEFAULT_TZ
    try:
        return pytz.timezone(tzname)
    except Exception:
        return pytz.timezone(DEFAULT_TZ)

def _today_local_date_str(tz):
    return datetime.now(tz).strftime("%Y-%m-%d")

def _now_utc_minute():
    return datetime.utcnow().replace(second=0, microsecond=0, tzinfo=pytz.UTC)

def _ensure_user(phone: str):
    phone = _normalize_phone(phone)
    users = _load_users()
    u = next((u for u in users if u.get("phone") == phone), None)
    if u is None:
        u = {
            "phone": phone,
            "name": "",
            "track": "Consulting",
            "per_day": 1,
            "timezone": DEFAULT_TZ,
            "subscribed": True,
            "open": None,  # holds current open question payload
            "stats": {"asked": 0, "correct": 0, "streak": 0},
            "schedule": {"local_date": None, "remaining_utc": []},
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        users.append(u)
        _save_users(users)
    return u, users

# -----------------------------
# Building/sending questions
# -----------------------------
def _compose_question_text(track: str):
    """
    Prefer a sample MCQ from the chosen track; fall back to a math question.
    Returns (text, payload_for_open).
    """
    # A) Sample MCQ
    try:
        q = pick_sample_question(track)
        if isinstance(q, dict) and q.get("q"):
            labels = "ABCDE"
            lines = [q["q"]]
            for i, choice in enumerate(q.get("choices") or []):
                if i >= len(labels):
                    break
                lines.append(f"{labels[i]}. {choice}")
            if q.get("choices"):
                lines.append("Reply with A–E.")
            payload = {"kind": "sample", "track": track, "qid": q.get("id")}
            return "\n".join(lines), payload
    except Exception:
        pass

    # B) Math fallback
    try:
        m = make_math_question(track) or make_math_question("General")
        payload = {"kind": "math", "qid": m.get("qid")}
        return m["question"], payload
    except Exception:
        pass

    return "Sorry, I couldn’t generate a question right now. Please text NEXT again.", {"kind": "none"}

def _open_and_send_question(user):
    text, payload = _compose_question_text(user.get("track", "Consulting"))
    user["open"] = payload
    user["updated_at"] = datetime.utcnow().isoformat() + "Z"
    send_sms(user["phone"], text)
    return text

# -----------------------------
# Grading & feedback
# -----------------------------
def _grade_open(user, raw_text: str):
    """
    Grade the user's reply against the currently open question and
    include 'how to do better' (tip) from tracks.py when available.
    """
    open_q = user.get("open")
    if not open_q:
        return None

    ans_text = (raw_text or "").strip()

    # A) Sample multiple choice (A–E)
    if open_q.get("kind") == "sample":
        track = open_q.get("track") or "Consulting"
        qid = open_q.get("qid")
        res = grade_answer(track, qid, ans_text)
        if "error" in res:
            return {"body": "Sorry—I couldn’t grade that. Reply with A, B, C, D, or E."}

        correct = bool(res.get("correct"))
        user["stats"]["asked"] += 1
        if correct:
            user["stats"]["correct"] += 1
            user["stats"]["streak"] = user["stats"].get("streak", 0) + 1
        else:
            user["stats"]["streak"] = 0
        user["open"] = None
        user["updated_at"] = datetime.utcnow().isoformat() + "Z"

        parts = ["Correct." if correct else "Not quite."]
        if res.get("rationale"):
            parts.append(f"Why: {res['rationale']}")
        if res.get("tip"):  # << how to do better next time
            parts.append(f"Tip: {res['tip']}")
        parts.append("Reply NEXT for another question.")
        return {"body": "\n".join(parts)}

    # B) Math numeric
    if open_q.get("kind") == "math":
        qid = open_q.get("qid")
        res = grade_math_q(qid, ans_text)
        if "error" in res:
            return {"body": "I couldn’t parse that number. Try digits (and % if needed)."}

        correct = bool(res.get("correct"))
        user["stats"]["asked"] += 1
        if correct:
            user["stats"]["correct"] += 1
            user["stats"]["streak"] = user["stats"].get("streak", 0) + 1
        else:
            user["stats"]["streak"] = 0
        user["open"] = None
        user["updated_at"] = datetime.utcnow().isoformat() + "Z"

        expected = res.get("expected")
        units = res.get("units") or ""
        parts = ["Correct." if correct else f"Not quite. Expected {expected}{(' ' + units) if units else ''}."]
        if res.get("rationale"):
            parts.append(f"Why: {res['rationale']}")
        if res.get("tip"):
            parts.append(f"Tip: {res['tip']}")
        parts.append("Reply NEXT for another question.")
        return {"body": "\n".join(parts)}

    return {"body": "Unknown question type. Reply NEXT for a new one."}

# -----------------------------
# Random schedule per user
# -----------------------------
def _rand_local_minutes(n: int, tz):
    """
    Pick n unique random minute instants today between WINDOW_START_HOUR and WINDOW_END_HOUR
    in the user's local tz.
    """
    n = max(1, min(3, int(n)))
    today = datetime.now(tz).replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    end = today.replace(hour=WINDOW_END_HOUR, minute=0)
    span = max(0, int((end - today).total_seconds() // 60))
    chosen = set()
    while len(chosen) < n:
        offset = random.randint(0, span)
        when = today + timedelta(minutes=offset)
        when = when.replace(second=0, microsecond=0)
        chosen.add(when)
    return sorted(list(chosen))

def _ensure_todays_schedule(user):
    tz = _user_tz(user)
    today_local = _today_local_date_str(tz)
    sched = user.get("schedule") or {}
    if sched.get("local_date") != today_local:
        per_day = max(1, min(3, int(user.get("per_day") or 1)))
        local_slots = _rand_local_minutes(per_day, tz)
        remaining_utc = [slot.astimezone(pytz.UTC).isoformat() for slot in local_slots]
        user["schedule"] = {"local_date": today_local, "remaining_utc": remaining_utc}
        user["updated_at"] = datetime.utcnow().isoformat() + "Z"

def _pop_due_utc(user):
    remaining = (user.get("schedule") or {}).get("remaining_utc", [])
    if not remaining:
        return []
    now_utc_iso = _now_utc_minute().isoformat()
    due = [t for t in remaining if t <= now_utc_iso]
    if due:
        user["schedule"]["remaining_utc"] = [t for t in remaining if t > now_utc_iso]
        user["updated_at"] = datetime.utcnow().isoformat() + "Z"
    return due

scheduler = BackgroundScheduler(timezone=pytz.UTC)

def _minute_tick():
    users = _load_users()
    changed = False
    for u in users:
        if not u.get("subscribed", True):
            continue
        _ensure_todays_schedule(u)
        due = _pop_due_utc(u)
        if due:
            for _ in due:
                _open_and_send_question(u)
            changed = True
    if changed:
        _save_users(users)

scheduler.add_job(_minute_tick, "interval", minutes=1, id="minute_tick", replace_existing=True)
scheduler.start()

# -----------------------------
# Twilio helpers
# -----------------------------
def _twiml(*messages):
    """Generate a TwiML response with one message per argument."""
    resp = MessagingResponse()
    for m in messages:
        if m:
            resp.message(m)
    return Response(str(resp), status=200, mimetype="application/xml")

def _welcome_text(user):
    tzname = (user.get("timezone") or DEFAULT_TZ).split("/")[-1]
    return (
        "Welcome to BrainTrain Daily!\n"
        f"You’ll receive {user.get('per_day',1)} question(s) randomly between "
        f"{WINDOW_START_HOUR:02d}:00–{WINDOW_END_HOUR:02d}:00 {tzname}.\n"
        "Commands: HELP, NEXT, TRACK <name>, FREQ <1-3>, TIMEZONE <Area/City>.\n"
        "Unsubscribe any time: STOP."
    )

# -----------------------------
# Public API (signup + prefs)
# -----------------------------
@app.post("/signup")
def signup():
    """
    JSON body: {phone, name?, track?, per_day?, timezone?}
    - creates/updates the user
    - sends onboarding + first question immediately
    - builds today’s schedule for future random sends
    """
    data = request.get_json(force=True, silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    if not phone:
        return jsonify({"error": "Phone required"}), 400

    u, users = _ensure_user(phone)
    for k in ("name", "track", "timezone"):
        if data.get(k) is not None:
            u[k] = data[k]
    if data.get("per_day") is not None:
        try:
            u["per_day"] = max(1, min(3, int(data["per_day"])))
        except Exception:
            pass

    u["subscribed"] = True
    tz = _user_tz(u)
    u["schedule"] = {"local_date": _today_local_date_str(tz), "remaining_utc": []}
    _ensure_todays_schedule(u)
    _save_users(users)

    # Onboarding + first question right now
    instructions = _welcome_text(u)
    text, payload = _compose_question_text(u.get("track", "Consulting"))
    u["open"] = payload
    _save_users(users)
    send_sms(u["phone"], instructions + "\n\n" + text)

    return jsonify({"ok": True})

@app.get("/me")
def me():
    phone = _normalize_phone(request.args.get("phone") or "")
    if not phone:
        return ("Phone required", 400)
    users = _load_users()
    u = next((u for u in users if u.get("phone") == phone), None)
    if not u:
        return ("Not found", 404)
    return jsonify(u)

@app.post("/update")
def update():
    data = request.get_json(force=True, silent=True) or {}
    phone = _normalize_phone(data.get("phone") or "")
    if not phone:
        return jsonify({"error": "Phone required"}), 400
    users = _load_users()
    u = next((u for u in users if u.get("phone") == phone), None)
    if not u:
        return jsonify({"error": "Not found"}), 404

    if data.get("name") is not None: u["name"] = data["name"]
    if data.get("track") is not None: u["track"] = data["track"]
    if data.get("timezone") is not None: u["timezone"] = data["timezone"]
    if data.get("per_day") is not None:
        try:
            u["per_day"] = max(1, min(3, int(data["per_day"])))
        except Exception:
            pass
    u["updated_at"] = datetime.utcnow().isoformat() + "Z"
    _save_users(users)
    return jsonify({"ok": True})

# -----------------------------
# Twilio webhook
# -----------------------------
@app.route("/sms", methods=["GET", "POST"])
def sms():
    if request.method == "GET":
        return Response("OK: /sms reachable. Twilio must POST.", mimetype="text/plain")

    from_phone = _normalize_phone(request.values.get("From") or "")
    body = (request.values.get("Body") or "").strip()

    u, users = _ensure_user(from_phone)
    text_upper = body.upper()

    # Opt-out / in
    if text_upper in {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}:
        u["subscribed"] = False
        _save_users(users)
        return _twiml("You have been unsubscribed. Text START to re-subscribe.")
    if text_upper == "START":
        u["subscribed"] = True
        _save_users(users)
        return _twiml("You are re-subscribed.", _welcome_text(u))

    # HELP
    if text_upper in {"HELP", "H", "?"}:
        tracks_line = ", ".join(_list_tracks()[:10]) + ("..." if len(_list_tracks()) > 10 else "")
        return _twiml(
            "Commands:",
            "NEXT — new question now",
            "TRACK <name> — change topic",
            "FREQ <1-3> — messages/day",
            "TIMEZONE <Area/City> — set your zone",
            f"Tracks: {tracks_line}",
            "STOP — unsubscribe"
        )

    # TRACK change
    if text_upper.startswith("TRACK "):
        _, _, maybe = body.partition(" ")
        choice = (maybe or "").strip()
        if choice not in QUESTIONS:
            return _twiml("Unknown track. Options: " + ", ".join(_list_tracks()))
        u["track"] = choice
        _save_users(users)
        text, payload = _compose_question_text(choice)  # send a fresh question in the new track
        u["open"] = payload
        _save_users(users)
        return _twiml(f"Track changed to {choice}.", text)

    # FREQ change
    if text_upper.startswith("FREQ "):
        _, _, maybe = body.partition(" ")
        digits = re.sub(r"\D", "", maybe or "")
        if not digits:
            return _twiml("Please send FREQ 1, FREQ 2, or FREQ 3.")
        val = max(1, min(3, int(digits)))
        u["per_day"] = val
        tz = _user_tz(u)
        u["schedule"] = {"local_date": _today_local_date_str(tz), "remaining_utc": []}
        _ensure_todays_schedule(u)
        _save_users(users)
        return _twiml(f"Frequency updated: {val} per day between {WINDOW_START_HOUR:02d}:00–{WINDOW_END_HOUR:02d}:00.")

    # TIMEZONE change
    if text_upper.startswith("TIMEZONE "):
        _, _, maybe = body.partition(" ")
        z = (maybe or "").strip()
        try:
            pytz.timezone(z)
        except Exception:
            return _twiml("Invalid timezone. Example: TIMEZONE America/Los_Angeles")
        u["timezone"] = z
        u["schedule"] = {"local_date": _today_local_date_str(_user_tz(u)), "remaining_utc": []}
        _ensure_todays_schedule(u)
        _save_users(users)
        return _twiml(f"Timezone set to {z}.")

    # NEXT (or empty)
    if text_upper == "NEXT" or body.strip() == "":
        text, payload = _compose_question_text(u.get("track", "Consulting"))
        u["open"] = payload
        _save_users(users)
        return _twiml(text)

    # Otherwise: try grading if there’s an open question
    graded = _grade_open(u, body)
    if graded:
        _save_users(users)
        return _twiml(graded["body"])

    # Fallback
    return _twiml("Reply NEXT for a new question or HELP for commands.")

# -----------------------------
# Entrypoint
# -----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=True)
