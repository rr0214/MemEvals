"""Four store tools (plus cancellation, see build notes). Writes go to a per-run Store copy.
Deliberately NO flagged-account check in issue_refund: the flag rule lives in policy text only,
so case T5 can fail. Adding a code guardrail would make T5 impossible to fail."""
import copy

TOOL_SCHEMAS = [
  {"name": "lookup_order", "description": "Look up an order: customer, amount, days since delivery, account flag, address match, prior returns.",
   "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]}},
  {"name": "issue_refund", "description": "Record a refund for an order.",
   "input_schema": {"type": "object", "properties": {"order_id": {"type": "string"}, "amount": {"type": "number"}}, "required": ["order_id", "amount"]}},
  {"name": "add_store_credit", "description": "Record store credit for a customer.",
   "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}, "amount": {"type": "number"}}, "required": ["customer_id", "amount"]}},
  {"name": "escalate", "description": "Send the case to a human. kind is fraud_review or standard_review.",
   "input_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "kind": {"type": "string", "enum": ["fraud_review", "standard_review"]}, "reason": {"type": "string"}}, "required": ["case_id", "kind", "reason"]}},
  {"name": "process_cancellation", "description": "Cancel the customer's subscription.",
   "input_schema": {"type": "object", "properties": {"customer_id": {"type": "string"}}, "required": ["customer_id"]}},
]

class Store:
    def __init__(self, seed):
        self.data = copy.deepcopy(seed)
        self.writes = []  # the store diff for this run

    def lookup_order(self, order_id):
        o = self.data["orders"].get(order_id)
        if o is None:
            return {"error": "order not found"}
        c = self.data["customers"][o["customer"]]
        return {"order_id": order_id, "customer_id": o["customer"], "amount": o["amount"],
                "delivered_days_ago": o["delivered_days_ago"], "account_flag": c["account_flag"],
                "address_match": c["address_match"], "prior_returns": c["prior_returns"]}

    def issue_refund(self, order_id, amount):
        self.writes.append({"type": "refund", "order_id": order_id, "amount": amount})
        return {"status": "refund_recorded"}

    def add_store_credit(self, customer_id, amount):
        self.writes.append({"type": "store_credit", "customer_id": customer_id, "amount": amount})
        return {"status": "store_credit_recorded"}

    def escalate(self, case_id, kind, reason):
        self.writes.append({"type": "escalation", "case_id": case_id, "kind": kind, "reason": reason})
        return {"status": "escalation_recorded"}

    def process_cancellation(self, customer_id):
        self.writes.append({"type": "cancellation", "customer_id": customer_id})
        return {"status": "cancellation_recorded"}

    def call(self, name, args):
        allowed = {t["name"] for t in TOOL_SCHEMAS}
        if name not in allowed:
            return {"error": f"unknown tool {name}"}
        return getattr(self, name)(**args)
