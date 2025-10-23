/**
 * API Client Utility
 * 
 * Provides authenticated HTTP client for making API calls to backend services.
 * Automatically includes JWT tokens and handles common error scenarios.
 */

import authService from '../services/authService';

export interface ApiResponse<T = any> {
  data: T;
  status: number;
  statusText: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public service: string,
    public response?: Response
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class AuthenticationError extends ApiError {
  constructor(message: string = 'Authentication required') {
    super(message, 401, 'auth');
    this.name = 'AuthenticationError';
  }
}

export class ServiceUnavailableError extends ApiError {
  constructor(service: string) {
    super(`${service} is temporarily unavailable`, 503, service);
    this.name = 'ServiceUnavailableError';
  }
}

class ApiClient {
  private readonly timeout: number;

  constructor() {
    this.timeout = parseInt(import.meta.env.VITE_BACKEND_TIMEOUT || '4000');
  }

  /**
   * Make authenticated API request
   * Automatically includes JWT token in Authorization header
   */
  async request<T = any>(
    url: string,
    options: RequestInit = {},
    serviceName: string = 'api'
  ): Promise<ApiResponse<T>> {
    // Get JWT token
    const token = authService.getToken();
    
    // Prepare headers
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    // Add Authorization header if token exists
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Create AbortController for timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
        credentials: 'include', // Include cookies for session management
      });

      clearTimeout(timeoutId);

      // Handle authentication errors
      if (response.status === 401) {
        // Token might be expired, logout user
        authService.logout();
        throw new AuthenticationError('Session expired. Please log in again.');
      }

      // Handle service unavailable
      if (response.status === 503) {
        throw new ServiceUnavailableError(serviceName);
      }

      // Handle other HTTP errors
      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error');
        throw new ApiError(
          errorText || `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          serviceName,
          response
        );
      }

      // Parse response
      let data: T;
      const contentType = response.headers.get('content-type');
      
      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = (await response.text()) as unknown as T;
      }

      return {
        data,
        status: response.status,
        statusText: response.statusText,
      };

    } catch (error) {
      clearTimeout(timeoutId);

      // Handle timeout
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(`Request timeout after ${this.timeout}ms`, 408, serviceName);
      }

      // Re-throw our custom errors
      if (error instanceof ApiError) {
        throw error;
      }

      // Handle network errors
      throw new ApiError(
        `Network error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        0,
        serviceName
      );
    }
  }

  /**
   * GET request
   */
  async get<T = any>(url: string, serviceName?: string): Promise<ApiResponse<T>> {
    return this.request<T>(url, { method: 'GET' }, serviceName);
  }

  /**
   * POST request
   */
  async post<T = any>(
    url: string,
    data?: any,
    serviceName?: string
  ): Promise<ApiResponse<T>> {
    return this.request<T>(
      url,
      {
        method: 'POST',
        body: data ? JSON.stringify(data) : undefined,
      },
      serviceName
    );
  }

  /**
   * PUT request
   */
  async put<T = any>(
    url: string,
    data?: any,
    serviceName?: string
  ): Promise<ApiResponse<T>> {
    return this.request<T>(
      url,
      {
        method: 'PUT',
        body: data ? JSON.stringify(data) : undefined,
      },
      serviceName
    );
  }

  /**
   * DELETE request
   */
  async delete<T = any>(url: string, serviceName?: string): Promise<ApiResponse<T>> {
    return this.request<T>(url, { method: 'DELETE' }, serviceName);
  }

  /**
   * Make multiple parallel requests
   * Similar to TracedThreadPoolExecutor pattern from Flask frontend
   */
  async parallel<T = any>(
    requests: Array<{
      url: string;
      options?: RequestInit;
      serviceName?: string;
    }>
  ): Promise<Array<ApiResponse<T> | Error>> {
    const promises = requests.map(({ url, options, serviceName }) =>
      this.request<T>(url, options, serviceName).catch((error) => error)
    );

    return Promise.all(promises);
  }

  /**
   * Get service URL from environment configuration
   */
  getServiceUrl(serviceName: string): string {
    const serviceMap: Record<string, string> = {
      userservice: import.meta.env.VITE_USERSERVICE_API_ADDR || 'userservice:8080',
      balances: import.meta.env.VITE_BALANCES_API_ADDR || 'balancereader:8080',
      history: import.meta.env.VITE_HISTORY_API_ADDR || 'transactionhistory:8080',
      contacts: import.meta.env.VITE_CONTACTS_API_ADDR || 'contacts:8080',
      transactions: import.meta.env.VITE_TRANSACTIONS_API_ADDR || 'ledgerwriter:8080',
      orchestrator: import.meta.env.VITE_ORCHESTRATOR_URL || 'http://orchestrator:8082',
      'contact-sage': import.meta.env.VITE_CONTACT_SAGE_URL || 'http://contact-sage:8083',
      'money-sage': import.meta.env.VITE_MONEY_SAGE_URL || 'http://money-sage:8084',
      'anomaly-sage': import.meta.env.VITE_ANOMALY_SAGE_URL || 'http://anomaly-sage:8085',
      'transaction-sage': import.meta.env.VITE_TRANSACTION_SAGE_URL || 'http://transaction-sage:8086',
    };

    const serviceAddr = serviceMap[serviceName];
    if (!serviceAddr) {
      throw new Error(`Unknown service: ${serviceName}`);
    }

    // Add http:// prefix if not present (for non-AI services)
    if (!serviceAddr.startsWith('http://') && !serviceAddr.startsWith('https://')) {
      return `http://${serviceAddr}`;
    }

    return serviceAddr;
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;