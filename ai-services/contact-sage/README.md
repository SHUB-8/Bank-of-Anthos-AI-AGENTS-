# Contact-Sage Service

Contact-Sage is an intelligent FastAPI-based microservice for managing user contacts in the Bank of Anthos platform. It enhances the core contact functionality by providing advanced features like atomic updates, direct deletions, and fuzzy-name resolution.

---

## How It Works

This service uses a hybrid model for contact management:

-   **Proxying**: For adding new contacts and retrieving the full contact list, Contact-Sage proxies requests to the core `contacts` service. This ensures that it respects the canonical source of truth for these fundamental operations.
-   **Direct Database Access**: For operations not supported by the core `contacts` service (updating, deleting) or for advanced features (fuzzy-name resolution), Contact-Sage interacts directly with the `contacts` table in the `accounts-db` PostgreSQL database.

This approach ensures full compatibility with the existing Bank of Anthos platform while enabling a richer set of features.

---

## API Endpoints

All endpoints require a valid JWT `Authorization: Bearer <token>` header, except for the `/health` check.

### 1. Health Check
-   **Endpoint**: `GET /health`
-   **Description**: Checks the operational status of the service.

### 2. Get All Contacts
-   **Endpoint**: `GET /contacts/{account_id}`
-   **Description**: Retrieves all contacts for the authenticated user by proxying the request to the core `contacts` service.

### 3. Add a New Contact
-   **Endpoint**: `POST /contacts/{account_id}`
-   **Description**: Adds a new contact for the authenticated user. First validates that internal accounts exist, then proxies the request to the core `contacts` service.

### 4. Update a Contact
-   **Endpoint**: `PUT /contacts/{account_id}/{contact_label}`
-   **Description**: Atomically updates an existing contact directly in the database.

### 5. Delete a Contact
-   **Endpoint**: `DELETE /contacts/{account_id}/{contact_label}`
-   **Description**: Deletes a contact directly from the database using its label.

### 6. Resolve a Contact Name
-   **Endpoint**: `POST /contacts/resolve`
-   **Description**: Performs a fuzzy-search on the authenticated user's contacts to find the best match for a given recipient name.

---

## Configuration

The service is configured using environment variables. See the `contact-sage.yaml` manifest for deployment details.