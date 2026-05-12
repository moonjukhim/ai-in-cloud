"""Delete the deployed AgentCore runtime + ECR repo + local config."""
import os
import pickle

import boto3

with open("_run_state.pkl", "rb") as f:
    state = pickle.load(f)
region = state["region"]

agentcore_client = boto3.client("bedrock-agentcore", region_name=region)
control_client = boto3.client("bedrock-agentcore-control", region_name=region)
ecr_client = boto3.client("ecr", region_name=region)

# Best-effort: stop the active session.
session_id = state.get("runtime_session_id")
if session_id:
    try:
        agentcore_client.stop_runtime_session(
            agentRuntimeArn=state["agent_arn"],
            runtimeSessionId=session_id,
            qualifier="DEFAULT",
        )
        print(f"Session '{session_id}' stopped")
    except Exception as e:
        print(f"stop_runtime_session: {e}")

# Delete the runtime.
try:
    control_client.delete_agent_runtime(agentRuntimeId=state["agent_id"])
    print(f"Runtime '{state['agent_id']}' deleted")
except Exception as e:
    print(f"delete_agent_runtime: {e}")

# Delete the ECR repository.
repo_name = state["ecr_uri"].split("/", 1)[1]
try:
    ecr_client.delete_repository(repositoryName=repo_name, force=True)
    print(f"ECR repo '{repo_name}' deleted")
except Exception as e:
    print(f"delete_repository: {e}")

# Delete local config.
for path in (".bedrock_agentcore.yaml", "_run_state.pkl"):
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"{path} deleted")
        except Exception as e:
            print(f"remove {path}: {e}")
