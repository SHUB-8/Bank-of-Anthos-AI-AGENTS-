# Local Development Setup

This guide provides instructions for setting up the Bank of Anthos application for local development, including all microservices and the conversational AI agent.

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

Create and activate a Python virtual environment for each Python service (`frontend`, `userservice`, `contacts`, `conversational_banking_agent`).

For each service:

```sh
cd src/<service_name>
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
pip install -r requirements.txt
```

## 4. Configure environment variables

The `conversational_banking_agent` requires a `GEMINI_API_KEY` to be set in its environment. You can either set this directly in your shell or create a `.env` file in the `src/conversational_banking_agent` directory.

```
GEMINI_API_KEY="your_api_key"
```

## 5. Deploy the application using Skaffold

Skaffold handles the building, pushing, and deploying of the application.

From the root of the project, run:

```sh
skaffold run
```

This will:

1.  Build the container images for each microservice.
2.  Push the images to your local Docker registry.
3.  Deploy the Kubernetes manifests to your local cluster.

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

The conversational AI agent is available at the `/chat` endpoint of the `conversational-agent` service. You can interact with it using a tool like `curl` or Postman.

```sh
# Get the URL of the conversational-agent service
minikube service conversational-agent --url

# Send a request to the chat endpoint
curl -X POST -H "Content-Type: application/json" -d '{"message": "what is my balance?"}' <service_url>/chat
```

## 9. Stopping the application

To stop and clean up the application, run:

```sh
skaffold delete
minikube stop
```
