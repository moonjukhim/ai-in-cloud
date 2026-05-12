"""Invoke the deployed insurance agent via the starter-toolkit SDK and via boto3."""
import json
import pickle

import boto3
from bedrock_agentcore_starter_toolkit import Runtime

with open("_run_state.pkl", "rb") as f:
    state = pickle.load(f)
region = state["region"]
agent_arn = state["agent_arn"]
agent_name = state["agent_name"]

# Re-attach Runtime to the existing config so the SDK invoke knows where to send.
runtime = Runtime()
runtime.configure(
    entrypoint="insurance_agent.py",
    auto_create_execution_role=True,
    auto_create_ecr=True,
    requirements_file="requirements.txt",
    region=region,
    agent_name=agent_name,
)

TEST_PROMPTS = [
    "What information do you have about customer cust-001?",
    "I'd like a quote for a 2023 Honda Civic for customer cust-002.",
    "How safe is a Tesla Model 3?",
]


def show(resp):
    """Pretty-print whatever shape the toolkit invoke returns."""
    if isinstance(resp, dict) and "response" in resp:
        for item in resp["response"]:
            if isinstance(item, (bytes, bytearray)):
                item = item.decode("utf-8")
            print(item)
    else:
        print(resp)


print("=" * 60)
print("1) Invoke via toolkit SDK")
print("=" * 60)
for prompt in TEST_PROMPTS:
    print(f"\n--- prompt: {prompt!r} ---")
    show(runtime.invoke({"prompt": prompt}))

print()
print("=" * 60)
print("2) Invoke via boto3 (captures runtime session id + handles event-stream)")
print("=" * 60)
client = boto3.client("bedrock-agentcore", region_name=region)
boto3_resp = client.invoke_agent_runtime(
    agentRuntimeArn=agent_arn,
    qualifier="DEFAULT",
    payload=json.dumps({"prompt": "Show me policy-003."}),
)
runtime_session_id = boto3_resp.get("runtimeSessionId")
print(f"Runtime Session ID: {runtime_session_id}")
print(f"Content-Type: {boto3_resp.get('contentType', '')}")

if "text/event-stream" in boto3_resp.get("contentType", ""):
    chunks = []
    for line in boto3_resp["response"].iter_lines(chunk_size=1):
        if not line:
            continue
        line = line.decode("utf-8")
        if line.startswith("data: "):
            line = line[6:]
            print(line)
            chunks.append(line)
    print("\n--- aggregated ---")
    print("\n".join(chunks))
else:
    events = []
    try:
        for event in boto3_resp.get("response", []):
            events.append(event)
    except Exception as e:
        events = [f"Error reading EventStream: {e}".encode()]
    parsed = json.loads(events[0].decode("utf-8")) if events else None
    print("Parsed response:")
    print(parsed)

state["runtime_session_id"] = runtime_session_id
with open("_run_state.pkl", "wb") as f:
    pickle.dump(state, f)
print("\nSession ID saved to _run_state.pkl")
