# Bank of Anthos

<!-- Checks badge below seem to take a "neutral" check as a negative and shows failures if some checks are neutral. Commenting out the badge for now. -->
<!-- ![GitHub branch check runs](https://img.shields.io/github/check-runs/GoogleCloudPlatform/bank-of-anthos/main) -->
[![Website](https://img.shields.io/website?url=https%3A%2F%2Fcymbal-bank.fsi.cymbal.dev%2F&label=live%20demo
)](https://cymbal-bank.fsi.cymbal.dev)

**Bank of Anthos** is a sample HTTP-based web app that simulates a bank's payment processing network, allowing users to create artificial bank accounts and complete transactions.

Google uses this application to demonstrate how developers can modernize enterprise applications using Google Cloud products, including: [Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine), [Anthos Service Mesh (ASM)](https://cloud.google.com/anthos/service-mesh), [Anthos Config Management (ACM)](https://cloud.google.com/anthos/config-management), [Migrate to Containers](https://cloud.google.com/migrate/containers), [Spring Cloud GCP](https://spring.io/projects/spring-cloud-gcp), [Cloud Operations](https://cloud.google.com/products/operations), [Cloud SQL](https://cloud.google.com/sql/docs), [Cloud Build](https://cloud.google.com/build), and [Cloud Deploy](https://cloud.google.com/deploy). This application works on any Kubernetes cluster.

If you are using Bank of Anthos, please ★Star this repository to show your interest!

**Note to Googlers:** Please fill out the form at [go/bank-of-anthos-form](https://goto2.corp.google.com/bank-of-anthos-form).

## Screenshots

### Dashboard
![Dashboard](ai-services/dashboard.png)

### Budgets
![Budgets](ai-services/budgets.png)

### Contacts
![Contacts](ai-services/contacts.png)

### Transactions
![Transactions](ai-services/transactions.png)

<!-- Legacy screenshots table (if needed)
| Sign in                                                                                                        | Home                                                                                                    |
| ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| [![Login](/docs/img/login.png)](/docs/img/login.png) | [![User Transactions](/docs/img/transactions.png)](/docs/img/transactions.png) |
-->


## Service architecture

![Architecture Diagram](/docs/img/architecture.png)


| Service                                                 | Language      | Description                                                                                                                                |
| ------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| [frontend](/src/frontend)                              | Python        | Exposes an HTTP server to serve the website. Contains login page, signup page, and home page.                                              |
| [ledger-writer](/src/ledger/ledgerwriter)              | Java          | Accepts and validates incoming transactions before writing them to the ledger.                                                             |
| [balance-reader](/src/ledger/balancereader)            | Java          | Provides efficient readable cache of user balances, as read from `ledger-db`.                                                              |
| [transaction-history](/src/ledger/transactionhistory)  | Java          | Provides efficient readable cache of past transactions, as read from `ledger-db`.                                                          |
| [ledger-db](/src/ledger/ledger-db)                     | PostgreSQL    | Ledger of all transactions. Option to pre-populate with transactions for demo users.                                                       |
| [user-service](/src/accounts/userservice)              | Python        | Manages user accounts and authentication. Signs JWTs used for authentication by other services.                                            |
| [contacts](/src/accounts/contacts)                     | Python        | Stores list of other accounts associated with a user. Used for drop down in "Send Payment" and "Deposit" forms.                            |
| [accounts-db](/src/accounts/accounts-db)               | PostgreSQL    | Database for user accounts and associated data. Option to pre-populate with demo users.                                                    |
| [ai-meta-db](/ai-services/ai-meta-db)                  | PostgreSQL    | Central AI metadata database for anomaly detection, transaction logging, budget tracking, and user profiles.                               |
| [anomaly-sage](/ai-services/anomaly-sage)              | Python        | AI microservice for risk analysis and anomaly detection. Logs results to `ai-meta-db`.                                                     |
| [transaction-sage](/ai-services/transaction-sage)      | Python        | AI microservice for transaction categorization, logging, and budget usage. Logs results to `ai-meta-db`.                                   |
| [contact-sage](/ai-services/contact-sage)              | Python        | AI microservice for contact inference and enrichment (e.g., identify likely payees / contact suggestions). Logs results to `ai-meta-db`.    |
| [money-sage](/ai-services/money-sage)                  | Python        | AI microservice for budgeting, spend classification, and money-related insights. Logs results to `ai-meta-db`.                             |
| [orchestrator](/ai-services/orchestrator)              | Python        | Coordinator service that invokes AI agent microservices, handles auth, and provides shared helpers (currency conversion, config).        |


### AI Agent Microservices

**anomaly-sage**: Performs risk analysis and anomaly detection on transactions. It writes risk scores and classifications to the `anomaly_logs` table in `ai-meta-db`.

**transaction-sage**: Categorizes transactions, logs details, and tracks budget usage. It writes to the `transaction_logs` and `budget_usage` tables in `ai-meta-db`.

**ai-meta-db**: Central PostgreSQL database for AI agent microservices. Stores logs, budgets, user profiles, and pending confirmations. See [README-ai-meta-db.md](/ai-services/README-ai-meta-db.md) for schema details.

**contact-sage**: Provides contact-related inference and enrichment for accounts and transactions. Examples: suggest likely payees, normalize contact details, or enrich transaction payee metadata. Writes contact-related events to `ai-meta-db`.

**money-sage**: Focuses on budgeting, spend classification and money-management insights (alerts, monthly summaries). Stores budget and classification outputs in `ai-meta-db`.

**orchestrator**: A small coordinator service used by the AI agents. It contains shared auth helpers (`auth.py`), configuration (`config.py`), currency conversion utilities (`currency_converter.py`), and wiring to call other sage services. It can be used to run or locally emulate agent workflows and exposes its own `main.py` entrypoint.

### Running & testing AI services (local / dev)

Each AI microservice under `ai-services/` is a small Python app with a `main.py` and a `requirements.txt`. The `ai-meta-db/` directory contains a PostgreSQL schema (`0001_create_ai_meta_tables.sql`) and a `Dockerfile` to run the database locally.

Quick steps (PowerShell):

```powershell
# 1) Install Python dependencies for the services you want to run (example installs orchestrator deps)
python -m pip install --upgrade pip; python -m pip install -r .\ai-services\orchestrator\requirements.txt

# 2) Run the AI service directly (example: orchestrator)
python .\ai-services\orchestrator\main.py

# 3) Run the database locally (optional) using the Dockerfile in ai-meta-db, or use your preferred Postgres instance.
#    Example: docker build -t ai-meta-db:local .\ai-services\ai-meta-db; docker run -p 5432:5432 ai-meta-db:local

# 4) Run the AI services tests from the repo root (requires pytest)
python -m pip install pytest; pytest .\ai-services\test_ai_services.py -q
```

Notes:
- If you prefer to install all AI service deps at once, install each `requirements.txt` found in `ai-services/*/requirements.txt` or use a virtual environment per service.
- The tests under `ai-services/` are small integration/unit tests for the agent code (see `test_anomaly_sage.py`, `test_contact_sage.py`, `test_money_sage.py`, `test_transaction_sage.py`).


## Interactive quickstart (GKE)

The following button opens up an interactive tutorial showing how to deploy Bank of Anthos in GKE:

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://ssh.cloud.google.com/cloudshell/editor?show=ide&cloudshell_git_repo=https://github.com/GoogleCloudPlatform/bank-of-anthos&cloudshell_workspace=.&cloudshell_tutorial=extras/cloudshell/tutorial.md)

## Quickstart (GKE)

1. Ensure you have the following requirements:
   - [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects#creating_a_project).
   - Shell environment with `gcloud`, `git`, and `kubectl`.

2. Clone the repository.

   ```sh
   git clone https://github.com/GoogleCloudPlatform/bank-of-anthos
   cd bank-of-anthos/
   ```

3. Set the Google Cloud project and region and ensure the Google Kubernetes Engine API is enabled.

   ```sh
   export PROJECT_ID=<PROJECT_ID>
   export REGION=us-central1
   gcloud services enable container.googleapis.com \
     --project=${PROJECT_ID}
   ```

   Substitute `<PROJECT_ID>` with the ID of your Google Cloud project.

4. Create a GKE cluster and get the credentials for it.

   ```sh
   gcloud container clusters create-auto bank-of-anthos \
     --project=${PROJECT_ID} --region=${REGION}
   ```

   Creating the cluster may take a few minutes.

5. Deploy Bank of Anthos to the cluster.

   ```sh
   kubectl apply -f ./extras/jwt/jwt-secret.yaml
   kubectl apply -f ./kubernetes-manifests
   kubectl apply -f ./kubernetes-manifests/conversational-agent.yaml
   ```

6. Wait for the pods to be ready.

   ```sh
   kubectl get pods
   ```

   After a few minutes, you should see the Pods in a `Running` state:

   ```
   NAME                                  READY   STATUS    RESTARTS   AGE
   accounts-db-6f589464bc-6r7b7          1/1     Running   0          99s
   balancereader-797bf6d7c5-8xvp6        1/1     Running   0          99s
   contacts-769c4fb556-25pg2             1/1     Running   0          98s
   conversational-agent-1a2b3c4d5e-6f7g8   1/1     Running   0          98s
   frontend-7c96b54f6b-zkdbz             1/1     Running   0          98s
   ledger-db-5b78474d4f-p6xcb            1/1     Running   0          98s
   ledgerwriter-84bf44b95d-65mqf         1/1     Running   0          97s
   loadgenerator-559667b6ff-4zsvb        1/1     Running   0          97s
   transactionhistory-5569754896-z94cn   1/1     Running   0          97s
   userservice-78dc876bff-pdhtl          1/1     Running   0          96s
   ```

7. Access the web frontend in a browser using the frontend's external IP.

   ```sh
   kubectl get service frontend | awk '{print $4}'
   ```

   Visit `http://EXTERNAL_IP` in a web browser to access your instance of Bank of Anthos.

8. Once you are done with it, delete the GKE cluster.

   ```sh
   gcloud container clusters delete bank-of-anthos \
     --project=${PROJECT_ID} --region=${REGION}
   ```

   Deleting the cluster may take a few minutes.

## Additional deployment options


- **Workload Identity**: [See these instructions.](/docs/workload-identity.md)
- **Cloud SQL**: [See these instructions](/extras/cloudsql) to replace the in-cluster databases with hosted Google Cloud SQL.
- **Multi Cluster with Cloud SQL**: [See these instructions](/extras/cloudsql-multicluster) to replicate the app across two regions using GKE, Multi Cluster Ingress, and Google Cloud SQL.
- **Istio**: [See these instructions](/extras/istio) to configure an IngressGateway.
- **Anthos Service Mesh**: ASM requires Workload Identity to be enabled in your GKE cluster. [See the workload identity instructions](/docs/workload-identity.md) to configure and deploy the app. Then, apply `extras/istio/` to your cluster to configure frontend ingress.
- **Java Monolith (VM)**: We provide a version of this app where the three Java microservices are coupled together into one monolithic service, which you can deploy inside a VM (eg. Google Compute Engine). See the [ledgermonolith](/src/ledgermonolith) directory.


## Documentation

<!-- This section is duplicated in the docs/ README: https://github.com/GoogleCloudPlatform/bank-of-anthos/blob/main/docs/README.md -->

- [GKE Autopilot Deployment Guide](/docs/GKE_AUTOPILOT_DEPLOYMENT.md) – Step-by-step instructions for creating and deleting clusters on GKE Autopilot using PowerShell.
- [Development](/docs/development.md) to learn how to run and develop this app locally.
- [Environments](/docs/environments.md) to learn how to deploy on non-GKE clusters.
- [Workload Identity](/docs/workload-identity.md) to learn how to set-up Workload Identity.
- [CI/CD pipeline](/docs/ci-cd-pipeline.md) to learn details about and how to set-up the CI/CD pipeline.
- [Troubleshooting](/docs/troubleshooting.md) to learn how to resolve common problems.

## Requirements
- Python 3.12+
- pip 25.1.1+

**Note:** Please ensure you have pip >= 25.1.1 installed before building or testing.
Upgrade with: `python -m pip install --upgrade pip`

## Demos featuring Bank of Anthos
- [Tutorial: Explore Anthos (Google Cloud docs)](https://cloud.google.com/anthos/docs/tutorials/explore-anthos)
- [Tutorial: Migrating a monolith VM to GKE](https://cloud.google.com/migrate/containers/docs/migrating-monolith-vm-overview-setup)
- [Tutorial: Running distributed services on GKE private clusters using ASM](https://cloud.google.com/service-mesh/docs/distributed-services-private-clusters)
- [Tutorial: Run full-stack workloads at scale on GKE](https://cloud.google.com/kubernetes-engine/docs/tutorials/full-stack-scale)
- [Architecture: Anthos on bare metal](https://cloud.google.com/architecture/ara-anthos-on-bare-metal)
- [Architecture: Creating and deploying secured applications](https://cloud.google.com/architecture/security-foundations/creating-deploying-secured-apps)
- [Keynote @ Google Cloud Next '20: Building trust for speedy innovation](https://www.youtube.com/watch?v=7QR1z35h_yc)
- [Workshop @ IstioCon '22: Manage and secure distributed services with ASM](https://www.youtube.com/watch?v=--mPdAxovfE)

## Platform-specific Maven wrapper usage
- **Windows:** Use `mvnw.cmd` and backslashes in paths (e.g., `..\..\..\mvnw.cmd checkstyle:check`)
- **Linux/Mac:** Use `mvnw` and forward slashes (e.g., `../../../mvnw checkstyle:check`)
If you see `'..' is not recognized as an internal or external command`, update your test command as above.
