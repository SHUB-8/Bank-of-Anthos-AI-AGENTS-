# Deploying the Orchestrator to Minikube

This guide provides step-by-step instructions to build, configure, and deploy the Orchestrator service to your local Minikube cluster.

### Prerequisites

- `minikube` is installed and running.
- `docker` is installed.
- `kubectl` is installed and configured to point to your Minikube cluster.

### Step 1: Build the Docker Image

First, you need to build the `orchestrator-service` Docker image within Minikube's own Docker environment. This makes the image directly available to the cluster without needing a separate registry.

```bash
# Point your shell's Docker daemon to the one inside Minikube
# For Linux/macOS/WSL:
eval $(minikube -p minikube docker-env)
# For PowerShell:
# minikube -p minikube docker-env | Invoke-Expression

# Navigate to the orchestrator directory
cd /path/to/bank-of-anthos/ai-services/orchestrator

# Build the Docker image. The tag `orchestrator-service:latest` matches the deployment manifest.
docker build -t orchestrator-service:latest .

# (Optional) To revert your shell to the host Docker daemon, run:
# eval $(minikube docker-env -u)
```

### Step 2: Create the Kubernetes Secret

Kubernetes requires that sensitive data like API keys and database URLs be base64 encoded. The manifest I created references a secret named `orchestrator-secret`. You must create this manually.

1.  **Encode your secrets:** Run the following commands and save the output for each value.

    ```bash
    # For your Gemini API Key
    echo -n 'your-real-gemini-api-key' | base64

    # For your Database URL
    echo -n 'postgresql+asyncpg://user:password@ai-meta-db:5432/ai_meta_db' | base64

    # For your JWT Public Key (ensure it's a single line of base64 text)
    echo -n 'YOUR_BASE64_ENCODED_PUBLIC_KEY' | base64
    ```

2.  **Create the secret:** Use `kubectl` to create the secret with the encoded values you just generated.

    ```bash
    kubectl create secret generic orchestrator-secret \
      --from-literal=GADK_API_KEY='<paste-encoded-gemini-key-here>' \
      --from-literal=JWT_PUBLIC_KEY='<paste-doubly-encoded-public-key-here>' \
      --from-literal=DATABASE_URL='<paste-encoded-db-url-here>'
    ```

### Step 3: Apply the Manifests

Now you can apply the `k8s-manifests.yaml` file. This will create the ConfigMap, Deployment, and Service for the Orchestrator.

```bash
# From the orchestrator directory
kubectl apply -f k8s-manifests.yaml
```

### Step 4: Verify the Deployment

Check that the pod is running correctly.

```bash
# See the deployment status
kubectl get deployment orchestrator-deployment

# See the running pod
kubectl get pods -l app=orchestrator

# Check the logs of the pod to ensure it started without errors
# (replace <pod-name> with the actual name from the command above)
kubectl logs <pod-name>
```

### Step 5: Accessing the Service

- **From inside the cluster:** Other pods can now access the orchestrator at the DNS name `http://orchestrator-service:8000`.

- **From your local machine:** To test the service directly, you can use port-forwarding.

  ```bash
  # Forward a local port (e.g., 8080) to the service's port (8000)
  kubectl port-forward svc/orchestrator-service 8080:8000
  ```
  You can now send requests to `http://localhost:8080/v1/query` from your machine.
