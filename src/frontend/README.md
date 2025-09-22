
# Frontend Service

The frontend service is the user-facing web interface for Bank of Anthos, built with Python and Flask. It handles authentication, account management, payments, and displays account information.

## Features
- User authentication (JWT-based)
- Account overview and transaction history
- Internal payments and external deposits
- Signup and login flows
- Integration with backend microservices via REST APIs
- Configurable branding and platform banners

## Endpoints
| Endpoint   | Type  | Auth? | Description |
| ---------- | ----- | ----- | ----------------------------------------------------------------------------------------- |
| `/`        | GET   | 🔒    | Renders `/home` or `/login` based on authentication status |
| `/home`    | GET   | 🔒    | Renders homepage if authenticated, else redirects to `/login` |
| `/login`   | GET   |       | Renders login page if not authenticated, else redirects to `/home` |
| `/login`   | POST  |       | Submits login request to `userservice` |
| `/logout`  | POST  | 🔒    | Deletes local authentication token and redirects to `/login` |
| `/signup`  | GET   |       | Renders signup page if not authenticated, else redirects to `/home` |
| `/signup`  | POST  |       | Submits new user signup request to `userservice` |
| `/deposit` | POST  | 🔒    | Submits a new external deposit transaction to `ledgerwriter` |
| `/payment` | POST  | 🔒    | Submits a new internal payment transaction to `ledgerwriter` |
| `/ready`   | GET   |       | Readiness probe endpoint |
| `/version` | GET   |       | Returns the contents of `$VERSION` |

## Environment Variables
- `VERSION`: Service version string
- `PORT`: Webserver port
- `SCHEME`: URL scheme for redirects (http/https)
- `DEFAULT_USERNAME`, `DEFAULT_PASSWORD`: Pre-populate login fields (optional)
- `BANK_NAME`: Bank name for navbar (default: Bank of Anthos)
- `CYMBAL_LOGO`: Show CymbalBank logo (default: false)
- `ENV_PLATFORM`: Platform banner (alibaba, aws, azure, gcp, local, onprem)

## ConfigMap Settings
- `environment-config`:
  - `LOCAL_ROUTING_NUM`: Routing number for the bank
  - `PUB_KEY_PATH`: Path to JWT signer's public key (mounted as secret)
- `service-api-config`:
  - `TRANSACTIONS_API_ADDR`: Address/port of `ledgerwriter`
  - `BALANCES_API_ADDR`: Address/port of `balancereader`
  - `HISTORY_API_ADDR`: Address/port of `transactionhistory`
  - `CONTACTS_API_ADDR`: Address/port of `contacts`
  - `USERSERVICE_API_ADDR`: Address/port of `userservice`

## Deployment
- See [GKE Autopilot Deployment Guide](/docs/GKE_AUTOPILOT_DEPLOYMENT.md)
- Kubernetes resources: [frontend deployment & service](/kubernetes-manifests/frontend.yaml)

## Usage
Build and run locally:
```sh
python frontend.py
```
Or deploy to Kubernetes as described above.
