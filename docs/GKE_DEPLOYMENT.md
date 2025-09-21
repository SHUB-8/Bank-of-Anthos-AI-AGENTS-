# Deploying to Google Kubernetes Engine (GKE)

This guide provides comprehensive instructions for deploying the Bank of Anthos application, including the conversational AI agent, to a Google Kubernetes Engine (GKE) cluster.

## Prerequisites

- A [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects) with billing enabled.
- The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated.
- `kubectl` installed. You can install it via `gcloud`:
  ```powershell
  gcloud components install kubectl
  ```
- A PowerShell environment.

## 1. Set up your Google Cloud project

Set your project ID and preferred region as environment variables:

```powershell
$env:PROJECT_ID = "your-gcp-project-id"
$env:REGION = "us-central1"
gcloud config set project $env:PROJECT_ID
gcloud config set compute/region $env:REGION
```

Enable the necessary APIs:
```powershell
gcloud services enable container.googleapis.com
```

## 2. Build and push images to Google Container Registry (GCR)

Authenticate Docker to GCR:
```powershell
gcloud auth configure-docker
```

Build and tag your image for GCR:
```powershell
docker build -t gcr.io/$env:PROJECT_ID/transaction-sage:latest ./ai-services/transaction-sage
# Repeat for other services
```

Push the image:
```powershell
docker push gcr.io/$env:PROJECT_ID/transaction-sage:latest
```

## 3. Create a GKE Cluster

You have two options for creating a GKE cluster: Autopilot or Standard. For most use cases, **Autopilot is recommended** as it simplifies cluster management by automating node provisioning and scaling.

### Option 1: GKE Autopilot Cluster (Recommended)

Create an Autopilot cluster:
```powershell
gcloud container clusters create-auto bank-of-anthos-cluster `
    --region=$env:REGION
```

### Option 2: GKE Standard Cluster

Create a Standard GKE cluster:
```powershell
gcloud container clusters create bank-of-anthos-cluster `
    --region=$env:REGION `
    --machine-type=e2-standard-4 `
    --num-nodes=2 `
    --enable-autoscaling --min-nodes=2 --max-nodes=5
```

## 4. Get Cluster Credentials

After the cluster is created, get the credentials for `kubectl`:
```powershell
gcloud container clusters get-credentials bank-of-anthos-cluster --region=$env:REGION
```

## 5. Deploy the Application

All secrets, API keys, and config are loaded from Kubernetes manifests (see `jwt-secret.yaml`, `api-keys-secret.yaml`, etc). No .env files are required.

Update your Kubernetes manifests to reference the GCR image:
```yaml
image: gcr.io/$PROJECT_ID/transaction-sage:latest
```

Apply manifests:
```powershell
kubectl apply -f ./extras/jwt/jwt-secret.yaml
kubectl apply -f ./kubernetes-manifests/ai-meta-db-pvc.yaml
kubectl apply -f ./kubernetes-manifests/ai-meta-db.yaml
kubectl apply -f ./kubernetes-manifests/anomaly-sage.yaml
kubectl apply -f ./kubernetes-manifests/transaction-sage.yaml
# Apply other manifests as needed
```

## 6. Verify the Deployment

Check the status of the pods:
```powershell
kubectl get pods
```

It may take a few minutes for all the pods to be in the `Running` state.

## 7. Access the Application

Get the external IP address of the frontend service:
```powershell
kubectl get service frontend
```

Once the `EXTERNAL-IP` is available, you can access the Bank of Anthos application by navigating to `http://<EXTERNAL-IP>` in your web browser.

## 8. Accessing the Conversational AI Agent

The conversational AI agent is exposed through a service. To interact with it, get the service's external IP:
```powershell
kubectl get service conversational-agent
```

Then, send a POST request to the `/chat` endpoint:
```powershell
Invoke-RestMethod -Uri "http://<AGENT_EXTERNAL_IP>/chat" -Method Post -Body '{"message": "what is my balance?"}' -ContentType "application/json"
```

## 9. Cleanup

To avoid incurring charges to your GCP account, delete the GKE cluster when you are finished:
```powershell
gcloud container clusters delete bank-of-anthos-cluster --region=$env:REGION
```
