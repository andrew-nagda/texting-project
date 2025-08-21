# tracks.py
import re, math, random

# ---------- helpers ----------
def parse_number(ans: str) -> float:
    """
    Turn inputs like '1,200', '1.2k', '12%' into floats.
    - 'k' -> *1000
    - '%' -> /100
    """
    s = (ans or "").strip().lower().replace(",", "")
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
        mult = 0.01
    if s.endswith("k"):
        s = s[:-1]
        mult *= 1000
    try:
        return float(s) * mult
    except Exception:
        m = re.findall(r"-?\d+(?:\.\d+)?", s)
        if not m:
            raise ValueError("no number found")
        return float(m[0]) * mult


# ---------- knowledge questions (expanded) ----------
QUESTIONS = {
    "Consulting": [
        {
            "id": "cons_profit_1",
            "q": "A client’s profits are down despite flat revenue. Which analysis should you run first?",
            "choices": [
                "Market sizing",
                "PESTLE analysis",
                "Price elasticity",
                "Cost structure (variable vs fixed)"
            ],
            "answer": "Cost structure (variable vs fixed)",
            "rationale": "If revenue is flat but profit falls, costs likely changed. Break down fixed vs variable costs, then drill into drivers.",
            "tip": "Rehearse a profitability tree: Revenue → Price × Volume; Costs → Fixed vs Variable; then list 2–3 hypotheses per branch."
        },
        {
            "id": "cons_market_1",
            "q": "Your client is entering a new market. What is the FIRST high-level question?",
            "choices": [
                "What is the regulatory barrier?",
                "What is the market size and growth?",
                "What is the product roadmap?",
                "What are the distribution partners?"
            ],
            "answer": "What is the market size and growth?",
            "rationale": "Market attractiveness (size & growth) is the gate before execution details.",
            "tip": "Estimate TAM/SAM/SOM with one quick bottom-up and one top-down triangulation."
        },
        {
            "id": "cons_price_1",
            "q": "If contribution margin is low, which lever MOST directly improves it?",
            "choices": ["Increase fixed costs", "Increase price", "Reduce overhead allocation", "Increase capex"],
            "answer": "Increase price",
            "rationale": "Contribution margin = Price − Variable cost; changing price or variable cost affects it directly.",
            "tip": "List price and variable cost levers; quantify CM uplift per lever to prioritize."
        },
        {
            "id": "cons_seg_1",
            "q": "Your client’s conversion rate is falling overall, but Segment A improved. What’s the most likely phenomenon?",
            "choices": ["Price elasticity dropped", "Ad creative worsened", "Mix shift toward weaker segments", "Cohort retention improved"],
            "answer": "Mix shift toward weaker segments",
            "rationale": "Aggregate decline with segment improvement often implies a mix shift toward worse-performing segments.",
            "tip": "Do a mix decomposition: ∑(segment share × segment conversion)."
        },
        {
            "id": "cons_ops_1",
            "q": "Lead times are up while capacity is unchanged. Which is the BEST initial diagnostic?",
            "choices": ["Value stream mapping", "PESTLE analysis", "Blue Ocean strategy", "VRIO analysis"],
            "answer": "Value stream mapping",
            "rationale": "Operational delay → map process steps, inventories, and bottlenecks to locate waste.",
            "tip": "Time each step, quantify WIP and rework, then test bottleneck relief scenarios."
        },
        {
            "id": "cons_case_math_1",
            "q": "A product sells for $100 with variable cost $60. Fixed costs are $2M. What volume to break even?",
            "choices": ["33,333", "40,000", "50,000", "20,000"],
            "answer": "50,000",
            "rationale": "Breakeven units = Fixed / (Price − Var) = 2,000,000 / 40 = 50,000.",
            "tip": "Remember: Units*CM = Fixed + Profit Target."
        },
        {
            "id": "cons_case_math_2",
            "q": "A growth project requires $3M fixed cost, CM per unit $25, target profit $1M. Units to target?",
            "choices": ["80,000", "120,000", "160,000", "200,000"],
            "answer": "160,000",
            "rationale": "Units = (Fixed + Target)/CM = (3M+1M)/25 = 160k.",
            "tip": "Convert to round numbers; solve in thousands to speed up."
        },
    ],

    "Investment Banking": [
        {
            "id": "ib_ev_1",
            "q": "Which metric best normalizes capital structure across comparable companies?",
            "choices": ["P/E", "EV/EBITDA", "Price/Sales", "Price/Book"],
            "answer": "EV/EBITDA",
            "rationale": "EV reflects debt and cash; EBITDA approximates core operating profit.",
            "tip": "Practice converting Market Cap → EV: add net debt & minorities; subtract cash."
        },
        {
            "id": "ib_dcf_1",
            "q": "In a DCF, which change most directly reduces the present value?",
            "choices": ["Lower terminal growth", "Higher working capital", "Higher discount rate (WACC)", "Lower CapEx"],
            "answer": "Higher discount rate (WACC)",
            "rationale": "Higher WACC reduces PV of all cash flows.",
            "tip": "Run a sensitivity table: PV vs WACC and terminal growth."
        },
        {
            "id": "ib_leverage_1",
            "q": "Which statement about leverage is MOST accurate?",
            "choices": [
                "Higher debt always lowers WACC",
                "Higher debt increases equity risk and can raise WACC beyond a point",
                "Higher debt does not affect beta",
                "Higher debt lowers equity cost"
            ],
            "answer": "Higher debt increases equity risk and can raise WACC beyond a point",
            "rationale": "Tax shields can lower WACC at first, but financial distress risk eventually raises it.",
            "tip": "Know the U-shaped WACC intuition vs leverage."
        },
        {
            "id": "ib_acc_1",
            "q": "Which item INCREASES Enterprise Value when calculating from equity value?",
            "choices": ["Cash", "Minority interest", "Preferred dividends", "Treasury stock"],
            "answer": "Minority interest",
            "rationale": "EV = Equity Value + Net Debt + Preferred + Minority Interest − Cash.",
            "tip": "Memorize the EV bridge and why each component is included/excluded."
        },
        {
            "id": "ib_merger_1",
            "q": "A stock-for-stock deal shows combined EPS rising, but operating income is unchanged. This is most likely:",
            "choices": ["True accretion from synergies", "Accretion from accounting/denominator effects", "No accretion", "Cash tax benefit"],
            "answer": "Accretion from accounting/denominator effects",
            "rationale": "EPS accretion without operating improvement is often mix/denominator, not true value creation.",
            "tip": "Check pro forma share count, purchase accounting, and cost of financing vs target yield."
        },
        {
            "id": "ib_workingcap_1",
            "q": "All else equal, an increase in NWC today does what to FCF in a DCF?",
            "choices": ["Increases FCF", "Decreases FCF", "No change", "Only impacts terminal value"],
            "answer": "Decreases FCF",
            "rationale": "ΔNWC is a cash outflow in the period it rises.",
            "tip": "Remember: FCF to firm often uses −ΔNWC in the formula."
        },
    ],

    "High Finance": [
        {
            "id": "hf_risk_1",
            "q": "Which best hedges a USD receivable due in 6 months?",
            "choices": ["USD put option", "USD call option", "Short USD forward", "Long USD forward"],
            "answer": "Short USD forward",
            "rationale": "Lock in selling price for future USD; short forward hedges a receivable.",
            "tip": "Match direction: receivable → short, payable → long (in the currency)."
        },
        {
            "id": "hf_bonds_1",
            "q": "When yields rise, bond prices generally:",
            "choices": ["Rise", "Fall", "Remain constant", "Become more volatile only for short duration"],
            "answer": "Fall",
            "rationale": "Inverse price–yield relationship.",
            "tip": "Longer duration → more sensitivity."
        },
        {
            "id": "hf_duration_1",
            "q": "Which portfolio change MOST reduces interest rate sensitivity?",
            "choices": ["Increase duration", "Decrease duration", "Increase convexity", "Increase coupon"],
            "answer": "Decrease duration",
            "rationale": "Lower duration lowers price sensitivity to yield changes.",
            "tip": "Compare Macaulay/modified duration, know the convexity effect directionally."
        },
        {
            "id": "hf_options_1",
            "q": "All else equal, which increases a call option’s value?",
            "choices": ["Lower volatility", "Lower interest rates", "Higher underlying price", "Higher dividend yield"],
            "answer": "Higher underlying price",
            "rationale": "Calls gain as the underlying rises (and with higher vol).",
            "tip": "Greeks intuition: Delta ≈ +, Vega ≈ +, Theta ≈ −, Rho ≈ + for calls."
        },
        {
            "id": "hf_fx_1",
            "q": "Company owes €5M in 90 days. Best plain-vanilla hedge?",
            "choices": ["Long EUR forward", "Short EUR forward", "Buy EUR call", "Sell EUR put"],
            "answer": "Long EUR forward",
            "rationale": "You need to buy EUR later → go long EUR forward to lock rate.",
            "tip": "Receivable vs payable; which side of the forward locks the needed exposure?"
        },
    ],

    "GMAT": [
        {
            "id": "gmat_cr_1",
            "q": "Critical Reasoning: The argument concludes that raising bus fares will increase revenue. What’s a common flaw?",
            "choices": ["Causal confusion", "Sampling bias", "Ignored price sensitivity (elasticity)", "Equivocation"],
            "answer": "Ignored price sensitivity (elasticity)",
            "rationale": "Higher prices can reduce ridership; revenue may fall if demand is elastic.",
            "tip": "List missing assumptions about demand, substitutes, and segments."
        },
        {
            "id": "gmat_ps_1",
            "q": "If x is even and y is odd, which must be odd?",
            "choices": ["x+y", "x−y", "xy", "x/2"],
            "answer": "x+y",
            "rationale": "Even + Odd = Odd; other expressions may be even.",
            "tip": "Memorize parity rules and test with x=2, y=1."
        },
    ],

    "GRE": [
        {
            "id": "gre_quant_1",
            "q": "Which is prime?",
            "choices": ["21", "29", "39", "51"],
            "answer": "29",
            "rationale": "29 is prime; others are divisible by 3 or other factors.",
            "tip": "Memorize primes under 60; use quick divisibility rules."
        },
        {
            "id": "gre_verbal_1",
            "q": "Choose the best pair of synonyms:",
            "choices": ["Loquacious – Taciturn", "Soporific – Sleep-inducing", "Cacophonous – Harmonious", "Mundane – Extraordinary"],
            "answer": "Soporific – Sleep-inducing",
            "rationale": "Only that pair matches in meaning.",
            "tip": "Eliminate antonyms; look for precise, not approximate matches."
        },
    ],

    "SAT": [
        {
            "id": "sat_math_1",
            "q": "What is the slope of the line through (2,3) and (6,11)?",
            "choices": ["1", "2", "3", "4"],
            "answer": "2",
            "rationale": "Slope = (11-3)/(6-2) = 8/4 = 2.",
            "tip": "Practice slope, midpoint, and distance formula; watch signs carefully."
        },
        {
            "id": "sat_ebrw_1",
            "q": "Choose the most concise correction: “Due to the fact that prices rose, consumers subsequently bought less.”",
            "choices": [
                "Because prices rose, consumers bought less.",
                "Since prices rose, consumers consequently bought less.",
                "Due to prices rising, consumers bought less.",
                "Consumers bought less, due to prices rising."
            ],
            "answer": "Because prices rose, consumers bought less.",
            "rationale": "Concise and direct; avoids redundancy.",
            "tip": "Prefer active, concise phrasing; remove filler words."
        },
    ],

    "ACT": [
        {
            "id": "act_english_1",
            "q": "Choose the best revision: “Running late the bus was missed by us.”",
            "choices": [
                "Running late, we missed the bus.",
                "Because we were running late, the bus was missed.",
                "We missed the bus running late.",
                "Running late, the bus was missed."
            ],
            "answer": "Running late, we missed the bus.",
            "rationale": "Intro participial phrase must modify the subject that follows; avoid passive voice/dangling modifiers.",
            "tip": "Scan for dangling modifiers and passive voice; prefer concise, active constructions."
        },
        {
            "id": "act_math_1",
            "q": "If f(x)=2x^2−3x+1, what is f(3)?",
            "choices": ["10", "11", "12", "13"],
            "answer": "10",
            "rationale": "f(3)=2*9 − 9 + 1 = 18 − 9 + 1 = 10.",
            "tip": "Plug carefully; check order of operations."
        },
    ],

    "LSAT": [
        {
            "id": "lsat_lr_1",
            "q": "A conclusion is likely flawed if it generalizes from a small survey to a population. This flaw is:",
            "choices": ["Ad hominem", "Circular reasoning", "Sampling bias", "Mistaken cause and effect"],
            "answer": "Sampling bias",
            "rationale": "Small or non-representative sample cannot justify population-level conclusions.",
            "tip": "Spot leaps from limited evidence to broad claims; ask about representativeness."
        },
        {
            "id": "lsat_lr_2",
            "q": "Which answer choice would MOST strengthen a causal claim?",
            "choices": [
                "Show correlation between the variables",
                "Rule out plausible alternative causes",
                "Show the effect occurs without the cause",
                "Show a small sample replicated the effect once"
            ],
            "answer": "Rule out plausible alternative causes",
            "rationale": "Causal strengthening often requires eliminating alternative explanations.",
            "tip": "For cause ↔ effect, check temporality, mechanism, and confounders."
        },
        {
            "id": "lsat_lr_3",
            "q": "An argument that assumes what it tries to prove commits which flaw?",
            "choices": ["Equivocation", "Begging the question", "Ad hominem", "Straw man"],
            "answer": "Begging the question",
            "rationale": "Circular reasoning assumes the conclusion in the premises.",
            "tip": "Ask: would the premise be true only if the conclusion were already true?"
        },
        {
            "id": "lsat_lr_4",
            "q": "A conditional claim 'If A then B' is logically equivalent to:",
            "choices": ["If not B then not A", "If B then A", "A only if B means if B then A", "A and B are mutually exclusive"],
            "answer": "If not B then not A",
            "rationale": "Contrapositive preserves logical truth.",
            "tip": "Memorize: A→B ≡ ¬B→¬A; 'only if' points to the necessary condition."
        },
        {
            "id": "lsat_lr_5",
            "q": "Which most weakens: 'Policy X will reduce traffic because it reduces car ownership'?",
            "choices": [
                "Public transit capacity is already constrained",
                "Most commuters lease rather than own cars",
                "Car ownership fell in cities with Policy X, but ride-hailing miles increased",
                "Traffic worsened during a storm last year"
            ],
            "answer": "Car ownership fell in cities with Policy X, but ride-hailing miles increased",
            "rationale": "Introduces a substitute mode that offsets the predicted effect.",
            "tip": "Weakeners often add a counter-mechanism or missing factor."
        },
        {
            "id": "lsat_lg_1",
            "q": "Logic Games: If slots 1–3 must contain exactly two of A,B,C (no repeats), which inference is strongest?",
            "choices": [
                "At least one of A,B,C is not used in 1–3",
                "Exactly one of A,B,C appears in 1–3",
                "All of A,B,C appear in 1–3",
                "None of A,B,C appears in 1–3"
            ],
            "answer": "At least one of A,B,C is not used in 1–3",
            "rationale": "Two items across three slots implies at least one of A,B,C is excluded.",
            "tip": "Translate constraints into counts/sets first; draw a simple board."
        },
        {
            "id": "lsat_rc_1",
            "q": "Reading Comp: Which choice states the main point of a passage most directly?",
            "choices": [
                "A detail from the second paragraph",
                "A counterexample briefly mentioned",
                "A paraphrase of the author’s overall conclusion",
                "A quote of a dissenting view"
            ],
            "answer": "A paraphrase of the author’s overall conclusion",
            "rationale": "Main point summarizes the author’s primary conclusion or thesis, not a detail or opposing view.",
            "tip": "Underline thesis statements and repeated claims; avoid answer choices that are 'too narrow'."
        },
    ],

    "CPA": [
        {
            "id": "cpa_gaap_1",
            "q": "Under GAAP, which method is acceptable for inventory cost flow?",
            "choices": ["FIFO", "Weighted Average", "LIFO", "All of the above"],
            "answer": "All of the above",
            "rationale": "GAAP allows FIFO, Weighted Average, and LIFO (IFRS disallows LIFO).",
            "tip": "Memorize GAAP vs IFRS hotspots: LIFO, revaluation, development cost capitalization."
        }
    ],

    "CMA": [
        {
            "id": "cma_cv_1",
            "q": "Which cost is not part of conversion cost?",
            "choices": ["Direct labor", "Manufacturing overhead", "Direct materials", "Indirect labor"],
            "answer": "Direct materials",
            "rationale": "Conversion cost = Direct labor + Manufacturing overhead.",
            "tip": "Prime cost = DM + DL; Conversion cost = DL + OH."
        }
    ],

    "CFA Level I": [
        {
            "id": "cfa1_time_1",
            "q": "At 8% effective annual, what’s the future value of $100 in 3 years?",
            "choices": ["$125.97", "$126.00", "$117.00", "$120.00"],
            "answer": "$125.97",
            "rationale": "FV = 100*(1.08)^3 = 125.97.",
            "tip": "Know compounding vs simple, nominal vs effective."
        }
    ],

    "CFA Level II": [
        {
            "id": "cfa2_fcff_1",
            "q": "Which is the correct formula for FCFF?",
            "choices": [
                "NI + NCC + Int*(1–t) – FCInv – WCInv",
                "NI + NCC – FCInv – WCInv",
                "CFO – FCInv",
                "EBITDA – FCInv"
            ],
            "answer": "NI + NCC + Int*(1–t) – FCInv – WCInv",
            "rationale": "One valid FCFF approach starts from NI, adds non-cash charges and after-tax interest, subtracts fixed and working capital investment.",
            "tip": "Memorize FCFF/FCFE variants and when to use each."
        }
    ],

    "CFA Level III": [
        {
            "id": "cfa3_ips_1",
            "q": "In IPS, “ability to take risk” is LEAST impacted by which?",
            "choices": ["Time horizon", "Liquidity needs", "Risk aversion", "Income stability"],
            "answer": "Risk aversion",
            "rationale": "Risk aversion is willingness, not ability.",
            "tip": "Final risk tolerance follows the lower of willingness vs ability."
        }
    ],
}


