# Contact-Sage Service

Contact-Sage is an intelligent FastAPI-based microservice for the Bank of Anthos platform. It acts as a "smart" layer on top of the core `contacts` service, providing advanced features like direct updates, deletions, fuzzy-name resolution, and validation of internal contacts.

---

## How It Works

This service uses a hybrid model for contact management:

-   **Validation & Proxying**: For adding new contacts, `contact-sage` first intercepts the request. If the contact is marked as internal (`is_external: false`), it validates that the account number exists in the `users` table. If valid, it then proxies the request to the core `contacts` service to be saved. This prevents the creation of invalid internal contacts.
-   **Direct Database Access**: For operations not supported by the core `contacts` service (updating, deleting) or for advanced features (fuzzy-name resolution), `contact-sage` interacts directly with the `contacts` table in the `accounts-db` database.

This approach ensures full compatibility with the existing platform while enabling a richer and more secure set of features.

---

## Configuration

The service is configured using the following environment variables:

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `ACCOUNTS_DB_URI` | **Required**. The connection URI for the PostgreSQL `accounts-db`. | `postgresql://user:pass@accounts-db:5432/accounts-db` |
| `JWT_PUBLIC_KEY` | **Required**. The PEM-encoded public key (RS256) used to validate JWTs. | Mounted from a Kubernetes secret. |
| `CONTACTS_SERVICE_URL` | The internal URL of the core `contacts` service for proxying. | `http://contacts:8080` |

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
      "service": "contact-sage"
    }
    ```

### 2. Get All Contacts
-   **Method**: `GET`
-   **Endpoint**: `/contacts/{account_id}`
-   **Description**: Retrieves all contacts for the authenticated user by proxying the request to the core `contacts` service.
-   **Success Response (`200 OK`)**:
    ```json
    [
      {
        "label": "Alice",
        "account_num": "7752843742",
        "routing_num": "883745000",
        "is_external": false
      },
      {
        "label": "External Bank",
        "account_num": "3434344535",
        "routing_num": "354354335",
        "is_external": true
      }
    ]
    ```

### 3. Add a New Contact
-   **Method**: `POST`
-   **Endpoint**: `/contacts/{account_id}`
-   **Description**: Adds a new contact. First validates that internal contacts exist in the `users` table, then proxies the request to the core `contacts` service.
-   **Request Body**:
    ```json
    {
      "label": "Bob",
      "account_num": "9530551227",
      "routing_num": "883745000",
      "is_external": false
    }
    ```
-   **Success Response (`200 OK`)**:
    ```json
    {
      "label": "Bob",
      "account_num": "9530551227",
      "routing_num": "883745000",
      "is_external": false
    }
    ```
-   **Error Response (`404 Not Found`)**:
    ```json
    {
      "detail": "Internal user with this account number not found."
    }
    ```

### 4. Update a Contact
-   **Method**: `PUT`
-   **Endpoint**: `/contacts/{account_id}/{contact_label}`
-   **Description**: Atomically updates an existing contact's details directly in the database. The `{contact_label}` in the URL must be the original name of the contact.
-   **Request Body**:
    ```json
    {
      "label": "Robert",
      "account_num": "9530551227",
      "routing_num": "883745000",
      "is_external": false
    }
    ```
-   **Success Response (`200 OK`)**:
    ```json
    {
      "status": "updated",
      "updated_label": "Robert"
    }
    ```

### 5. Delete a Contact
-   **Method**: `DELETE`
-   **Endpoint**: `/contacts/{account_id}/{contact_label}`
-   **Description**: Deletes a single contact from the database using its label.
-   **Success Response (`200 OK`)**:
    ```json
    {
      "status": "deleted",
      "category": "Robert"
    }
    ```

### 6. Resolve a Contact Name
-   **Method**: `POST`
-   **Endpoint**: `/contacts/resolve`
-   **Description**: Performs a fuzzy search on the user's contacts to find the account number for a given recipient name.
-   **Request Body**:
    ```json
    {
      "recipient": "ali",
      "account_id": "7072261198"
    }
    ```
-   **Success Response (`200 OK`)**:
    ```json
    {
      "status": "success",
      "account_id": "7752843742",
      "contact_name": "Alice",
      "confidence": 0.95
    }
    ```