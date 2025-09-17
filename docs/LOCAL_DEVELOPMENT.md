# Local Development Setup

This guide provides instructions for setting up the Bank of Anthos application for local development, including all core microservices and the AI agent services (`anomaly-sage`, `transaction-sage`, and `ai-meta-db`).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
- [minikube](https://minikube.sigs.k8s.io/docs/start/) (or another local Kubernetes cluster)
- [skaffold](https://skaffold.dev/docs/install/)
- [Java 11 or higher](https://www.oracle.com/java/technologies/javase-jdk11-downloads.html)
- [Maven](https://maven.apache.org/install.html)
- [Python 3.9 or higher](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)
- [gcloud CLI](https://cloud.google.com/sdk/gcloud) (optional, for GCP integration)

## 1. Start your local Kubernetes cluster

Start minikube (or your preferred local Kubernetes solution):

```sh
minikube start
```

## 2. Build the Java services

Build the Java microservices using Maven:

```sh
mvn clean install -f pom.xml
```

## 3. Set up Python environments

Create and activate a Python virtual environment for each Python service (`frontend`, `userservice`, `contacts`, `ai-services/conversational_banking_agent`).

For each service:

```sh
cd src/<service_name>
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
pip install -r requirements.txt
```

## 4. Configure environment variables

The `conversational_banking_agent` requires a `GEMINI_API_KEY` to be set in its environment. You can either set this directly in your shell or create a `.env` file in the `ai-services/conversational_banking_agent` directory.

```
GEMINI_API_KEY="your_api_key"
```

## 5. Deploy the application using Skaffold

### Build and load images in Minikube

First, ensure you are using Minikube's Docker environment:
```powershell
& minikube docker-env | Invoke-Expression
```

Build the images for the AI agent services:
```powershell
docker build -t ai-meta-db ./ai-services/ai-meta-db
docker build -t anomaly-sage ./ai-services/anomaly-sage
docker build -t transaction-sage ./ai-services/transaction-sage
```

### Apply manifests and deploy services

Apply the PersistentVolumeClaim for ai-meta-db:
```powershell
kubectl apply -f kubernetes-manifests/ai-meta-db-pvc.yaml
```

Apply the manifests for all services:
```powershell
kubectl apply -f kubernetes-manifests/ai-meta-db.yaml
kubectl apply -f kubernetes-manifests/anomaly-sage.yaml
kubectl apply -f kubernetes-manifests/transaction-sage.yaml
```

### Port-forward and test endpoints

Port-forward the services to your local machine (use separate terminals):
```powershell
kubectl port-forward svc/anomaly-sage 8081:8080
kubectl port-forward svc/transaction-sage 8082:8080
kubectl port-forward svc/ai-meta-db 5432:5432
```

Test endpoints using PowerShell:
```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8081/v1/health" -Method Get
Invoke-RestMethod -Uri "http://localhost:8082/v1/health" -Method Get

# Example anomaly check
Invoke-RestMethod -Uri "http://localhost:8081/v1/anomaly/check" -Method Post -Body '{"transaction_id":123,"account_id":"A123456789","amount_cents":1000,"recipient":"B987654321"}' -ContentType "application/json" -Headers @{ "X-Correlation-ID" = "test-corr-id" }
```

To access the database, use:
```powershell
kubectl exec -it ai-meta-db-0 -- psql -U ai_meta_admin -d ai_meta_db
```

## 6. Access the application

Once all the pods are running, you can access the frontend service.

```sh
minikube service frontend
```

This will open the Bank of Anthos application in your web browser.

## 7. Local development workflow

With Skaffold, you can use `skaffold dev` to enable a continuous development workflow. Any changes you make to the source code will be automatically detected, and Skaffold will rebuild and redeploy the updated services.

```sh
skaffold dev
```

## 8. Accessing the Conversational AI Agent

**Note:** The conversational agent is not present in the current setup. Only the AI agent services (`anomaly-sage`, `transaction-sage`, `ai-meta-db`) are deployed.

## 9. Stopping the application

To stop and clean up the application, run:

```sh
skaffold delete
minikube stop
```