def pick_sample_question(track: str):
    qs = QUESTIONS.get(track)
    return qs[0] if qs else None


def grade_answer(track: str, qid: str, answer: str):
    qs = QUESTIONS.get(track) or []
    for q in qs:
        if q["id"] == qid:
            user_raw = (answer or "").strip()
            user_up  = user_raw.upper()

            # Allow A–E or 1–5
            choices = q.get("choices") or []
            letter_map = {chr(65 + i): c for i, c in enumerate(choices)}  # A,B,C,D,E...
            if user_up in letter_map:
                user_choice = letter_map[user_up]
            elif user_up.isdigit() and 1 <= int(user_up) <= len(choices):
                user_choice = choices[int(user_up) - 1]
            else:
                # Fall back to matching full text, case-insensitive
                user_choice = next(
                    (c for c in choices if c.strip().upper() == user_up),
                    user_raw,
                )

            correct_text = q["answer"]
            correct = correct_text.strip().upper() == str(user_choice).strip().upper()

            # Compute the correct letter if we have choices
            try:
                idx = choices.index(correct_text)
                correct_letter = "ABCDE"[idx]
            except Exception:
                correct_letter = None

            return {
                "correct": correct,
                "correct_answer": correct_text,
                "correct_letter": correct_letter,
                "rationale": q.get("rationale"),
                "tip": q.get("tip"),
            }
    return {"error": "Question not found"}



