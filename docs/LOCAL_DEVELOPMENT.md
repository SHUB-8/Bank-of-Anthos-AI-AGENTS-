
# Local Development Setup (Minikube)

This guide provides step-by-step instructions for running the Bank of Anthos application locally on Minikube, including all microservices and the conversational AI agent.

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


## 1. Start Minikube

Start your local Kubernetes cluster:
```sh
minikube start --memory=4096 --cpus=4
```


## 2. Build Microservice Images

Build Java services:
```sh
mvn clean install -f pom.xml
```

Build Python services (frontend, userservice, contacts, conversational_banking_agent):
```sh
# Example for frontend
cd src/frontend
docker build -t frontend:latest .
# Repeat for other Python services
```


## 3. Configure Environment Variables & Secrets

Set up the Gemini API key for the conversational agent:
```sh
kubectl create secret generic gemini-api-key --from-literal=api-key=YOUR_GEMINI_API_KEY
```


## 4. Deploy the Application to Minikube

Apply the JWT secret:
```sh
kubectl apply -f ./extras/jwt/jwt-secret.yaml
```

Apply all Kubernetes manifests:
```sh
kubectl apply -f ./kubernetes-manifests
```


## 5. Access the Application

Once all pods are running, expose and access the frontend:
```sh
minikube service frontend
```
This will open the Bank of Anthos web UI in your browser.


## 6. Accessing the Conversational AI Agent

Get the URL of the conversational-agent service:
```sh
minikube service conversational-agent --url
```
Interact with the `/chat` endpoint using curl or Postman:
```sh
curl -X POST -H "Content-Type: application/json" -d '{"message": "what is my balance?"}' <service_url>/chat
```


## 7. Stopping the Application

To stop and clean up:
```sh
kubectl delete -f ./kubernetes-manifests
kubectl delete secret gemini-api-key
minikube stop
```
