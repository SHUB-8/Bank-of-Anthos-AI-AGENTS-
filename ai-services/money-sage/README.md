# Money-Sage Service

Money-Sage is an intelligent FastAPI-based microservice for the Bank of Anthos platform. It provides users with financial insights, budget management tools, and saving tips by analyzing their account data.

---

## How It Works

This service acts as a financial analysis layer:

-   **Direct Database Access**: It connects to a dedicated `ai-meta-db` to manage user-defined budgets. It is the owner of all budget-related data.
-   **Proxying**: It securely fetches real-time data like transaction history and account balances from the core Bank of Anthos microservices (`transactionhistory` and `balancereader`).
-   **Data Analysis**: It processes transaction data from the core services and compares it against the user's budgets to generate spending summaries, overviews, and actionable saving tips.

---

## Configuration

The service is configured using the following environment variables:

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `AI_META_DB_URI` | **Required**. The connection URI for the PostgreSQL `ai-meta-db`. | `postgresql://user:pass@ai-meta-db:5432/ai-meta-db` |
| `JWT_PUBLIC_KEY` | **Required**. The PEM-encoded public key (RS256) used to validate JWTs. | Mounted from a Kubernetes secret. |
| `BALANCE_READER_URL` | The internal URL of the core `balancereader` service. | `http://balancereader:8080` |
| `TRANSACTION_HISTORY_URL`| The internal URL of the core `transactionhistory` service. | `http://transactionhistory:8080` |

---

## API Endpoints

All endpoints require a valid JWT `Authorization: Bearer <token>` header, except for `/health`.

### 1. Health Check
-   **Method**: `GET`
-   **Endpoint**: `/health`
-   **Description**: Checks the operational status of the service.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "status": "healthy",
      "service": "money-sage"
    }
    ```

### 2. Get Balance
-   **Method**: `GET`
-   **Endpoint**: `/balance/{account_id}`
-   **Description**: Retrieves the current account balance by proxying to the `balancereader` service.
-   **Success Response (`200 OK`)**:
    ```json
    137205629
    ```

### 3. Get Transactions
-   **Method**: `GET`
-   **Endpoint**: `/transactions/{account_id}`
-   **Description**: Retrieves a list of recent transactions by proxying to the `transactionhistory` service.
-   **Success Response (`200 OK`)**:
    ```json
    [
      {
        "transaction_id": "abc-123",
        "amount": -55.75,
        "timestamp": "2025-09-20T18:34:25.980Z",
        "details": {
          "memo": "Dining",
          "to_account_num": "..."
        }
      }
    ]
    ```

### 4. Budget Management (CRUD)

#### Create a New Budget
-   **Method**: `POST`
-   **Endpoint**: `/budgets/{account_id}`
-   **Description**: Creates a new budget for a given category and time period.
-   **Request Body**:
    ```json
    {
      "category": "Dining",
      "budget_limit": 500,
      "period_start": "2025-09-01",
      "period_end": "2025-09-30"
    }
    ```
-   **Success Response (`200 OK`)**:
    ```json
    {
      "id": "2f36b630-15f8-459f-873d-6c89e88c7929",
      "account_id": "7072261198",
      "category": "Dining",
      "budget_limit": 500,
      "period_start": "2025-09-01",
      "period_end": "2025-09-30"
    }
    ```

#### Get All Budgets
-   **Method**: `GET`
-   **Endpoint**: `/budgets/{account_id}`
-   **Description**: Lists all budgets for the account.
-   **Success Response (`200 OK`)**: An array of budget objects, similar to the response for creating a budget.

#### Update a Budget
-   **Method**: `PUT`
-   **Endpoint**: `/budgets/{account_id}/{category}`
-   **Description**: Updates a budget's limit and/or period. Any field not included will be unchanged.
-   **Request Body**:
    ```json
    {
      "budget_limit": 550,
      "period_end": "2025-10-15"
    }
    ```
-   **Success Response (`200 OK`)**: The full, updated budget object.

#### Delete a Budget
-   **Method**: `DELETE`
-   **Endpoint**: `/budgets/{account_id}/{category}`
-   **Description**: Deletes a budget for a specific category.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "status": "deleted",
      "category": "Dining"
    }
    ```

### 5. Insights & Analysis

#### Get Spending Summary
-   **Method**: `GET`
-   **Endpoint**: `/summary/{account_id}`
-   **Description**: Calculates total spending per category for the current period using data from the `transaction_logs` table.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "spending_by_category": {
        "Dining": 450.00,
        "Groceries": 750.00,
        "Shopping": 280.00
      }
    }
    ```

#### Get Budget Overview
-   **Method**: `GET`
-   **Endpoint**: `/overview/{account_id}`
-   **Description**: Compares current spending (from `budget_usage`) against created budgets.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "overview": {
        "Groceries": {
          "limit": 800,
          "spent": 750.00,
          "remaining": 50.00,
          "status": "at_risk"
        },
        "Transport": {
          "limit": 250,
          "spent": 255.00,
          "remaining": -5.00,
          "status": "over_budget"
        }
      }
    }
    ```

#### Get Saving Tips
-   **Method**: `GET`
-   **Endpoint**: `/tips/{account_id}`
-   **Description**: Generates simple, rule-based saving tips based on the budget overview.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "tips": [
        "You're close to your budget limit for Groceries ($750.00/$800.00). Be mindful of your next purchases.",
        "You've gone over your budget for Transport. It's a good time to review your spending in this area."
      ]
    }
    ```