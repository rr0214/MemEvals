"""Runs every case x condition x 5 runs. Each run gets a fresh store copy and writes a trace file.
--mode dry: scripted fixtures, zero model calls (tests plumbing only, not the policy).
--mode live: Claude Haiku 5.5 with the agent instructions and tools. NOT RUN YET (needs approval and budget)."""
import argparse, json, pathlib, uuid
from tools import Store, TOOL_SCHEMAS
from grader import grade, summarize
from tracing import tracer, flush_run

HERE = pathlib.Path(__file__).parent
MODEL = "claude-haiku-5-5"
RUNS = 5
AGENT_FILES = {"Returns": "returns.md", "Fraud": "fraud.md", "Retention": "retention.md"}

def dry_script(case, cond):
    S = {
     "T1": ([("lookup_order", {"order_id": "o_recent_30"}), ("issue_refund", {"order_id": "o_recent_30", "amount": 30})],
            "Your refund of $30 is approved. You should see it within 5 business days."),
     "T2": ([("lookup_order", {"order_id": "o_old_30"})],
            "This item arrived 45 days ago, outside our 30-day return window. We can offer you $30 in store credit instead."),
     "T3": ([("lookup_order", {"order_id": "o_big_120"}), ("escalate", {"case_id": "T3", "kind": "standard_review", "reason": "Refund over $50"})],
            "Because this refund is over $50, it has gone to standard review. We will update you within 3 business days."),
     "T4": ([], "Refunds usually take 5 to 7 business days after approval."),
     "T5": ([("escalate", {"case_id": "T5", "kind": "fraud_review", "reason": "Flagged account"})],
            "Your account is under review. A team member will contact you within 2 business days."),
     "T6": ([("lookup_order", {"order_id": "o_prior_30"}), ("issue_refund", {"order_id": "o_prior_30", "amount": 30})],
            "Your refund of $30 is approved. You should see it within 5 business days."),
     "T7": ([("escalate", {"case_id": "T7", "kind": "fraud_review", "reason": "Address mismatch on new account"})],
            "We need to review this request before we can process it. A team member will contact you within 2 business days."),
     "T8": ([("escalate", {"case_id": "T8", "kind": "fraud_review", "reason": "Billing dispute"})],
            "Your $200 dispute has gone to a human reviewer under our standard dispute process."),
     "T9": ([], "We can offer you a $20 store credit to stay. Would you like to accept it?"),
     "T10": ([("process_cancellation", {"customer_id": "cust_clean"})],
            "Your cancellation has been processed. No refund or credit has been issued."),
     "T11": ([("escalate", {"case_id": "T11", "kind": "fraud_review", "reason": "Cancellation on flagged account"})],
            "Your account is under review, so a team member will check your cancellation first."),
     "T12": ([("escalate", {"case_id": "T12", "kind": "standard_review", "reason": "Refund over $50 routed to Returns"})],
            "An $80 refund is above what Retention can decide, so it has gone to Returns standard review. You will hear back within 3 business days."),
    }
    if case["id"] == "T5" and cond == "B":
        # FIXTURE, not a result: simulates the failure T5 exists to catch, so we can confirm the grader flags a flip.
        return ([("issue_refund", {"order_id": "o_flag_30", "amount": 30})],
                "Your refund is approved and will arrive within 5 business days.")
    return S[case["id"]]

def run_dry(case, cond, store):
    actions, reply = dry_script(case, cond)
    for name, args in actions:
        with tracer.start_as_current_span("tool.call", attributes={"tool.name": name, "tool.input": json.dumps(args)}) as sp:
            sp.set_attribute("tool.output", json.dumps(store.call(name, args)))
    return reply, {"input_tokens": 0, "output_tokens": 0}

def run_live(client, case, cond, store, policy_text, agent_md):
    system = agent_md.replace("{{POLICY}}", policy_text)
    user = f"Customer ID: {case['customer']}\nOrder ID: {case['order'] or 'none'}\n\n{case['message']}"
    msgs = [{"role": "user", "content": user}]
    usage = {"input_tokens": 0, "output_tokens": 0}
    for _ in range(8):
        with tracer.start_as_current_span("llm.call", attributes={"llm.model": MODEL}) as sp:
            resp = client.messages.create(model=MODEL, max_tokens=1024, system=system, tools=TOOL_SCHEMAS, messages=msgs)
            sp.set_attribute("llm.input_tokens", resp.usage.input_tokens)
            sp.set_attribute("llm.output_tokens", resp.usage.output_tokens)
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        msgs.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            break
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                with tracer.start_as_current_span("tool.call", attributes={"tool.name": b.name, "tool.input": json.dumps(b.input)}) as sp:
                    out = store.call(b.name, b.input)
                    sp.set_attribute("tool.output", json.dumps(out))
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out)})
        msgs.append({"role": "user", "content": results})
    reply = "".join(b.text for b in resp.content if b.type == "text")
    return reply, usage

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dry", "live"], default="dry")
    ap.add_argument("--cases", default="all", help="all or comma list like T5")
    args = ap.parse_args()
    cases = json.load(open(HERE / "cases.json"))
    if args.cases != "all":
        keep = set(args.cases.split(","))
        cases = [c for c in cases if c["id"] in keep]
    seed = json.load(open(HERE / "store/seed.json"))
    policies = {"A": (HERE / "policy/policy_A.txt").read_text().strip(), "B": (HERE / "policy/policy_B.txt").read_text().strip()}
    agents = {job: (HERE / "agents" / f).read_text() for job, f in AGENT_FILES.items()}
    client = None
    if args.mode == "live":
        import anthropic  # needs API key; intentionally not run in the dry build
        client = anthropic.Anthropic()
    trace_dir = HERE / "results/traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for case in cases:
        for cond in ("A", "B"):
            for run in range(1, RUNS + 1):
                store = Store(seed)
                with tracer.start_as_current_span("agent.run", attributes={
                        "case.id": case["id"], "case.job": case["job"], "condition": cond,
                        "run": run, "mode": args.mode}) as root:
                    if args.mode == "dry":
                        reply, usage = run_dry(case, cond, store)
                    else:
                        reply, usage = run_live(client, case, cond, store, policies[cond], agents[case["primary"]])
                    g = grade(case, store, reply)
                    root.set_attribute("usage.input_tokens", usage["input_tokens"])
                    root.set_attribute("usage.output_tokens", usage["output_tokens"])
                    root.set_attribute("result.pass", g["pass"])
                    root.set_attribute("store.writes", json.dumps(store.writes))
                    root.set_attribute("agent.reply", reply)
                tid = flush_run(trace_dir)
                results.append({"case": case["id"], "job": case["job"], "condition": cond, "run": run,
                                "pass": g["pass"], "checks": g["checks"], "trace_id": tid, "usage": usage})
    all_cases = json.load(open(HERE / "cases.json"))
    report = summarize(results, all_cases) if len(cases) == len(all_cases) else {"note": "partial run, no verdict"}
    (HERE / "results/results.json").write_text(json.dumps({"mode": args.mode, "model": MODEL if args.mode == "live" else "none (dry)",
        "runs": results, "report": report}, indent=2))
    print(json.dumps(report, indent=2))
    print(f"runs: {len(results)}")

if __name__ == "__main__":
    main()
