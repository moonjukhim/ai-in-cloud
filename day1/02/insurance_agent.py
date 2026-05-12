"""
Self-contained Auto Insurance Agent for AWS Bedrock AgentCore Runtime.

Based on local-prototype-to-agentcore/local_prototype's Strands insurance agent,
but with all tool data embedded in-process (no separate FastAPI / MCP server).
This makes the agent a single-file deployable unit suitable for AgentCore Runtime.

Pattern mirrors day1/01.AgentCore-runtime/strands_claude.py.
"""
from datetime import date, datetime
from typing import Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel


# --- Embedded data (originally JSON files in local_insurance_api/data) ---

CUSTOMERS = {
    "cust-001": {
        "first_name": "John", "last_name": "Smith",
        "email": "john.smith@example.com", "phone": "555-123-4567",
        "address": "123 Main St, Anytown, CA 94123", "dob": "1985-06-15",
        "accidents": 1, "violations": 1, "current_policies": ["policy-001"],
    },
    "cust-002": {
        "first_name": "Sarah", "last_name": "Johnson",
        "email": "sarah.johnson@example.com", "phone": "555-987-6543",
        "address": "456 Oak Ave, Somewhere, NY 10001", "dob": "1990-09-23",
        "accidents": 0, "violations": 0, "current_policies": ["policy-002"],
    },
    "cust-003": {
        "first_name": "Michael", "last_name": "Chen",
        "email": "michael.chen@example.com", "phone": "555-456-7890",
        "address": "789 Pine St, Elsewhere, TX 75001", "dob": "1978-12-03",
        "accidents": 1, "violations": 1, "current_policies": ["policy-003"],
    },
}

VEHICLES = {
    ("toyota", "camry"):       {"category": "standard",        "safety_rating": "5_star", "base_2023": 28000},
    ("honda",  "civic"):       {"category": "economy",         "safety_rating": "5_star", "base_2023": 25000},
    ("ford",   "f-150"):       {"category": "standard",        "safety_rating": "4_star", "base_2023": 38000},
    ("bmw",    "3 series"):    {"category": "luxury",          "safety_rating": "5_star", "base_2023": 45000},
    ("tesla",  "model 3"):     {"category": "luxury",          "safety_rating": "5_star", "base_2023": 50000},
    ("chevrolet", "corvette"): {"category": "high_performance","safety_rating": "4_star", "base_2023": 80000},
}

PRODUCTS = [
    {"id": "basic-auto",    "name": "Basic Auto Insurance",    "base_premium": 600.0,
     "description": "Minimum coverage required by law"},
    {"id": "standard-auto", "name": "Standard Auto Insurance", "base_premium": 1000.0,
     "description": "Balanced coverage for most drivers"},
    {"id": "premium-auto",  "name": "Premium Auto Insurance",  "base_premium": 1500.0,
     "description": "Maximum protection for you and your vehicle"},
]

POLICIES = {
    "policy-001": {"customer_id": "cust-001", "premium": 1200.0, "status": "active",
                   "start_date": "2024-01-15", "end_date": "2025-01-15",
                   "vehicle": "2018 Honda Accord"},
    "policy-002": {"customer_id": "cust-002", "premium":  950.0, "status": "active",
                   "start_date": "2024-03-10", "end_date": "2025-03-10",
                   "vehicle": "2020 Tesla Model S"},
    "policy-003": {"customer_id": "cust-003", "premium": 1450.0, "status": "active",
                   "start_date": "2024-05-22", "end_date": "2025-05-22",
                   "vehicle": "2019 Jeep Grand Cherokee"},
}


def _age(dob: str) -> int:
    born = datetime.strptime(dob, "%Y-%m-%d").date()
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _lookup_vehicle(make: str, model: str) -> Optional[dict]:
    return VEHICLES.get((make.strip().lower(), model.strip().lower()))


# --- Strands tools ---

@tool
def get_customer_info(customer_id: str) -> str:
    """Look up an insurance customer by ID (e.g. 'cust-001')."""
    c = CUSTOMERS.get(customer_id.strip().lower())
    if not c:
        return f"Customer '{customer_id}' not found. Try cust-001, cust-002, or cust-003."
    return (
        f"Customer {customer_id}\n"
        f"  Name: {c['first_name']} {c['last_name']}\n"
        f"  Age:  {_age(c['dob'])}\n"
        f"  Address: {c['address']}\n"
        f"  Email: {c['email']}, Phone: {c['phone']}\n"
        f"  Driving history: {c['accidents']} accident(s), {c['violations']} violation(s)\n"
        f"  Current policies: {', '.join(c['current_policies']) or 'none'}"
    )


