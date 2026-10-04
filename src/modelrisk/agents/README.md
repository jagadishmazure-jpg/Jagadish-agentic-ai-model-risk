# agents

LangGraph-style agents, offline with a mock model and synthetic data. Companies are fictional.

| File | What it does |
|---|---|
| `__init__.py` | Package marker |
| `graph.py` | StateGraph runtime |
| `base.py` | Controls, AgentSpec, the shared graph |
| `llm.py` | MockLLM |
| `guardrails.py` | Screen, masking, tool policy, budget |
| `registry.py` | SPECS by model id |
| `banking.py` | Halcyon fraud triage |
| `insurance.py` | Bramblewood claims |
| `mortgage.py` | Cedar Hollow underwriting |
| `healthcare.py` | Juniper prior authorization |
| `retail.py` | Marigold pricing |
