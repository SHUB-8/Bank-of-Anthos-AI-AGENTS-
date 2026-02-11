# Anomaly-Sage Service

Anomaly-Sage is an intelligent FastAPI-based microservice for the Bank of Anthos platform. It acts as a crucial security layer, analyzing proposed transactions in real-time to detect and classify potential threats like suspicious activity and fraud.

---

## How It Works

This service functions as a synchronous validation step called by an orchestrator before any transaction is executed. Its goal is to provide an **explainable** risk assessment.

-   **Data Gathering**: For each request, it gathers real-time data by calling the core `balancereader` and `transactionhistory` services.
-   **Profile Management**: It maintains user financial profiles in the `ai-meta-db`. It uses **Welford's online algorithm** to maintain running statistics (mean and M2 for variance) in the `user_profiles` table, allowing for O(1) updates without re-scanning history.
-   **Rule-Based Analysis**: It uses a scoring system to evaluate a transaction against several risk factors using Z-scores:
    -   Deviation from the user's normal spending habits (mean/variance).
    -   Account balance depletion risks.
    -   Rapid, repeated transactions in a short time (velocity check).
    -   Transactions to new, unknown recipients.
-   **Explainable AI (XAI)**: The service returns a classification (`normal`, `pending`, `fraud`) along with `anomaly_reasons` for full transparency.
-   **Auditing**: Every analysis is recorded in the `anomaly_logs` table, tracking the status from `pending` through to `confirmed`, `expired`, or `cancelled`.

---

## Configuration

The service is configured using environment variables. See the `anomaly-sage.yaml` manifest for details.

---

## API Endpoint

All endpoints require a valid JWT `Authorization: Bearer <token>`.

### 2. Detect Anomaly
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
      "risk_score": 0.85,
      "status": "pending",
      "reasons": ["High transaction amount", "New recipient"],
      "log_id": "uuid-for-confirmation"
    }
    ```

### 3. Handle Pending Transactions (2FA)
-   **POST /confirm-pending/{log_id}**: Confirm a pending transaction (e.g., after OTP).
-   **POST /cancel-pending/{log_id}**: Cancel/Reject a pending transaction.

### 4. Admin & Support
-   **GET /anomalies/{account_id}**: List anomalies for a user.
-   **POST /update-profile**: Update user profile stats after a successful transaction.
-   **POST /link-transaction**: Link an anomaly log to an executed transaction ID.
-   **POST /expire-pending**: Trigger expiration of old pending transactions.
      "account_id": "7072261198",
      "risk_score": 0.5,
      "status": "suspicious",
      "reasons": [
        "Transaction amount is higher than the user's average spending (2.1x).",
        "Recipient is not in the user's saved contact list."
      ]
    }
    ```