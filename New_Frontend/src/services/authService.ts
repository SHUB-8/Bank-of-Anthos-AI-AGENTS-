/**
 * Authentication Service
 * Handles JWT-based authentication compatible with existing Bank of Anthos userservice.
 */

import { jwtDecode } from 'jwt-decode';
import { mockAuthService } from './mockAuthService';

export interface JWTClaims {
  user: string;
  acct: string;
  name: string;
  exp: number;
  iat: number;
}

export interface AuthResponse {
  token: string;
  user: JWTClaims;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface SignupData {
  username: string;
  password: string;
  'password-repeat': string;
  firstname: string;
  lastname: string;
  birthday: string;
  timezone: string;
  address: string;
  state: string;
  zip: string;
  ssn: string;
}

class AuthService {
  private readonly TOKEN_NAME = 'token';
  private readonly CONSENT_COOKIE = 'consented';

  /**
   * Login user with username and password
   * Uses the same LOGIN_URI endpoint as existing frontend
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    // Use mock authentication in development
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      try {
        const mockResponse = await mockAuthService.mockLogin(credentials.username, credentials.password);
        const token = mockResponse.token;
        
        // Decode token to get claims
        const claims = this.decodeToken(token);
        const maxAge = claims.exp - claims.iat;

        // Store token in cookie
        this.setCookie(this.TOKEN_NAME, token, maxAge);

        return {
          token,
          user: claims,
        };
      } catch (error) {
        console.error('Mock login error:', error);
        throw new Error('Login failed');
      }
    }

    // Real authentication for production
    const loginUri = this.getLoginUri();
    
    try {
      // Build URL with query parameters
      // For relative URLs, we need to construct the query string manually
      const separator = loginUri.includes('?') ? '&' : '?';
      const fullUrl = `${loginUri}${separator}username=${encodeURIComponent(credentials.username)}&password=${encodeURIComponent(credentials.password)}`;

      console.log('Attempting login to:', fullUrl);

      const loginResponse = await fetch(fullUrl, {
        method: 'GET',
        credentials: 'include',
      });

      console.log('Login response status:', loginResponse.status);

      if (!loginResponse.ok) {
        const errorText = await loginResponse.text().catch(() => 'Login failed');
        console.error('Login failed:', errorText);
        throw new Error(errorText || 'Login failed');
      }

      const data = await loginResponse.json();
      console.log('Login response data:', data);
      const token = data.token;

      if (!token) {
        console.error('No token in response:', data);
        throw new Error('No token received');
      }

      // Decode token to get claims (matching decode_token from Flask frontend)
      let claims: JWTClaims;
      try {
        claims = this.decodeToken(token);
        console.log('Decoded claims:', claims);
      } catch (decodeError) {
        console.error('Failed to decode token:', decodeError);
        throw decodeError;
      }
      
      const maxAge = claims.exp - claims.iat;

      // Store token in cookie (matching Flask frontend pattern)
      this.setCookie(this.TOKEN_NAME, token, maxAge);

      return {
        token,
        user: claims,
      };
    } catch (error) {
      console.error('Login error details:', error);
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Login failed');
    }
  }

  /**
   * Signup user with detailed information
   * Uses the same /users endpoint as existing userservice
   */
  async signup(data: SignupData): Promise<void> {
    // Use mock service in development if configured
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      try {
        await mockAuthService.mockSignup(data);
        return;
      } catch (error) {
        console.error('Mock signup error:', error);
        throw new Error('Signup failed');
      }
    }

    const usersUri = this.getUsersUri();
    
    try {
      console.log('Attempting signup to:', usersUri);

      // userservice expects form data (request.form)
      const formData = new URLSearchParams();
      Object.entries(data).forEach(([key, value]) => {
        formData.append(key, value);
      });

      const response = await fetch(usersUri, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
        credentials: 'include',
      });

      console.log('Signup response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Signup failed');
        console.error('Signup failed:', errorText);
        throw new Error(errorText || 'Signup failed');
      }

