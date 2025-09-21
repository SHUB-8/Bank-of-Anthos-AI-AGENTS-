# Deploying to GKE Autopilot

This guide provides instructions for deploying the Bank of Anthos application to a cost-effective GKE Autopilot cluster, designed for development and testing.

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

## 3. Create a GKE Autopilot Cluster

This command creates a single-zone Autopilot cluster that can scale down to zero to minimize costs.

```powershell
gcloud container clusters create-auto bank-of-anthos-autopilot `
     --region=$env:REGION
```

## 4. Get Cluster Credentials

After the cluster is created, get the credentials for `kubectl`:
```powershell
gcloud container clusters get-credentials bank-of-anthos-autopilot --region=$env:REGION
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

## 7. Access the Services
```powershell
kubectl get services
```

Get the external IP addresses of the frontend and conversational-agent services:
```powershell
kubectl get services
```

- **Bank of Anthos UI:** Access the application at `http://<EXTERNAL-IP-OF-FRONTEND>`

## 8. Cleanup
```powershell
gcloud container clusters delete bank-of-anthos-autopilot --region=$env:REGION
```

