# Money-Sage Service

Money-Sage is an intelligent FastAPI-based microservice for the Bank of Anthos platform. It provides users with financial insights, budget management tools, and saving tips by analyzing their account data.

---

## How It Works

This service acts as a financial analysis layer:

-   **Direct Database Access**: It connects to a dedicated `ai-meta-db` to manage user-defined budgets and retrieve transaction logs for analysis. It is the owner of all budget-related data.
-   **Proxying**: It securely fetches real-time data like account balances from the core Bank of Anthos microservices (`balancereader`).
-   **Data Analysis**: It processes transaction logs from ai-meta-db (with category and amount information) and compares them against the user's budgets to generate spending summaries, overviews, and actionable saving tips.
-   **AI-Powered Tips**: Uses Google Gemini 1.5 Flash to analyze spending patterns by category and generate personalized, actionable saving recommendations.

---

## Configuration

The service is configured using the following environment variables:

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `AI_META_DB_URI` | **Required**. The connection URI for the PostgreSQL `ai-meta-db`. | `postgresql://user:pass@ai-meta-db:5432/ai-meta-db` |
| `JWT_PUBLIC_KEY` | **Required**. The PEM-encoded public key (RS256) used to validate JWTs. | Mounted from a Kubernetes secret. |
| `GEMINI_API_KEY` | **Optional**. Google Gemini API key for AI-powered tips. Falls back to rule-based tips if not provided. | Mounted from a Kubernetes secret. |
| `BALANCE_READER_URL` | The internal URL of the core `balancereader` service. | `http://balancereader:8080` |

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
-   **Query Parameters**:
    -   `limit` (optional): Maximum number of transactions to return (default: 5)
-   **Description**: Retrieves recent transaction logs from ai-meta-db with category and amount information for spending analysis.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "count": 10,
      "limit": 10,
      "transactions": [
        {
          "id": "uuid-here",
          "transaction_id": 123,
          "account_id": "7072261198",
          "amount": 5500,
          "amount_dollars": 55.00,
          "category": "Dining"
        }
      ]
    }
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
-   **Description**: Generates personalized saving tips using Gemini AI based on transaction_logs spending patterns (category and amount data) and budget comparisons. Falls back to rule-based tips if AI is unavailable.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "account_id": "7072261198",
      "tips": [
        "You've spent $450 on Dining this month (18 transactions, avg $25/transaction). Consider meal prepping 2-3 times per week to reduce this by approximately $150.",
        "Your Groceries spending of $750 is approaching your $800 budget. You're on track - keep monitoring!",
        "Consider setting a budget for Transport ($255 spent with no limit set) to better track this expense category."
      ]
    }
    ```