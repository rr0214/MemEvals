"""OpenTelemetry tracing for each run. One root span per run (agent.run), child spans for each
model call (llm.call) and each tool call (tool.call). Spans are flushed to one JSON file per run,
named by the 32-hex trace id. The in-memory exporter is swapped for an OTLP exporter when Phoenix is added."""
import json
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(SimpleSpanProcessor(_exporter))
tracer = _provider.get_tracer("context-harness", "0.1.0")

def flush_run(trace_dir):
    spans = _exporter.get_finished_spans()
    _exporter.clear()
    root = next(s for s in spans if s.parent is None)
    tid = format(root.context.trace_id, "032x")
    records = [json.loads(s.to_json()) for s in spans]
    (trace_dir / f"{tid}.json").write_text(json.dumps(records, indent=2))
    return tid