# ---------- mental math generators (expanded consulting context) ----------
def gen_general_math():
    # subtraction / percent-of / quick division to integer
    r = random.random()
    if r < 0.4:
        a = random.randint(120, 999)
        b = random.randint(20, 119)
        if b > a: a, b = b, a
        expected = a - b
        q = f"{a} - {b} = ?"
        qid = f"mm_gen_sub:{a}:{b}:{expected}"
        return {"qid": qid, "question": q, "expected": expected, "tolerance": 0.0, "units": None}
    elif r < 0.8:
        p = random.choice([4,5,6,7,8,9,10,12,15,20,25])
        n = random.randint(30, 499)
        expected = round(n * p / 100.0, 2)
        q = f"{p}% of {n} = ?"
        qid = f"mm_gen_pct:{p}:{n}:{expected}"
        return {"qid": qid, "question": q, "expected": expected, "tolerance": max(0.5, 0.02*abs(expected)), "units": None}
    else:
        # simple division rounding
        num = random.randint(4_000, 90_000)
        den = random.choice([12, 24, 36, 48, 60])
        expected = round(num/den, 2)
        q = f"{num} ÷ {den} = ?"
        qid = f"mm_gen_div:{num}:{den}:{expected}"
        return {"qid": qid, "question": q, "expected": expected, "tolerance": 0.02*abs(expected), "units": None}