@tool
def get_vehicle_info(make: str, model: str, year: int) -> str:
    """Look up vehicle specs/value by make, model and year (e.g. Toyota Camry 2023)."""
    v = _lookup_vehicle(make, model)
    if not v:
        known = ", ".join(f"{m.title()} {mo.title()}" for m, mo in VEHICLES)
        return f"Vehicle '{year} {make} {model}' not in catalog. Known: {known}."
    age = max(0, date.today().year - int(year))
    # naive depreciation from base_2023: 8%/yr away from 2023
    drift = 1.0 + 0.08 * (int(year) - 2023)
    current = max(2000, int(v["base_2023"] * drift * max(0.4, 1 - 0.08 * age)))
    return (
        f"{year} {make.title()} {model.title()}\n"
        f"  Category: {v['category']}\n"
        f"  Safety rating: {v['safety_rating']}\n"
        f"  Estimated current value: ${current:,}\n"
        f"  Vehicle age: {age} year(s)"
    )


@tool
def get_vehicle_safety(make: str, model: str) -> str:
    """Get the safety rating and assessment for a vehicle make/model."""
    v = _lookup_vehicle(make, model)
    if not v:
        return f"No safety data for {make} {model}."
    rating = v["safety_rating"]
    stars = int(rating.split("_")[0])
    assessment = {5: "Excellent", 4: "Very Good", 3: "Good", 2: "Fair", 1: "Poor"}[stars]
    return f"Safety for {make.title()} {model.title()}: {stars}/5 stars — {assessment}."


@tool
def get_insurance_quote(customer_id: str, make: str, model: str, year: int) -> str:
    """Produce an annual auto-insurance quote for a customer + vehicle across all product tiers."""
    c = CUSTOMERS.get(customer_id.strip().lower())
    if not c:
        return f"Customer '{customer_id}' not found."
    v = _lookup_vehicle(make, model)
    if not v:
        return f"Vehicle '{year} {make} {model}' not in catalog."

    age = _age(c["dob"])
    age_factor    = 1.30 if age < 25 else 1.15 if age < 30 else 1.00 if age < 65 else 1.10
    history_factor = 1.00 + 0.10 * c["accidents"] + 0.05 * c["violations"]
    cat_factor = {"economy": 0.90, "standard": 1.00, "luxury": 1.25, "high_performance": 1.45}[v["category"]]
    safety_factor = 0.95 if v["safety_rating"] == "5_star" else 1.00

    risk_score = age_factor * history_factor * cat_factor * safety_factor
    risk_label = (
        "low" if risk_score < 1.05 else
        "moderate" if risk_score < 1.25 else
        "high" if risk_score < 1.5 else "very high"
    )

    lines = [
        f"Quote for customer {customer_id} on {year} {make.title()} {model.title()}",
        f"  Age factor: {age_factor:.2f} (age {age})",
        f"  Driving history factor: {history_factor:.2f} "
        f"({c['accidents']} accident(s), {c['violations']} violation(s))",
        f"  Vehicle category factor: {cat_factor:.2f} ({v['category']})",
        f"  Safety factor: {safety_factor:.2f} ({v['safety_rating']})",
        f"  Overall risk: {risk_label} (score {risk_score:.2f})",
        "",
        "Annual premiums:",
    ]
    for p in PRODUCTS:
        annual = round(p["base_premium"] * risk_score, 2)
        lines.append(f"  - {p['name']}: ${annual:,.2f}  ({p['description']})")
    return "\n".join(lines)


@tool
def get_policy_by_id(policy_id: str) -> str:
    """Look up an existing policy by ID (e.g. 'policy-001')."""
    p = POLICIES.get(policy_id.strip().lower())
    if not p:
        return f"Policy '{policy_id}' not found."
    return (
        f"Policy {policy_id} — status {p['status']}\n"
        f"  Customer: {p['customer_id']}\n"
        f"  Premium:  ${p['premium']:,.2f}\n"
        f"  Period:   {p['start_date']} to {p['end_date']}\n"
        f"  Vehicle:  {p['vehicle']}"
    )


# --- Strands Agent + AgentCore wiring ---

SYSTEM_PROMPT = """You are an auto-insurance assistant.

You have these tools (no external API — data is in-process):
- get_customer_info(customer_id)
- get_vehicle_info(make, model, year)
- get_vehicle_safety(make, model)
- get_insurance_quote(customer_id, make, model, year)
- get_policy_by_id(policy_id)

Be concise and professional. Always call a tool when the question is about a specific
customer, vehicle, policy, or quote. If the user asks for a quote, you need a
customer_id plus the vehicle's make/model/year — ask for whatever is missing.
"""

MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"

app = BedrockAgentCoreApp()
agent = Agent(
    model=BedrockModel(model_id=MODEL_ID),
    tools=[get_customer_info, get_vehicle_info, get_vehicle_safety,
           get_insurance_quote, get_policy_by_id],
    system_prompt=SYSTEM_PROMPT,
)


@app.entrypoint
def invoke(payload):
    """AgentCore Runtime entrypoint. Expects {'prompt': '...'} or {'user_input': '...'}."""
    user_input = payload.get("prompt") or payload.get("user_input")
    if not user_input:
        return "Please supply 'prompt' (or 'user_input') in the payload."
    print(f"[insurance_agent] user_input={user_input!r}")
    response = agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