      // 201 Created indicates success
      return;
    } catch (error) {
      console.error('Signup error details:', error);
      if (error instanceof Error) {
        throw error;
      }
      throw new Error('Signup failed');
    }
  }

  /**
   * Logout user by clearing tokens and redirecting
   * Matches the logout logic from Flask frontend
   */
  logout(): void {
    this.deleteCookie(this.TOKEN_NAME);
    this.deleteCookie(this.CONSENT_COOKIE);
    
    // Clear any stored authentication data
    localStorage.removeItem('authToken');
    sessionStorage.clear();
  }

  /**
   * Get current JWT token from cookie
   * Matches request.cookies.get(app.config['TOKEN_NAME']) pattern
   */
  getToken(): string | null {
    return this.getCookie(this.TOKEN_NAME);
  }

  /**
   * Check if user is authenticated
   * Uses same verify_token logic as Flask frontend
   */
  isAuthenticated(): boolean {
    const token = this.getToken();
    return this.verifyToken(token);
  }

  /**
   * Get user claims from current token
   * Matches decode_token function from Flask frontend
   */
  getUserClaims(): JWTClaims | null {
    const token = this.getToken();
    if (!token || !this.verifyToken(token)) {
      return null;
    }
    return this.decodeToken(token);
  }

  /**
   * Refresh token if needed
   * Placeholder for future implementation
   */
  async refreshToken(): Promise<void> {
    // TODO: Implement token refresh logic if needed
    // For now, redirect to login if token is expired
    if (!this.isAuthenticated()) {
      this.logout();
      window.location.href = '/login';
    }
  }

  /**
   * Decode JWT token without signature verification
   * Matches decode_token function from Flask frontend
   */
  private decodeToken(token: string): JWTClaims {
    try {
      // Decode without verification (matching Flask frontend options={"verify_signature": False})
      return jwtDecode<JWTClaims>(token);
    } catch (error) {
      console.error('Error decoding token:', error);
      throw new Error('Invalid token format');
    }
  }

  /**
   * Verify JWT token
   * Matches verify_token function from Flask frontend
   * Note: Full signature verification would require the public key
   */
  private verifyToken(token: string | null): boolean {
    if (!token) {
      return false;
    }

    try {
      const claims = this.decodeToken(token);
      
      // Check if token is expired
      const now = Math.floor(Date.now() / 1000);
      if (claims.exp < now) {
        console.debug('Token expired');
        return false;
      }

      // Basic validation - in production, should verify signature with public key
      if (!claims.user || !claims.acct || !claims.name) {
        console.debug('Token missing required claims');
        return false;
      }

      return true;
    } catch (error) {
      console.error('Error validating token:', error);
      return false;
    }
  }

  /**
   * Get LOGIN_URI from environment configuration
   * Matches app.config["LOGIN_URI"] pattern from Flask frontend
   */
  private getLoginUri(): string {
    // Check if we're in development mode and use mock API
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      // Return mock login endpoint for development
      return '/api/login';
    }

    // For development with Vite, always use the proxy path
    // This avoids CORS issues by proxying through Vite dev server
    const isDevelopment = import.meta.env.DEV;
    
    if (isDevelopment) {
      // Always use proxy path in development to avoid CORS
      return `/userservice/login`;
    }
    
    // In production (Kubernetes), use service name or configured URL
    const userserviceAddr = import.meta.env.VITE_USERSERVICE_API_ADDR || 'http://userservice:8080';
    return `${userserviceAddr}/login`;
  }

  /**
   * Get USERS_URI for user registration
   */
  private getUsersUri(): string {
    // Check if we're in development mode and use mock API
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return '/api/users';
    }

    const isDevelopment = import.meta.env.DEV;
    
    if (isDevelopment) {
      // Always use proxy path in development to avoid CORS
      return `/userservice/users`;
    }
    
    // In production (Kubernetes), use service name or configured URL
    // Default to relative proxy path
    const userserviceAddr = import.meta.env.VITE_USERSERVICE_API_ADDR || '/api/userservice';
    return `${userserviceAddr}/login`;
  }

  /**
   * Set cookie with expiration
   * Matches resp.set_cookie pattern from Flask frontend
   */
  private setCookie(name: string, value: string, maxAge: number): void {
    const expires = new Date();
    expires.setTime(expires.getTime() + maxAge * 1000);
    
    document.cookie = `${name}=${value}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
  }

  /**
   * Get cookie value
   * Matches request.cookies.get pattern from Flask frontend
   */
  private getCookie(name: string): string | null {
    const nameEQ = name + '=';
    const ca = document.cookie.split(';');
    
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    
    return null;
  }

  /**
   * Delete cookie
   * Matches resp.delete_cookie pattern from Flask frontend
   */
  private deleteCookie(name: string): void {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
  }
}

// Export singleton instance
export const authService = new AuthService();
export default authService;