def _vtarget_units(price, var, fixed, target):
    cm = price - var
    return math.ceil((fixed + target) / cm)

def _breakeven_units(price, var, fixed):
    cm = price - var
    return math.ceil(fixed / cm)

def _margin_pct(price, var):
    return (price - var) / price * 100.0

def gen_consulting_context():
    # choose among (a) target units, (b) breakeven units, (c) margin %, (d) price needed to hit margin
    choice = random.random()
    if choice < 0.45:
        # target profit units (physical)
        price = random.choice([120, 200, 250, 300, 350])
        var = random.choice([40, 60, 80, 100, 120, 180])
        fixed = random.choice([600_000, 800_000, 1_200_000, 1_500_000])
        target = random.choice([300_000, 600_000, 900_000])
        units = _vtarget_units(price, var, fixed, target)
        q = (f"A product sells for ${price}. Variable cost is ${var}. Fixed costs are ${fixed:,}/yr. "
             f"What sales volume is needed to earn ${target:,} annual profit?")
        qid = f"mm_cons_vtarget:{price}:{var}:{fixed}:{target}:{units}"
        return {"qid": qid, "question": q, "expected": units, "tolerance": 0.5, "units": "units"}
    elif choice < 0.75:
        # breakeven units (SaaS style)
        price = random.choice([60, 96, 120, 180])
        var = random.choice([10, 12, 20, 30])
        fixed = random.choice([240_000, 360_000, 480_000, 600_000])
        units = _breakeven_units(price, var, fixed)
        q = (f"A SaaS company charges ${price}/user/year. Variable cost per user is ${var}/year. "
             f"Fixed costs are ${fixed:,}/year. How many users are needed to break even?")
        qid = f"mm_cons_breakeven:{price}:{var}:{fixed}:{units}"
        return {"qid": qid, "question": q, "expected": units, "tolerance": 0.5, "units": "users"}
    elif choice < 0.9:
        # margin percent
        price = random.choice([50, 80, 100, 120, 200, 250, 300])
        var = random.choice([10, 20, 30, 40, 60, 90, 120])
        margin = round(_margin_pct(price, var), 1)
        q = (f"Price is ${price}, variable cost ${var}. What is the contribution margin percent?")
        qid = f"mm_cons_marginpct:{price}:{var}:{margin}"
        return {"qid": qid, "question": q, "expected": margin, "tolerance": 0.5, "units": "%"}
    else:
        # price needed to hit target margin %
        var = random.choice([20, 40, 60, 90, 120])
        target_margin = random.choice([30, 40, 50, 60])  # as %
        # target_margin% = (P - var)/P → P = var / (1 - m)
        P = var / (1 - target_margin/100.0)
        price_needed = round(P, 2)
        q = (f"Variable cost is ${var}. What price achieves a {target_margin}% contribution margin?")
        qid = f"mm_cons_pricemargin:{var}:{target_margin}:{price_needed}"
        return {"qid": qid, "question": q, "expected": price_needed, "tolerance": max(0.01*price_needed, 0.5), "units": "$"}


