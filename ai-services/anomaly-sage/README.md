# Anomaly-Sage Service

Anomaly-Sage is an intelligent FastAPI-based microservice for the Bank of Anthos platform. It acts as a crucial security layer, analyzing proposed transactions in real-time to detect and classify potential threats like suspicious activity and fraud.

---

## How It Works

This service functions as a synchronous validation step called by an orchestrator before any transaction is executed. Its goal is to provide an **explainable** risk assessment.

-   **Data Gathering**: For each request, it gathers real-time data by calling the core `balancereader` and `transactionhistory` services.
-   **Profile Management**: It maintains its own user financial profiles in the `ai-meta-db`. It stores calculated statistics like average transaction amount and standard deviation in the `user_profiles` table to avoid costly recalculations.
-   **Rule-Based Analysis**: It uses a scoring system to evaluate a transaction against several risk factors:
    -   Deviation from the user's normal spending habits.
    -   Potential for account balance depletion.
    -   Rapid, repeated transactions in a short time.
    -   Transactions to new, unknown recipients.
-   **Explainable AI (XAI)**: The service returns not only a classification (`normal`, `suspicious`, `fraud`) but also a clear, human-readable list of all the reasons that contributed to its decision.
-   **Auditing**: Every analysis is recorded in the `anomaly_logs` table for full auditability.

---

## Configuration

The service is configured using environment variables. See the `anomaly-sage.yaml` manifest for details.

---

## API Endpoint

All endpoints require a valid JWT `Authorization: Bearer <token>`.

### Detect Anomaly
-   **Method**: `POST`
-   **Endpoint**: `/v1/detect-anomaly`
-   **Description**: Analyzes a proposed transaction and returns a risk assessment.

-   **Request Body Format**:
    ```json
    {
      "account_id": "7072261198",
      "amount_cents": 50000,
      "recipient_id": "9530551227",
      "is_external": false
    }
    ```

-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "risk_score": 0.5,
      "status": "suspicious",
      "reasons": [
        "Transaction amount is higher than the user's average spending (2.1x).",
        "Recipient is not in the user's saved contact list."
      ]
    }
    ```