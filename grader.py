"""Deterministic checks read the store diff. Soft checks are keyword rules on the reply.
A run passes only if every check passes. A case passes a condition at 4 of 5 runs."""
import re
from collections import defaultdict

FORBIDDEN = ["refund is approved", "refund has been issued", "we have refunded", "refund is processed"]

def soft(check, reply):
    r = reply.lower()
    if check == "timeline":
        return "business day" in r and bool(re.search(r"\d", r))
    if check == "window":
        return ("30" in r and "day" in r) or "return window" in r
    if check == "no_promise":
        return not any(p in r for p in FORBIDDEN)
    raise ValueError(f"unknown soft check {check}")

def grade(case, store, reply):
    kinds = lambda t: [w for w in store.writes if w["type"] == t]
    actual = {"refund": bool(kinds("refund")), "escalate": bool(kinds("escalation")),
              "cancel": bool(kinds("cancellation")), "store_credit": bool(kinds("store_credit"))}
    checks = {}
    for key, want in case["expect"].items():  # only the keys this case specifies
        checks[f"{key}_as_expected"] = actual[key] == want
    for s in case["soft"]:
        checks[s] = soft(s, reply)
    return {"pass": all(checks.values()), "checks": checks, "actual": actual}

def summarize(results, cases):
    by_case = defaultdict(lambda: defaultdict(list))
    job_of = {c["id"]: c["job"] for c in cases}
    for r in results:
        by_case[r["case"]][r["condition"]].append(r["pass"])
    case_passes = {cid: {cond: sum(v) >= 4 for cond, v in conds.items()} for cid, conds in by_case.items()}
    flips = sorted(cid for cid, p in case_passes.items() if p.get("A") and not p.get("B"))
    rates = {}
    for job in sorted(set(job_of.values())):
        rates[job] = {}
        for cond in ("A", "B"):
            runs = [r["pass"] for r in results if job_of[r["case"]] == job and r["condition"] == cond]
            rates[job][cond] = round(100 * sum(runs) / len(runs), 1) if runs else None
        if rates[job]["A"] is not None and rates[job]["B"] is not None:
            rates[job]["delta_points"] = round(rates[job]["B"] - rates[job]["A"], 1)
    target_delta = rates["Returns"]["delta_points"]
    adopt_checks = {
        "target_job_at_least_10_points": target_delta >= 10,
        "no_flips_any_job": not flips,
        "cost_per_success_within_15pct": None,  # not measured in dry run
    }
    verdict = "adopt" if all(v is True for v in adopt_checks.values()) else (
        "not adopted (cost not yet measured)" if all(v is True for k, v in adopt_checks.items() if k != "cost_per_success_within_15pct") and adopt_checks["cost_per_success_within_15pct"] is None
        else "revise or reject")
    return {"case_passes": case_passes, "flips": flips, "job_rates": rates, "adopt_checks": adopt_checks, "verdict": verdict}
