# app_cli.py
import os, re, math, random, datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

# --- Optional OpenAI explanations ---
from dotenv import load_dotenv
load_dotenv()
USE_OAI = os.getenv("USE_OPENAI_EXPLANATIONS", "true").lower() == "true"
oai = None
if USE_OAI:
    try:
        from openai import OpenAI
        oai = OpenAI()
    except Exception:
        USE_OAI = False  # fall back to built-in explanations

# ---------------------------
# Question generators by track
# ---------------------------
def gen_consulting() -> Tuple[str, str]:
    price = random.randint(12, 28)
    var = random.randint(3, max(4, int(price * 0.7)))
    fixed = random.choice([3000, 4000, 5000, 6000, 8000])
    be = math.ceil(fixed / (price - var))
    q = f"[Consulting] Price ${price}, Var ${var}, Fixed ${fixed}. Breakeven units?"
    return q, str(be)

def gen_ib() -> Tuple[str, str]:
    ni = random.choice([200_000, 400_000, 600_000, 800_000])
    sh = random.choice([20_000, 50_000, 100_000])
    q = f"[IB] Net income ${ni}, shares {sh}. EPS (2dp)?"
    return q, f"{ni/sh:.2f}"

def gen_lsat() -> Tuple[str, str]:
    q = ("[LSAT] Which flaw? 'All swans observed are white; therefore all swans are white.' "
         "A) Causation B) Hasty generalization C) Circular D) Equivocation E) Ad hominem")
    return q, "B"

GEN_BY_TRACK = {
    "consulting": gen_consulting,
    "ib": gen_ib,
    "lsat": gen_lsat,
}

# ---------------------------
# User model
# ---------------------------
@dataclass
class User:
    name: str
    track: str = "consulting"
    per_day: int = 3
    queue: List[Tuple[str, str]] = field(default_factory=list)  # list of (q, a)
    open_idx: Optional[int] = None
    correct: int = 0
    total: int = 0

    def seed_today(self):
        self.queue.clear()
        for _ in range(self.per_day):
            q, a = GEN_BY_TRACK[self.track]()
            self.queue.append((q, a))
        self.open_idx = None

# ---------------------------
# Grading and explanations
# ---------------------------
def grade(user_text: str, correct: str) -> Tuple[str, Optional[str]]:
    t = user_text.strip().upper()
    if t == "HINT":
        return "hint", None
    # numeric grading
    if re.fullmatch(r"-?\d+(\.\d+)?", correct or ""):
        nums = re.findall(r"-?\d+(\.\d+)?", t)
        if not nums:
            return "unknown", None
        ok = abs(float(nums[0]) - float(correct)) < 1e-6
        return ("correct" if ok else "incorrect", nums[0])
    # multiple choice grading
    if correct in "ABCDE" and t in "ABCDE":
        return ("correct" if t == correct else "incorrect", t)
    return "unknown", None

def explain_with_oai(question: str, answer: str) -> str:
    if not USE_OAI or oai is None:
        return ""
    prompt = (
        "Explain the answer in at most 2 concise lines. Plain text only.\n"
        f"Question: {question}\nCorrect answer: {answer}\n"
    )
    try:
        resp = oai.responses.create(model="gpt-4.1-mini", input=prompt)
        return (resp.output_text or "").strip()
    except Exception:
        return ""

def builtin_explanation(q: str, a: str) -> str:
    if q.startswith("[Consulting]"):
        return f"Breakeven = Fixed / (Price − Var). Here: {a} units."
    if q.startswith("[IB]"):
        return f"EPS = Net income / Shares. Here: {a}."
    if q.startswith("[LSAT]"):
        return "This is a hasty generalization from limited observations."
    return f"Answer: {a}"

# ---------------------------
# CLI “transport” (simulate SMS)
# ---------------------------
def send_message(user: User, text: str):
    timestamp = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[to {user.name} @ {timestamp}] {text}")

def receive_message(prompt: str = "> ") -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""

def send_next_question(user: User) -> bool:
    for idx, (q, a) in enumerate(user.queue):
        if user.open_idx is None or idx > user.open_idx:
            user.open_idx = idx
            send_message(user, q + "\nReply with a number or A–E. (HINT for a nudge)")
            return True
    return False

def handle_reply(user: User, text: str):
    if user.open_idx is None:
        send_message(user, "No open question. Type NEXT to get one.")
        return
    q, a = user.queue[user.open_idx]
    status, _ = grade(text, a)
    if status == "hint":
        send_message(user, "Hint: identify the one formula/step needed; keep it to one move.")
        return
    if status == "unknown":
        send_message(user, "Please reply with a number or A–E (or HINT).")
        return

    user.total += 1
    if status == "correct":
        user.correct += 1
        send_message(user, "Correct.")
    else:
        exp = explain_with_oai(q, a) or builtin_explanation(q, a)
        send_message(user, f"Not quite. {exp}")

def summary(user: User):
    rate = "—" if user.total == 0 else f"{(100*user.correct/user.total):.0f}%"
    print(f"\n[{user.name}] Track: {user.track} | Today: {user.correct}/{user.total} correct ({rate})\n")

# ---------------------------
# Main loop
# ---------------------------
def main():
    print("StudyBot CLI — type HELP for commands.")
    users: Dict[str, User] = {
        "andrew": User(name="Andrew", track="consulting", per_day=3),
        "friend": User(name="Friend", track="ib", per_day=3),
    }
    for u in users.values():
        u.seed_today()

    current = users["andrew"]

    help_txt = (
        "Commands:\n"
        "  USER <name>         — switch user (andrew|friend)\n"
        "  TRACK <t>           — set track (consulting|ib|lsat)\n"
        "  NEXT                — send next question to current user\n"
        "  REPLY <text>        — reply to open question (simulated SMS)\n"
        "  STATS               — show accuracy for current user\n"
        "  SEED                — reseed today’s questions for current user\n"
        "  HELP                — show commands\n"
        "  QUIT                — exit\n"
    )
    print(help_txt)

    while True:
        raw = receive_message("cmd> ").strip()
        if not raw:
            continue
        parts = raw.split(maxsplit=1)
        cmd = parts[0].upper()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "QUIT":
            break
        elif cmd == "HELP":
            print(help_txt)
        elif cmd == "USER":
            key = arg.lower()
            if key in users:
                current = users[key]
                print(f"Switched to user: {current.name} (track={current.track})")
            else:
                print(f"Unknown user. Options: {', '.join(users.keys())}")
        elif cmd == "TRACK":
            t = arg.lower()
            if t in GEN_BY_TRACK:
                current.track = t
                print(f"{current.name} track set to {t}.")
            else:
                print("Valid tracks: consulting, ib, lsat")
        elif cmd == "NEXT":
            ok = send_next_question(current)
            if not ok:
                print("No more questions queued. Use SEED to generate new ones.")
        elif cmd == "REPLY":
            if not arg:
                print("Usage: REPLY <your answer or HINT>")
            else:
                handle_reply(current, arg)
        elif cmd == "STATS":
            summary(current)
        elif cmd == "SEED":
            current.seed_today()
            print("New questions seeded for today.")
        else:
            print("Unknown command. Type HELP.")

if __name__ == "__main__":
    main()
