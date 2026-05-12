"""Configure + launch the insurance agent on AgentCore Runtime (local Docker build → ECR push)."""
import pickle
import time

from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session

AGENT_NAME = "insurance_agent_local_to_agentcore"
ENTRYPOINT = "insurance_agent.py"
REQUIREMENTS = "requirements.txt"

boto_session = Session()
region = boto_session.region_name or "us-west-2"
print(f"Region: {region}")

runtime = Runtime()

print("Configuring runtime...")
runtime.configure(
    entrypoint=ENTRYPOINT,
    auto_create_execution_role=True,
    auto_create_ecr=True,
    requirements_file=REQUIREMENTS,
    region=region,
    agent_name=AGENT_NAME,
)
print("Configure done.")

print("\nLaunching runtime (local_build=True; builds ARM64 image via local Docker, pushes to ECR)...")
launch = runtime.launch(local_build=True)
print(f"  agent_arn = {launch.agent_arn}")
print(f"  agent_id  = {launch.agent_id}")
print(f"  ecr_uri   = {launch.ecr_uri}")

print("\nWaiting for runtime endpoint to become READY...")
end_states = {"READY", "CREATE_FAILED", "DELETE_FAILED", "UPDATE_FAILED"}
status = runtime.status().endpoint["status"]
while status not in end_states:
    print(f"  status: {status}")
    time.sleep(10)
    status = runtime.status().endpoint["status"]
print(f"\nFinal status: {status}")

state = {
    "region": region,
    "agent_name": AGENT_NAME,
    "agent_arn": launch.agent_arn,
    "agent_id": launch.agent_id,
    "ecr_uri": launch.ecr_uri,
    "final_status": status,
}
with open("_run_state.pkl", "wb") as f:
    pickle.dump(state, f)
print("\nState saved to _run_state.pkl")
