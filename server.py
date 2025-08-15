from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import json, os, re, random
from twilio.twiml.messaging_response import MessagingResponse

# Serve only from /static so secrets like users.json aren't downloadable
app = Flask(__name__, static_url_path="", static_folder="static")
CORS(app)

DATA_FILE = "users.json"
ALLOWED_TRACKS = {
    "Consulting","Investment Banking","High Finance",
    "GMAT","GRE","SAT","ACT","LSAT",
    "CPA","CMA","CFA Level I","CFA Level II","CFA Level III"
}

# -------- storage ----------
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

# --------- question generation / grading helpers ---------
def make_question(track: str):
    """
    Super-simple generator by track (you can expand later).
    Returns: (prompt_text, correct_numeric_answer, tiny_explainer)
    """
    a = random.randint(100, 999)
    b = random.randint(10, 99)
    if random.random() < 0.5:
        prompt = f"{a} - {b}"
        ans = a - b
        explain = f"Try rounding: {a} - {b} → {a} - {b//10*10} - {b%10}"
    else:
        prompt = f"{a} + {b}"
        ans = a + b
        explain = f"Break it up: {a} + {b} = {a}+{b//10*10}+{b%10}"
    return prompt, ans, explain

def level_text(stats):
    answered = max(1, stats.get("answered", 0))
    correct = stats.get("correct", 0)
    acc = correct / answered
    if answered < 5:
        return "Calibrating"
    if acc < 0.5:
        return "Warm-up"
    if acc < 0.7:
        return "Steady"
    if acc < 0.85:
        return "Strong"
    return "Elite"

def normalize_phone_from_form(raw: str) -> str:
    """
    Twilio sends E.164 in From, but for curl tests we normalize too.
    Accept 10-digit US convenience: '5084982017' -> '+15084982017'
    """
    p = (raw or "").strip()
    if p.startswith("+"):
        return p
    digits = re.sub(r"\D", "", p)
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return p

def twiml(text: str):
    resp = MessagingResponse()
    resp.message(text)
    return str(resp)

# -------- API ----------
@app.post("/signup")
def signup():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    phone = (data.get("phone") or "").strip()
    track = (data.get("track") or "").strip()
    per_day = int(data.get("per_day") or 1)
    timezone = (data.get("timezone") or "America/New_York").strip()
    consent = bool(data.get("consent"))

    if not name: return ("Name required", 400)
    if not valid_e164(phone): return ("Phone must be E.164 (e.g., +15551234567)", 400)
    if track not in ALLOWED_TRACKS: return ("Invalid track", 400)
    if per_day < 1 or per_day > 3: return ("per_day must be 1–3", 400)
    if not consent: return ("Consent is required", 400)

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
        "last_q": existing.get("last_q") if existing else None,
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
    # allow 10-digit US lookup convenience
    if not phone.startswith("+"):
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            phone = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            phone = "+" + digits
    if not valid_e164(phone): return ("Phone must be E.164 or 10-digit US", 400)
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

# -------- SMS webhook ----------
@app.route("/sms", methods=["POST"])
def sms():
    """
    Handles incoming SMS (or curl-simulated) messages.
    Commands:
      - ANOTHER / NEXT: send a new question
      - STATS: show accuracy and level
      - <number>: grade against last question
    """
    from_number = normalize_phone_from_form(request.form.get("From", ""))
    body_raw = request.form.get("Body", "") or ""
    body = body_raw.strip()

    # Look up user
    u, users = get_user(from_number)
    if not u:
        return twiml(
            "Hi! I don't see you yet. Please sign up on the website first "
            "so I know your track and timezone."
        )

    # Commands
    upper = body.upper()
    if upper in ("ANOTHER", "NEXT"):
        q, ans, expl = make_question(u["track"])
        u["last_q"] = {"q": q, "ans": ans, "expl": expl}
        stats = u.setdefault("stats", {"sent": 0, "answered": 0, "correct": 0})
        stats["sent"] = stats.get("sent", 0) + 1
        save_users(users)
        return twiml(f"{u['name']}, try this: {q}")

    if upper == "STATS":
        stats = u.setdefault("stats", {"sent": 0, "answered": 0, "correct": 0})
        answered = stats.get("answered", 0)
        correct = stats.get("correct", 0)
        acc = 0 if answered == 0 else round(correct / answered * 100)
        lvl = level_text(stats)
        return twiml(f"Stats — Sent:{stats.get('sent',0)} Answered:{answered} "
                     f"Correct:{correct} ({acc}%). Level: {lvl}.")

    # Numeric answer?
    if re.fullmatch(r"-?\d+", body):
        if not u.get("last_q"):
            return twiml("I don't have a current question. Reply ANOTHER to get one.")

        try:
            guess = int(body)
        except Exception:
            return twiml("Please reply with a number, or say ANOTHER for a new question.")

        correct_ans = int(u["last_q"]["ans"])
        stats = u.setdefault("stats", {"sent": 0, "answered": 0, "correct": 0})
        stats["answered"] = stats.get("answered", 0) + 1
        if guess == correct_ans:
            stats["correct"] = stats.get("correct", 0) + 1
            save_users(users)
            return twiml("Correct! Nice work. Text ANOTHER for a new one.")
        else:
            hint = u["last_q"].get("expl", "Try rounding or breaking it up.")
            save_users(users)
            return twiml(f"Incorrect. A tip: {hint}. Try ANOTHER for a fresh one.")

    # Fallback help
    return twiml("Commands: ANOTHER for a new question, reply with a number to answer, "
                 "STATS to see your progress.")

# -------- admin (token-protected) ----------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

def _require_admin():
    token = request.headers.get("X-Admin-Token") or request.args.get("token")
    if not ADMIN_TOKEN or token != ADMIN_TOKEN:
        abort(403)

@app.get("/__admin/users")
def admin_users():
    _require_admin()
    return jsonify(load_users())

@app.get("/__admin/users_redacted")
def admin_users_redacted():
    _require_admin()
    redacted = []
    for u in load_users():
        redacted.append({
            "name": u.get("name"),
            "phone_suffix": (u.get("phone","")[-4:] if u.get("phone") else ""),
            "track": u.get("track"),
            "per_day": u.get("per_day"),
            "timezone": u.get("timezone"),
            "stats": u.get("stats", {}),
        })
    return jsonify(redacted)

# -------- pages ----------
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
