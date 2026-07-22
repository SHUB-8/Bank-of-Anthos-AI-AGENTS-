# Bank of Anthos — MCP Servers

Four domain-grouped [Model Context Protocol (MCP)](https://modelcontextprotocol.io) servers that expose Bank of Anthos banking operations as tools for external AI agents. Each server runs inside the Kubernetes cluster as a Dockerized microservice, accessible via **streamable HTTP** over **NodePort** services.

## Architecture

```
External AI Agent
        │  SSE (HTTP)
        ▼
┌─────────────────────────────────────────────────────────┐
│  NodePort Services                                      │
│  :31100  Identity    :31200  Payments                   │
│  :31300  Financial   :31400  Risk                       │
└───┬──────────┬──────────┬──────────┬────────────────────┘
    ▼          ▼          ▼          ▼
 ┌────────────────────────────────────────────────────┐
 │  Internal K8s Services                             │
 │  userservice · contacts · contact-sage             │
 │  balancereader · transactionhistory · ledgerwriter │
 │  transaction-sage · money-sage · anomaly-sage      │
 └────────────────────────────────────────────────────┘
```

## MCP Servers

| Server | NodePort | Tools | Upstream Services |
|:---|:---|:---|:---|
| **Identity & Contacts** | `31100` | `login`, `create_user`, `list_contacts`, `resolve_contact`, `add_contact`, `update_contact`, `delete_contact` | userservice, contact-sage |
| **Payments & Ledger** | `31200` | `get_balance`, `get_transaction_history`, `get_transaction_count`, `transfer_money`, `deposit_funds` | money-sage, transaction-sage |
| **Financial Insights** | `31300` | `get_spending_summary`, `get_budget_overview`, `get_savings_tips`, `create_budget`, `get_budgets`, `update_budget`, `delete_budget` | money-sage |
| **Risk & Security** | `31400` | `evaluate_transaction_risk`, `get_flagged_anomalies`, `confirm_pending_transaction`, `cancel_pending_transaction` | anomaly-sage |

## Auth Flow

1. Call `login(username, password)` on the **Identity & Contacts** server (`:31100`)
2. Receive a JWT `token` in the response
3. Pass this token as `bearer_token` to **every** subsequent tool call on **any** server

## Quick Start

### 1. Build Docker Images

From the `mcp-servers/` directory:

```bash
# Build all 4 images (run from mcp-servers/ directory)
docker build -t mcp-identity-contacts:latest -f identity-contacts/Dockerfile .
docker build -t mcp-payments-ledger:latest   -f payments-ledger/Dockerfile .
docker build -t mcp-financial-insights:latest -f financial-insights/Dockerfile .
docker build -t mcp-risk-security:latest     -f risk-security/Dockerfile .
```

> **Minikube users:** Run `eval $(minikube docker-env)` before building so
> images are available inside the cluster.

### 2. Deploy to Kubernetes

```bash
kubectl apply -f identity-contacts/k8s/deployment.yaml
kubectl apply -f payments-ledger/k8s/deployment.yaml
kubectl apply -f financial-insights/k8s/deployment.yaml
kubectl apply -f risk-security/k8s/deployment.yaml
```

### 3. Verify

```bash
kubectl get pods -l tier=mcp
kubectl get svc  -l tier=mcp
```

### 4. Connect from External Agent

Each MCP server exposes a streamable HTTP endpoint at:

```
http://<node-ip>:<nodeport>/mcp
```

For Minikube:
```bash
minikube service mcp-identity-contacts --url
# → http://192.168.49.2:31100
```

## Agent Configuration Examples

### Claude Desktop / Cursor (via mcp-remote or streamable HTTP client)

```json
{
  "mcpServers": {
    "bank-identity": {
      "url": "http://<node-ip>:31100/mcp"
    },
    "bank-payments": {
      "url": "http://<node-ip>:31200/mcp"
    },
    "bank-financial": {
      "url": "http://<node-ip>:31300/mcp"
    },
    "bank-risk": {
      "url": "http://<node-ip>:31400/mcp"
    }
  }
}
```

## Environment Variables

Each server reads upstream service URLs from environment variables
(with K8s DNS defaults):

| Variable | Default | Used By |
|:---|:---|:---|
| `MCP_PORT` | `8080` | All servers |
| `USERSERVICE_URL` | `http://userservice:8080` | Identity |
| `CONTACT_SAGE_URL` | `http://contact-sage:8083` | Identity |
| `MONEY_SAGE_URL` | `http://money-sage:8084` | Payments, Financial |
| `TRANSACTION_SAGE_URL` | `http://transaction-sage:8086` | Payments |
| `ANOMALY_SAGE_URL` | `http://anomaly-sage:8085` | Risk |
