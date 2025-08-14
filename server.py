from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os, re

app = Flask(__name__, static_url_path="", static_folder=".")
CORS(app)

DATA_FILE = "users.json"
ALLOWED_TRACKS = {
    "Consulting","Investment Banking","High Finance","GMAT","GRE","SAT","ACT",
    "CPA","CMA","CFA Level I","CFA Level II","CFA Level III"
}

# -------- storage ----------
def load_users():
    if not os.path.exists(DATA_FILE): return []
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
    if not valid_e164(phone): return ("Phone must be E.164 (e.g., +15551234567)", 400)  # enforce CC on signup
    if track not in ALLOWED_TRACKS: return ("Invalid track", 400)
    if per_day < 1 or per_day > 3: return ("per_day must be 1–3", 400)
    if not consent: return ("Consent is required", 400)

    users = load_users()
    existing = next((u for u in users if u["phone"] == phone), None)
    record = {
        "name": name, "phone": phone, "track": track,
        "per_day": per_day, "timezone": timezone, "consent": True,
        "stats": existing.get("stats") if existing else {"sent":0,"answered":0,"correct":0}
    }
    if existing: existing.update(record)
    else: users.append(record)
    save_users(users)
    return jsonify({"ok": True})

@app.get("/me")
def me():
    phone = request.args.get("phone","").strip()
    if not phone: return ("Phone required", 400)
    # allow 10-digit US lookup convenience
    if not phone.startswith("+"):
        digits = re.sub(r"\D","", phone)
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
