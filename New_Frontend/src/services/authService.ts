/**
 * Authentication Service
 * 
 * Handles JWT-based authentication compatible with existing Bank of Anthos userservice.
 * Mirrors the authentication patterns from src/frontend/frontend.py
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
      // Construct URL with query parameters (matching Flask frontend pattern)
      const url = new URL(loginUri);
      url.searchParams.append('username', credentials.username);
      url.searchParams.append('password', credentials.password);

      const loginResponse = await fetch(url.toString(), {
        method: 'GET',
        credentials: 'include',
      });

      if (!loginResponse.ok) {
        const errorText = await loginResponse.text().catch(() => 'Login failed');
        throw new Error(errorText || 'Login failed');
      }

      const data = await loginResponse.json();
      const token = data.token;

      if (!token) {
        throw new Error('No token received');
      }

      // Decode token to get claims (matching decode_token from Flask frontend)
      const claims = this.decodeToken(token);
      const maxAge = claims.exp - claims.iat;

      // Store token in cookie (matching Flask frontend pattern)
      this.setCookie(this.TOKEN_NAME, token, maxAge);

      return {
        token,
        user: claims,
      };
    } catch (error) {
      console.error('Login error:', error);
      throw new Error('Login failed');
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

    // For development, use localhost proxy or direct service URL
    const isDevelopment = import.meta.env.DEV;
    const userserviceAddr = import.meta.env.VITE_USERSERVICE_API_ADDR || 'userservice:8080';
    
    if (isDevelopment) {
      // In development, proxy through Vite dev server or use localhost
      return `/api/login`;
    }
    
    // In production (Kubernetes), use service name
    return `http://${userserviceAddr}/login`;
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