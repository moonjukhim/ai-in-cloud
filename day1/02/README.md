# Local → AgentCore: Self-contained Insurance Agent

이 폴더는 `local-prototype-to-agentcore/local_prototype`의 Strands 기반 보험 에이전트를
AWS Bedrock AgentCore Runtime에 **단일 컨테이너**로 배포하는 최소 예제입니다.

원본 cloud migration(`agentcore_app/`)과 달리:
- MCP Gateway / Cognito / Lambda를 사용하지 않습니다.
- 보험 데이터(고객/차량/상품/정책)는 `insurance_agent.py` 안에 인라인 상수로 들어가 있습니다.
- 도구는 Strands `@tool`로 정의되어 에이전트 프로세스 안에서 실행됩니다.

검증된 배포 패턴은 `day1/01.AgentCore-runtime`의 starter-toolkit 사용 방식을 그대로 따릅니다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `insurance_agent.py` | Strands `Agent` + `BedrockAgentCoreApp`의 entrypoint. 5개의 `@tool` 포함. |
| `requirements.txt` | 컨테이너 내부 의존성 (`strands-agents`, `bedrock-agentcore`, …). |
| `.dockerignore` | starter-toolkit이 생성한 Dockerfile이 참조. 배포 스크립트는 이미지에서 제외. |
| `deploy.py` | `Runtime().configure()` → `launch(local_build=True)` → `READY` 대기. 상태를 `_run_state.pkl`에 저장. |
| `invoke.py` | starter-toolkit SDK + boto3 양쪽으로 invoke 테스트. |
| `cleanup.py` | runtime + ECR repo + 로컬 설정 삭제. |
| `local_test.py` | 배포 없이 in-process 호출만으로 에이전트 동작 확인. |

## 사전 준비

1. AWS 자격증명 (`aws configure` 또는 `AWS_PROFILE`), Bedrock 모델 접근 권한
2. Docker Desktop 실행 중 (`local_build=True`는 ARM64 이미지를 로컬에서 빌드)
3. Python 3.10+ + `pip install -r requirements.txt`

## 실행 순서

```powershell
# 0) (선택) 배포 전 in-process로 도구 동작 확인
python local_test.py

# 1) AgentCore Runtime에 배포
python deploy.py

# 2) 배포된 runtime invoke (3가지 프롬프트 SDK 호출 + 1개 boto3 호출)
python invoke.py

# 3) 정리
python cleanup.py
```

## Entrypoint 페이로드

```json
{ "prompt": "What information do you have about customer cust-001?" }
```

`prompt` 키 또는 `user_input` 키 모두 허용합니다.

## 도구

- `get_customer_info(customer_id)` — cust-001 / cust-002 / cust-003
- `get_vehicle_info(make, model, year)` — Toyota Camry, Honda Civic, Ford F-150, BMW 3 Series, Tesla Model 3, Chevrolet Corvette
- `get_vehicle_safety(make, model)`
- `get_insurance_quote(customer_id, make, model, year)` — 3개 상품 등급으로 연간 보험료 산출
- `get_policy_by_id(policy_id)` — policy-001 / policy-002 / policy-003
