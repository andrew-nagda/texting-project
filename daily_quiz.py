import random, math, datetime, time

USERS = [
    {"name": "Andrew", "phone": "+15084982017", "track": "Arithmetic", "per_day": 1},
]

def gen_arithmetic():
    a = random.randint(200, 999)
    b = random.randint(10, 99)
    if b > a:
        a, b = b + 300, a
    return f"{a} - {b}", a - b, {"a": a, "b": b}

def gen_consulting():
    price = random.randint(12, 28)
    var = random.randint(3, max(4, int(price * 0.7)))
    if var >= price:
        var = max(1, price - 1)
    fixed = random.choice([3000, 4000, 5000, 6000, 8000])
    be = math.ceil(fixed / (price - var))
    return f"Breakeven units? Price ${price}, Variable ${var}, Fixed ${fixed}", be, {
        "price": price, "var": var, "fixed": fixed
    }

def hint_arithmetic(ctx):
    a, b = ctx["a"], ctx["b"]
    tens = (b // 10) * 10
    ones = b % 10
    step1 = a - tens
    step2 = step1 - ones
    return f"Try splitting {b} into {tens} and {ones}: {a} - {tens} = {step1}, then {step1} - {ones} = {step2}."

def hint_consulting(ctx):
    p, v, f = ctx["price"], ctx["var"], ctx["fixed"]
    margin = p - v
    return f"Use breakeven = Fixed / (Price - Variable). Here: {f} / ({p} - {v}) = {math.ceil(f/margin)}."

ANOTHER_WORDS = ("another", "again", "next", "one more", "let's try another", "lets try another")
def wants_another(text): return any(phrase in text.strip().lower() for phrase in ANOTHER_WORDS)
def is_done(text): return text.strip().lower() in ("done", "quit", "q", "exit", "stop")

def ask_and_grade(user):
    track = user["track"].lower()
    if track == "arithmetic":
        q, ans, ctx = gen_arithmetic()
        print(f"\n[to {user['name']}] {q}")
        while True:
            reply = input("Your answer (or 'another'/'done'): ")
            if is_done(reply): return "done"
            if wants_another(reply): return "another"
            if reply.replace('-', '').isdigit():
                if int(reply) == ans:
                    print("Correct.")
                else:
                    print(f"Incorrect. {hint_arithmetic(ctx)}")
                return "answered"
    elif track == "consulting":
        q, ans, ctx = gen_consulting()
        print(f"\n[to {user['name']}] {q}")
        while True:
            reply = input("Your answer (or 'another'/'done'): ")
            if is_done(reply): return "done"
            if wants_another(reply): return "another"
            if reply.isdigit():
                if int(reply) == ans:
                    print("Correct.")
                else:
                    print(f"Incorrect. {hint_consulting(ctx)}")
                return "answered"
    else:
        print(f"Unknown track '{user['track']}'.")
        return "done"

def session_for_user(user):
    # Random send time between 9:00 and 22:00 (10 PM)
    hour = random.randint(9, 21)
    minute = random.randint(0, 59)
    send_time = datetime.time(hour, minute)
    print(f"Scheduled send time for {user['name']}: {send_time.strftime('%I:%M %p')}")
    # Simulate waiting until that time (remove in production)
    # For real SMS, you’d use a scheduler like cron or APScheduler
    # Here we just ask immediately for demo
    while True:
        status = ask_and_grade(user)
        if status in ("done", "answered") and not wants_another(status):
            break

def main():
    print("Daily Quiz (9 AM–10 PM window demo)")
    for u in USERS:
        session_for_user(u)

if __name__ == "__main__":
    main()
