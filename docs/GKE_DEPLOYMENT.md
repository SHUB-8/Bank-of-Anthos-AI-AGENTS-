# Deploying to Google Kubernetes Engine (GKE)

This guide provides comprehensive instructions for deploying the Bank of Anthos application, including the conversational AI agent, to a Google Kubernetes Engine (GKE) cluster.

## Prerequisites

- A [Google Cloud project](https://cloud.google.com/resource-manager/docs/creating-managing-projects) with billing enabled.
- The [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`) installed and authenticated.
- `kubectl` installed. You can install it via `gcloud`:
  ```sh
  gcloud components install kubectl
  ```
- A shell environment (like bash, zsh, or PowerShell).

## 1. Set up your Google Cloud project

First, set your project ID and preferred region as environment variables:

```sh
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID
gcloud config set compute/region $REGION
```

Enable the necessary APIs:

```sh
gcloud services enable container.googleapis.com
```

## 2. Create a GKE Cluster

You have two options for creating a GKE cluster: Autopilot or Standard. For most use cases, **Autopilot is recommended** as it simplifies cluster management by automating node provisioning and scaling.

### Option 1: GKE Autopilot Cluster (Recommended)

Create an Autopilot cluster:

```sh
gcloud container clusters create-auto bank-of-anthos-cluster \
    --region=$REGION
```

This command creates a regional Autopilot cluster, which is highly available and managed by Google. Autopilot will automatically provision resources for your workloads, so you don't need to worry about node pools or scaling.

### Option 2: GKE Standard Cluster

If you require more control over your cluster's configuration, you can create a Standard cluster. To ensure the cluster has enough resources for the core services and future AI agents, we will create a node pool with a machine type that has sufficient CPU and memory.

Create a Standard GKE cluster:

```sh
gcloud container clusters create bank-of-anthos-cluster \
    --region=$REGION \
    --machine-type=e2-standard-4 \
    --num-nodes=2 \
    --enable-autoscaling --min-nodes=2 --max-nodes=5
```

This command creates a regional Standard cluster with the following configuration:

- `machine-type=e2-standard-4`: Each node will have 4 vCPUs and 16 GB of memory.
- `num-nodes=2`: The cluster will start with 2 nodes per zone.
- `enable-autoscaling --min-nodes=2 --max-nodes=5`: The cluster can automatically scale the number of nodes in each zone between 2 and 5, based on workload demands.

## 3. Get Cluster Credentials

After the cluster is created, get the credentials for `kubectl`:

```sh
gcloud container clusters get-credentials bank-of-anthos-cluster --region=$REGION
```

## 4. Deploy the Application

Now you can deploy the Bank of Anthos application to your GKE cluster.

1.  **Create the JWT secret:**
    ```sh
    kubectl apply -f ./extras/jwt/jwt-secret.yaml
    ```

2.  **Deploy the core services and AI agent microservices:**
    ```sh
    kubectl apply -f ./kubernetes-manifests/ai-meta-db-pvc.yaml
    kubectl apply -f ./kubernetes-manifests/ai-meta-db.yaml
    kubectl apply -f ./kubernetes-manifests/anomaly-sage.yaml
    kubectl apply -f ./kubernetes-manifests/transaction-sage.yaml
    # Apply other manifests as needed
    ```

**Note:** The conversational agent is not present in the current setup. Only the AI agent services (`anomaly-sage`, `transaction-sage`, `ai-meta-db`) are deployed.

## 5. Verify the Deployment

Check the status of the pods:

```sh
kubectl get pods
```

It may take a few minutes for all the pods to be in the `Running` state.

## 6. Access the Application

Get the external IP address of the frontend service:

```sh
kubectl get service frontend
```

Once the `EXTERNAL-IP` is available, you can access the Bank of Anthos application by navigating to `http://<EXTERNAL-IP>` in your web browser.

## 7. Accessing the Conversational AI Agent

The conversational AI agent is exposed through a service. To interact with it, get the service's external IP:

```sh
kubectl get service conversational-agent
```

Then, send a POST request to the `/chat` endpoint:

```sh
curl -X POST -H "Content-Type: application/json" -d '{"message": "what is my balance?"}' http://<AGENT_EXTERNAL_IP>/chat
```

## 8. Cleanup

To avoid incurring charges to your GCP account, delete the GKE cluster when you are finished:

```sh
gcloud container clusters delete bank-of-anthos-cluster --region=$REGION
```
