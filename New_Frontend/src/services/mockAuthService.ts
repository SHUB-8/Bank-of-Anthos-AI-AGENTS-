/**
 * Mock Authentication Service
 * 
 * Provides mock authentication for development environment.
 * Simulates the JWT token structure from the real userservice.
 */

import { JWTClaims } from './authService';

export class MockAuthService {
  /**
   * Mock login that returns a fake JWT token
   */
  async mockLogin(username: string, password: string): Promise<{ token: string }> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // Mock user data based on username
    const mockUsers: Record<string, { name: string; acct: string }> = {
      'testuser': { name: 'Test User', acct: '1011226307' },
      'alice': { name: 'Alice Johnson', acct: '1033623433' },
      'bob': { name: 'Bob Smith', acct: '1055757655' },
      'eve': { name: 'Eve Davis', acct: '1077441377' },
      'charlie': { name: 'Charlie Wilson', acct: '1099115099' },
    };

    const user = mockUsers[username.toLowerCase()];
    if (!user || password !== 'bankofanthos') {
      throw new Error('Invalid credentials');
    }

    // Create mock JWT claims
    const now = Math.floor(Date.now() / 1000);
    const claims: JWTClaims = {
      user: username,
      acct: user.acct,
      name: user.name,
      iat: now,
      exp: now + (24 * 60 * 60), // 24 hours
    };

    // Create a mock JWT token (base64 encoded JSON for simplicity)
    const header = { alg: 'RS256', typ: 'JWT' };
    const headerB64 = btoa(JSON.stringify(header));
    const payloadB64 = btoa(JSON.stringify(claims));
    const signature = 'mock-signature';
    
    const token = `${headerB64}.${payloadB64}.${signature}`;

    return { token };
  }
}

export const mockAuthService = new MockAuthService();