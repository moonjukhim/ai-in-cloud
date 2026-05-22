# Amazon Cognito OAuth2 Three-Tier Authentication with Amazon Bedrock AgentCore

Per-tier token isolation with Amazon Cognito User Pool OAuth2 and RBAC-based access control. This is a port of the [Okta version](../README.md) to Cognito; the architecture and request flow are identical.

## Architecture

```
User (Cognito JWT: agentcore/agent:invoke)
  | Validates user token via Cognito OIDC
Agent Runtime (Cognito JWT: agentcore/gateway:invoke)
  | Validates agent token via Cognito OIDC + allowedClients
Gateway
  |-- OAuth2 Credential Provider (tool sync -- control plane)
  +-- Interceptor Lambda (token exchange -- data plane)
  | Fresh Cognito JWT (scope: agentcore/mcp:invoke)
MCP Server Runtime
  | Validates MCP token via Cognito OIDC
  | RBAC check on caller's group -> returns or denies data
```

Each tier validates its inbound JWT via Cognito OIDC (signature, expiry, issuer, `client_id`). No token is ever forwarded downstream.

## Key Differences from the Okta Version

| Concern | Okta | Amazon Cognito |
|---|---|---|
| Authorization server | Custom Authorization Server per tenant | The Cognito User Pool itself |
| Issuer | `https://{domain}/oauth2/{authServerId}` | `https://cognito-idp.{region}.amazonaws.com/{userPoolId}` |
| Token endpoint | `{issuer}/v1/token` | `https://{domain}.auth.{region}.amazoncognito.com/oauth2/token` |
| Authorize endpoint | `{issuer}/v1/authorize` | `https://{domain}.auth.{region}.amazoncognito.com/oauth2/authorize` |
| Discovery | `{issuer}/.well-known/openid-configuration` | `{issuer}/.well-known/openid-configuration` |
| Custom scope format | `mcp:invoke` | `{resourceServerId}/mcp:invoke` (resource server prefix required) |
| Access-token `aud` claim | Configurable per auth server | Not populated; validate `client_id` instead |
| Gateway `allowedAudience` | Required | Omitted (Cognito access tokens have no `aud`) |
| Groups claim | `groups` (configurable) | `cognito:groups` (built-in, list type) |
| DPoP | Must be disabled per app | Not applicable |

## Cognito Setup

You can create everything in the AWS Console (Cognito > User Pools) or via the AWS CLI. The notebook does **not** provision the User Pool for you — set it up once, fill in `.env`, then run the notebook.

### 1. Create a User Pool

- Sign-in options: email
- Password policy: as you like; **set permanent passwords on demo users** (no FORCE_CHANGE_PASSWORD)
- MFA: off for demo

### 2. Add a Hosted UI domain

User Pool > App integration > Domain. Pick a unique prefix; full domain becomes:

```
https://{prefix}.auth.{region}.amazoncognito.com
```

Set `COGNITO_DOMAIN_PREFIX` in `.env` to the prefix only.

### 3. Create a Resource Server with three custom scopes

User Pool > App integration > Resource servers > Create.

- Identifier: `agentcore` (set `COGNITO_RESOURCE_SERVER_ID=agentcore` in `.env`)
- Custom scopes:
  - `agent:invoke`
  - `gateway:invoke`
  - `mcp:invoke`

These will appear in tokens as `agentcore/agent:invoke`, etc.

### 4. Create three App Clients

User Pool > App integration > App clients.

| App client | Type | Auth flows / OAuth grants | Allowed scopes |
|---|---|---|---|
| `agentcore-gateway` | Confidential (with secret) | `client_credentials` | `agentcore/mcp:invoke` |
| `agentcore-agent` | Confidential (with secret) | `client_credentials` | `agentcore/gateway:invoke` |
| `agentcore-user-web` | Confidential (with secret) | `authorization_code` | `agentcore/agent:invoke`, `openid`, `email`, `profile` |

For the user web client:
- Callback URL: `http://localhost:8080/callback`
- Enable Hosted UI
- Enable `ALLOW_USER_PASSWORD_AUTH` if you want to test without the Hosted UI; the notebook itself uses the Hosted UI authorization-code flow.

Note: `client_credentials` grant requires a Resource Server with scopes selected on the app client. Cognito will refuse to enable `client_credentials` without one.

### 5. Create groups and demo users

User Pool > Groups:
- `engineering-admin`
- `finance-viewer`

User Pool > Users:
- `alice@example.com` -> assign to `engineering-admin`
- `bob@example.com` -> assign to `finance-viewer`

Set permanent passwords (e.g. via `aws cognito-idp admin-set-user-password --permanent`). The notebook will open the Hosted UI for each user during the test step.

### 6. Fill in `.env`

Copy `.env.example` to `.env` and fill in the values from the steps above.

## Prerequisites

- Python 3.10+
- AWS credentials configured with AgentCore + IAM + Lambda + SSM + Cognito permissions
- A Cognito User Pool set up as above

## Getting Started

The notebook `cognito-auth-three-tier-end-to-end-demo.ipynb` walks through the full deployment, mirroring the Okta version:

1. Install dependencies and configure environment
2. Deploy MCP Server to AgentCore Runtime (Tier 3)
3. Deploy AgentCore Gateway with Interceptor Lambda (Tier 2)
4. Deploy Agent Runtime (Tier 1)
5. Test the full chain as Alice (full access) and Bob (limited access)
6. Verify token isolation
7. Cleanup AWS-side resources

## Project Structure

```
cognito_ver/
|-- cognito-auth-three-tier-end-to-end-demo.ipynb   # Main deployment notebook
|-- mcp_server.py                                   # MCP Server with RBAC and security header middleware
|-- requirements.txt                                # Python dependencies for the MCP Server container
+-- .env.example                                    # Environment variable template
```

`agent_runtime/`, `Dockerfile`, `.dockerignore`, and `.bedrock_agentcore.yaml` are generated at deploy time by the starter toolkit.

## Notes on the Port

- The MCP Server (`mcp_server.py`) is identical to the Okta version. JWT validation happens at the AgentCore Runtime layer (via `customJWTAuthorizer`), not inside the server.
- The Interceptor Lambda's token-fetch logic is the same OAuth2 `client_credentials` POST -- only the endpoint URL, scope format, and the env vars it reads change.
- The Gateway authorizer drops `allowedAudience` (Cognito access tokens don't carry an `aud` claim) and keeps `allowedClients` for `client_id`-based validation.
- The end-user identity propagation still flows via custom HTTP headers + body `_meta` injection -- nothing Cognito-specific changes there. If you want to enforce groups from the access token instead of trusting the caller's header, decode the JWT in the Agent Runtime and set the header from `cognito:groups`.
