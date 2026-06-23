"""The intelligence layer — a per-blog LangGraph state graph.

Discovery → Research → Outline → Draft → Critique → [human email gate]
→ Finalize → Visuals → Distribute, with the run's Firestore document acting as
the durable checkpoint so a run can pause at the email gate and resume in a
separate (serverless) process.
"""
