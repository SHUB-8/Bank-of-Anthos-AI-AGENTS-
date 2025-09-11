# Deploying to GKE Autopilot

This guide provides instructions for deploying the Bank of Anthos application to a cost-effective GKE Autopilot cluster, designed for development and testing.

## Prerequisites

- A [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects) with billing enabled.
- The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated.
- `kubectl` installed. You can install it via `gcloud`:
  ```powershell
  gcloud components install kubectl
  ```
- A powershell environment.

## 1. Set up your Google Cloud project

First, set your project ID and preferred region as environment variables:

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


## 2. Create a GKE Autopilot Cluster

This command creates a single-zone Autopilot cluster that can scale down to zero to minimize costs.

```powershell
gcloud container clusters create-auto bank-of-anthos-autopilot `
     --region=$env:REGION `
     --cluster-version=latest `
     --enable-autoscaling --min-nodes=0 --max-nodes=5
```
- `--enable-autoscaling --min-nodes=0 --max-nodes=5`: This configures the cluster to scale down to 0 nodes when not in use, and scale up to a maximum of 5 nodes.



## 3. Get Cluster Credentials

After the cluster is created, get the credentials for `kubectl`:
```powershell
gcloud container clusters get-credentials bank-of-anthos-autopilot --region=$env:REGION
```


## 4. Deploy the Application

Now you can deploy the Bank of Anthos application to your GKE cluster.
     ```powershell
     kubectl apply -f ./extras/jwt/jwt-secret.yaml
     ```

1)  **Create the JWT secret:**

     ```powershell
     kubectl apply -f ./kubernetes-manifests
     ```

2)  **Deploy the core services and the conversational agent:**

    ```powershell
    kubectl apply -f ./kubernetes-manifests
    ```


## 5. Verify the Deployment

```powershell
kubectl get pods
```

Check the status of the pods:

```powershell
kubectl get pods
```

It may take a few minutes for all the pods to be in the `Running` state.

## 6. Access the Services
```powershell
kubectl get services
```

Get the external IP addresses of the frontend and conversational-agent services:

```powershell
kubectl get services
```

You will see output similar to this:

```
NAME                     TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)        AGE
accounts-db              ClusterIP      10.0.0.1        <none>          5432/TCP       5m
balancereader            ClusterIP      10.0.0.2        <none>          8080/TCP       5m
contacts                 ClusterIP      10.0.0.3        <none>          8080/TCP       5m
conversational-agent     LoadBalancer   10.0.0.4        <none>        8080:31234/TCP 5m
frontend                 LoadBalancer   10.0.0.5        35.x.x.x        80:32345/TCP   5m
ledger-db                ClusterIP      10.0.0.6        <none>          5432/TCP       5m
transaction-history      ClusterIP      10.0.0.9        <none>          8080/TCP       5m
userservice              ClusterIP      10.0.0.10       <none>          8080/TCP       5m
```

- **Bank of Anthos UI:** Access the application at `http://<EXTERNAL-IP-OF-FRONTEND>`


## 7. Cleanup
```powershell
gcloud container clusters delete bank-of-anthos-autopilot --region=$env:REGION
```

To avoid incurring charges to your GCP account, delete the GKE cluster when you are finished:

```powershell
gcloud container clusters delete bank-of-anthos-autopilot --region=$REGION
```