def gen_ib_math():
    # IRR/CAGR: initial -> final over years
    initial = random.choice([20_000, 50_000, 75_000, 100_000])
    multiple = random.choice([1.8, 2.0, 2.5, 3.0, 4.0])
    years = random.choice([3,4,5,6,7])
    final = int(initial * multiple)
    irr = (final / initial) ** (1.0 / years) - 1.0
    irr_pct = irr * 100.0
    q = (f"What is the approximate annualized return (IRR) if an investment grows from "
         f"${initial:,} to ${final:,} over {years} years? (Answer in %)")
    tol = 0.5  # percentage points
    qid = f"mm_ib_irr:{initial}:{final}:{years}:{irr_pct:.4f}:{tol}"
    return {"qid": qid, "question": q, "expected": irr_pct, "tolerance": tol, "units": "%"}


def make_math_question(track: str):
    if track == "General":
        return gen_general_math()
    if track == "Consulting":
        return gen_consulting_context()
    if track == "Investment Banking":
        return gen_ib_math()
    return None


def grade_math_q(track: str, qid: str, answer_raw: str):
    """
    Recompute expected from qid and compare with tolerant grading.
    qid formats:
      - mm_gen_sub:a:b:expected
      - mm_gen_pct:p:n:expected
      - mm_gen_div:num:den:expected
      - mm_cons_vtarget:price:var:fixed:target:units
      - mm_cons_breakeven:price:var:fixed:units
      - mm_cons_marginpct:price:var:margin%
      - mm_cons_pricemargin:var:targetMargin:priceNeeded
      - mm_ib_irr:initial:final:years:irrPct:tol
    """
    try:
        ans = parse_number(answer_raw)
    except Exception:
        return {"error": "Could not parse numeric answer."}

    parts = qid.split(":")
    kind = parts[0]

    def ok(delta_abs, tolerance):
        return delta_abs <= tolerance

    if kind == "mm_gen_sub":
        expected = float(parts[3])
        return {"correct": ok(abs(ans - expected), 0.0), "expected": expected, "units": None,
                "rationale": "Arithmetic subtraction"}

    if kind == "mm_gen_pct":
        expected = float(parts[3])
        tol = max(0.5, abs(expected) * 0.02)
        return {"correct": ok(abs(ans - expected), tol), "expected": expected, "units": None,
                "rationale": "Percent-of calculation"}

    if kind == "mm_gen_div":
        expected = float(parts[3])
        tol = max(0.02 * abs(expected), 0.25)
        return {"correct": ok(abs(ans - expected), tol), "expected": expected, "units": None,
                "rationale": "Division / rate calculation"}

    if kind == "mm_cons_vtarget":
        price, var, fixed, target, units = map(float, parts[1:6])
        expected = units
        return {"correct": ok(abs(ans - expected), 0.5), "expected": expected, "units": "units",
                "rationale": f"(Fixed+Target)/CM = ({int(fixed)}+{int(target)})/({int(price)}-{int(var)})"}

    if kind == "mm_cons_breakeven":
        price, var, fixed, units = map(float, parts[1:5])
        expected = units
        return {"correct": ok(abs(ans - expected), 0.5), "expected": expected, "units": "users",
                "rationale": f"Breakeven units = Fixed / (Price - Var) = {int(fixed)}/({int(price)}-{int(var)})"}

    if kind == "mm_cons_marginpct":
        price, var, margin = float(parts[1]), float(parts[2]), float(parts[3])
        expected = margin
        tol = 0.5  # percentage points
        # interpret e.g. 40, 40%, 0.40 → 40%
        user_pct_pts = ans * (100 if abs(ans) <= 1.5 else 1)
        return {"correct": ok(abs(user_pct_pts - expected), tol),
                "expected": expected, "units": "%", "rationale": "CM% = (P−V)/P × 100"}

    if kind == "mm_cons_pricemargin":
        var, target_margin, price_needed = float(parts[1]), float(parts[2]), float(parts[3])
        expected = price_needed
        tol = max(0.01 * expected, 0.5)
        return {"correct": ok(abs(ans - expected), tol), "expected": expected, "units": "$",
                "rationale": "Solve P from margin% = (P−V)/P → P = V / (1 − m)"}

    if kind == "mm_ib_irr":
        expected = float(parts[4])
        tol = float(parts[5])
        # interpret 26, 26%, 0.26 → 26%
        user_pct_pts = ans * (100 if abs(ans) < 1.5 else 1)
        return {"correct": ok(abs(user_pct_pts - expected), tol),
                "expected": round(expected, 2), "units": "%",
                "rationale": "IRR ≈ (Final/Initial)^(1/Years) − 1, expressed as %"}

    return {"error": "Unknown question id"}
