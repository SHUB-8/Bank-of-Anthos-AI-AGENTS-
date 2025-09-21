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

Start minikube:
```powershell
minikube start
```

## 2. Build the Java services

Build the Java microservices using Maven:
```powershell
mvn clean install -f pom.xml
```

## 3. Set up Python environments

Create and activate a Python virtual environment for each Python service (`frontend`, `userservice`, `contacts`, `ai-services/conversational_banking_agent`).

For each service:
```powershell
cd src/<service_name>
python -m venv .venv
.venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

## 4. Configure environment variables

All secrets, API keys, and config are now loaded from Kubernetes manifests (see `jwt-secret.yaml`, `api-keys-secret.yaml`, etc). No .env files are required.

## 5. Build and deploy images (local dev)

First, ensure you are using Minikube's Docker environment:
```powershell
& minikube docker-env | Invoke-Expression
```

Build the images for the AI agent services:
```powershell
docker build -t bank-of-anthos/transaction-sage:latest ./ai-services/transaction-sage
# Repeat for other services
```

## 6. Apply manifests and deploy services

Apply all manifests (which reference secrets/config via Kubernetes secrets):
```powershell
kubectl apply -f ./kubernetes-manifests/
```

### Ensure JWT secret and database constraint
```powershell
kubectl apply -f ./extras/jwt/jwt-secret.yaml
```
- Ensure the `budget_usage` table has a unique constraint named `uix_budget_usage` on `(account_id, category, period_start, period_end)`.

## 7. Port-forward and test endpoints

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

## 8. Access the application

Once all the pods are running, you can access the frontend service:
```powershell
minikube service frontend
```
This will open the Bank of Anthos application in your web browser.

## 9. Local development workflow

With Skaffold, you can use `skaffold dev` to enable a continuous development workflow. Any changes you make to the source code will be automatically detected, and Skaffold will rebuild and redeploy the updated services.

```powershell
skaffold dev
```

## 10. Accessing the Conversational AI Agent

**Note:** The conversational agent is not present in the current setup. Only the AI agent services (`anomaly-sage`, `transaction-sage`, `ai-meta-db`) are deployed.

## 11. Stopping the application

To stop and clean up the application, run:
```powershell
skaffold delete
minikube stop
```

## 12. Building and pushing images for GKE

When deploying to GKE, build and push your images to Google Container Registry (GCR):

```powershell
# Authenticate Docker to GCR
 gcloud auth configure-docker

# Build and tag your image for GCR
 docker build -t gcr.io/$env:PROJECT_ID/transaction-sage:latest ./ai-services/transaction-sage
 # Repeat for other services

# Push the image
 docker push gcr.io/$env:PROJECT_ID/transaction-sage:latest
```

Update your Kubernetes manifests to reference the GCR image:
```yaml
image: gcr.io/$PROJECT_ID/transaction-sage:latest
```

Apply manifests as usual:
```powershell
kubectl apply -f ./kubernetes-manifests/
```
