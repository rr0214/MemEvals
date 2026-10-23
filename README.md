# MemEvals


Tests whether a change to shared agent memory (policy text) helps the target agent and breaks any other agent.

Run the free scripted check first: python3 runner.py --mode dry
The live run (--mode live) calls the Claude API and costs money. Set ANTHROPIC_API_KEY in your environment first. Do not commit keys.

Files: runner.py (runs cases), grader.py (pass/fail checks and verdict), tools.py (fake store tools), tracing.py (OpenTelemetry traces), cases.json (12 cases), store/seed.json (fake store), policy/ (current and proposed policy), agents/ (job instructions).

Output goes to results/ (not committed).
