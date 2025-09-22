# GKE Turns 10 Hackathon Submission

## Hosted Project URL
[http://34.60.197.255]


---

## Project Description

**Bank of Anthos AI Agents** is a cloud-native banking demo application deployed on Google Kubernetes Engine (GKE) Autopilot. It simulates a modern bank’s payment processing network and now features a Conversational Banking Agent powered by AI.

**Features & Functionality:**
- User authentication, account management, payments, and transaction history via a web UI (Python/Flask).
- Conversational Banking Agent (Python/FastAPI) enables users to interact with their accounts using natural language, supporting multi-currency, contact management, and secure JWT authentication.
- Microservices architecture: frontend, user service, contacts, ledger writer, balance reader, transaction history, and databases.
- AI integration: Gemini API for advanced intent extraction in the conversational agent.
- Secure communication between services using JWTs.
- Kubernetes-native deployment with GKE Autopilot for scalability and reliability.

**Technologies Used:**
- GKE Autopilot (Google Kubernetes Engine)
- Python (Flask, FastAPI)
- Java (Spring Boot)
- PostgreSQL
- Google Artifact Registry
- Gemini API (Google Generative AI)
- JWT Authentication
- Kubernetes ConfigMaps, Secrets, Services, Deployments
- Cloud Build, Cloud Deploy

**Other Data Sources:**
- Demo user and transaction data stored in PostgreSQL databases.
- Currency conversion rates (static or via external API, if configured).

**Findings & Learnings:**
- GKE Autopilot simplifies cluster management and scales resources automatically.
- Integrating AI (Gemini) with microservices enables natural language banking and improves user experience.
- Secure service-to-service communication is critical; JWTs and Kubernetes secrets make this manageable.
- Artifact Registry and Cloud Build streamline container image management and deployment.
- Modular architecture allows easy addition of new features (like the conversational agent).

---

## Public Code Repository
[https://github.com/SHUB-8/Bank-of-Anthos-AI-AGENTS-](https://github.com/SHUB-8/Bank-of-Anthos-AI-AGENTS-)

---

## Architecture Diagram
- See `/docs/img/NewArchitecture.png` for the updated architecture.
- For the updated diagram, add a “Conversational Banking Agent” microservice (Python/FastAPI) connected to frontend, user service, contacts, balance reader, ledger writer, and transaction history. Indicate Gemini API integration and JWT authentication.

---

## How to Run
See [GKE Autopilot Deployment Guide](/docs/GKE_AUTOPILOT_DEPLOYMENT.md) for step-by-step instructions.
