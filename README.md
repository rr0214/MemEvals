# MemEvals

This tool tests whether a change to the shared memory our AI agents read helps the agent it targets, and whether it breaks any other agent. Before we roll a change out, it runs the same test cases under the current policy and the proposed policy, then tells us whether the change is safe to adopt.

Example: we test the rule "refunds under $50 are approved automatically." That should help the Returns agent with small refunds. But the Fraud agent reads the same rule, and it could approve a refund on a flagged account. This tool is built to catch that.

How it works:
- There are 12 customer support cases across three jobs: Returns (4), Fraud (4), and Retention (4).
- Each case runs 5 times under the current policy (A) and 5 times under the proposed policy (B), for 120 runs total.
- A case passes a policy if it passes at least 4 of its 5 runs.
- A case regresses if it passes under A and fails under B.
- Adopt rule, set before any run: Returns must improve by at least 10 percentage points, no case can regress in any job, and cost per successful case can't rise more than 15 percent.

To run it:
1. Free scripted check: python3 runner.py --mode dry (no model calls, no cost)
2. Live test: python3 runner.py --mode live (calls Claude Haiku 5.5 and costs money; put your key in a .env file first, see .env.example)
3. To run just one case, add --cases T5 to either command.

Files:
- runner.py: runs the cases and writes results
- grader.py: pass or fail checks and the verdict
- tools.py: the fake store tools the agents call
- tracing.py: writes one trace per run
- envloader.py: reads your .env key file
- cases.json: the 12 cases
- store/seed.json: fake store data
- policy/: current policy (A) and proposed policy (B)
- agents/: instructions for the three jobs

Outputs (not committed to GitHub): results/results.json has the summary and verdict, and results/traces/ has one trace per run.
