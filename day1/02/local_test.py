"""Quick local sanity check: import the entrypoint and invoke a couple of payloads
without deploying. Useful before running deploy.py.

This calls the @app.entrypoint function in-process, so it does NOT exercise the
AgentCore Runtime HTTP server — but it does prove that the agent + tools work and
that Bedrock credentials/model access are wired up.
"""
from insurance_agent import invoke

PROMPTS = [
    "What information do you have about customer cust-001?",
    "Give me an annual quote for cust-002 on a 2023 Honda Civic.",
]

for prompt in PROMPTS:
    print("=" * 60)
    print(f"PROMPT: {prompt}")
    print("=" * 60)
    print(invoke({"prompt": prompt}))
    print()
