/**
 * AI Agents API Service
 * 
 * Integrates with the Bank of Anthos AI Services (Orchestrator, Money-Sage, Contact-Sage, etc.)
 * All requests go through the Orchestrator's chat interface for AI-powered interactions,
 * or directly to specific sage services for direct CRUD operations.
 */

import authService from '../services/authService';

// Get base URLs - default to relative proxy paths for K8s Nginx deployment
const getOrchestratorUrl = () => {
  return import.meta.env.VITE_ORCHESTRATOR_URL || '/api/orchestrator';
};

const getMoneySageUrl = () => {
  return import.meta.env.VITE_MONEY_SAGE_URL || '/api/money-sage';
};

const getContactSageUrl = () => {
  return import.meta.env.VITE_CONTACT_SAGE_URL || '/api/contact-sage';
};

const getAnomalySageUrl = () => {
  return import.meta.env.VITE_ANOMALY_SAGE_URL || '/api/anomaly-sage';
};

const getTransactionSageUrl = () => {
  return import.meta.env.VITE_TRANSACTION_SAGE_URL || '/api/transaction-sage';
};

// Helper to get auth headers
const getAuthHeaders = () => {
  const token = authService.getToken();
  console.log('Auth token present:', !!token);
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

// Session ID management for orchestrator conversations
const getOrCreateSessionId = () => {
  let sessionId = localStorage.getItem('boa_session_id');
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem('boa_session_id', sessionId);
  }
  return sessionId;
};

/**
 * Orchestrator API - Main AI Chat Interface
 * All AI-powered interactions go through here
 */
export const orchestratorAPI = {
  /**
   * Send a chat message to the AI orchestrator
   * @param {string} message - User's message
   * @param {Array} _conversationHistory - Previous messages for context (optional, reserved for future use)
   * @returns {Promise<{response: string, session_id: string}>}
   */
  async chat(message, _conversationHistory = []) {
    const url = `${getOrchestratorUrl()}/chat`;
    const sessionId = getOrCreateSessionId();

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          query: message
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Chat request failed');
      }

      const data = await response.json();
      return {
        response: data.response,
        session_id: data.session_id,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('Chat API Error:', error);
      throw error;
    }
  },

  /**
   * Stream chat response from orchestrator (SSE)
   * @param {string} message - User's message
   * @param {Function} onChunk - Callback for each chunk
   * @param {Function} onComplete - Callback when stream ends
   */
  async streamChat(message, onChunk, onComplete) {
    const url = `${getOrchestratorUrl()}/chat/stream`;
    const sessionId = getOrCreateSessionId();

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          query: message
        })
      });

      if (!response.ok) {
        throw new Error('Stream request failed');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6);
            if (chunk === '[DONE]') {
              onComplete?.();
            } else {
              onChunk?.(chunk);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream Chat Error:', error);
      throw error;
    }
  },

  /**
   * Get notifications from orchestrator
   */
  async getNotifications(includeRead = false) {
    const url = `${getOrchestratorUrl()}/notifications?include_read=${includeRead}`;
    try {
      const response = await fetch(url, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to fetch notifications');
      const data = await response.json();
      return data.notifications || [];
    } catch (error) {
      console.error('getNotifications error:', error);
      return [];
    }
  },

  /**
   * Mark notifications as read
   */
  async markNotificationsRead(notificationIds) {
    const url = `${getOrchestratorUrl()}/notifications/read`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify(notificationIds)
      });
      return response.ok;
    } catch (error) {
      console.error('markNotificationsRead error:', error);
      return false;
    }
  },

  /**
   * Verify OTP for a pending transaction
   */
  async verifyOtp(confirmationId, otp) {
    const url = `${getOrchestratorUrl()}/verify-otp`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ confirmation_id: confirmationId, otp: otp })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'OTP verification failed');
      return data;
    } catch (error) {
      console.error('verifyOtp error:', error);
      throw error;
    }
  },

  /**
   * Get or create a stable session ID for the user
   */
  async getSessionId() {
    const url = `${getOrchestratorUrl()}/session-id`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (response.ok) {
        const data = await response.json();
        if (data.session_id) {
          localStorage.setItem('boa_session_id', data.session_id);
          return data.session_id;
        }
      }
    } catch (error) {
      console.error('Session ID fetch error:', error);
    }
    
    return getOrCreateSessionId();
  },

  /**
   * Get list of previous chat sessions
   */
  async getUserSessions() {
    const url = `${getOrchestratorUrl()}/sessions`;
    try {
      const response = await fetch(url, {
        headers: getAuthHeaders()
      });
      if (!response.ok) throw new Error('Failed to fetch sessions');
      const data = await response.json();
      return data.sessions || [];
    } catch (error) {
      console.error('getUserSessions error:', error);
      return [];
    }
  },

  /**
   * Start a new chat session
   */
  async startNewSession() {
    // Generate new ID locally or fetch from server
    // We'll use the server endpoint to respect the architecture
    const url = `${getOrchestratorUrl()}/session-id`;
    try {
      const response = await fetch(url, { headers: getAuthHeaders() });
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('boa_session_id', data.session_id);
        return data.session_id;
      }
    } catch (e) { console.error(e); }
    
    // Fallback
    const newId = crypto.randomUUID();
    localStorage.setItem('boa_session_id', newId);
    return newId;
  },

  /**
   * Check orchestrator health
   */
  async healthCheck() {
    const url = `${getOrchestratorUrl()}/health`;
    
    try {
      const response = await fetch(url);
      return response.ok;
    } catch (error) {
      console.error('Health check error:', error);
      return false;
    }
  },

  /**
   * Get messages for a specific session
   */
  async getSessionMessages(sessionId) {
    const url = `${getOrchestratorUrl()}/sessions/${sessionId}/messages`;
    try {
      const response = await fetch(url, { headers: getAuthHeaders() });
      if (!response.ok) throw new Error('Failed to fetch messages');
      const data = await response.json();
      return data.messages || [];
    } catch (error) {
      console.error('getSessionMessages error:', error);
      return [];
    }
  },

  /**
   * Delete a session
   */
  async deleteSession(sessionId) {
    const url = `${getOrchestratorUrl()}/sessions/${sessionId}`;
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      return response.ok;
    } catch (error) {
      console.error('deleteSession error:', error);
      return false;
    }
  }
};

/**
 * Contact-Sage API - Direct Contact Management
 * Use for CRUD operations on contacts when not going through chat
 */
export const contactSageAPI = {
  /**
   * Get all contacts for the current user
   */
  async getContacts() {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getContactSageUrl()}/contacts/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch contacts');
      }

      const data = await response.json();
      // Transform to frontend format
      return (data.contacts || data || []).map(contact => ({
        id: contact.label || contact.account_num,
        name: contact.label,
        accountNumber: contact.account_num,
        routingNumber: contact.routing_num,
        isExternal: contact.is_external || false,
        email: contact.email || '',
        phone: contact.phone || ''
      }));
    } catch (error) {
      console.error('Contacts fetch error:', error);
      throw error;
    }
  },

  /**
   * Create a new contact
   */
  async createContact(contactData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    // Validate and sanitize inputs
    const accountNum = (contactData.accountNumber || '').trim();
    const isExternal = contactData.isExternal || false;
    
    // For internal contacts, use local routing. For external, require a different routing.
    let routingNum = (contactData.routingNumber || '').trim();
    
    if (!isExternal) {
      // Internal contacts use Bank of Anthos routing
      routingNum = routingNum || '883745000';
    }
    
    // Account number must be exactly 10 digits
    if (!/^\d{10}$/.test(accountNum)) {
      throw new Error('Account number must be exactly 10 digits');
    }
    
    // Routing number must be exactly 9 digits
    if (!/^\d{9}$/.test(routingNum)) {
      throw new Error('Routing number must be exactly 9 digits');
    }

    const url = `${getContactSageUrl()}/contacts/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          label: contactData.name.trim(),
          account_num: accountNum,
          routing_num: routingNum,
          is_external: isExternal
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create contact');
      }

      const data = await response.json();
      return {
        id: data.label || contactData.name,
        name: data.label || contactData.name,
        accountNumber: data.account_num || contactData.accountNumber,
        routingNumber: data.routing_num || contactData.routingNumber,
        isExternal: data.is_external || contactData.isExternal
      };
    } catch (error) {
      console.error('Contact creation error:', error);
      throw error;
    }
  },

  /**
   * Update an existing contact
   */
  async updateContact(contactLabel, contactData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    // Validate and sanitize inputs
    const accountNum = (contactData.accountNumber || '').trim();
    const routingNum = (contactData.routingNumber || '').trim() || '883745000';
    
    // Account number must be exactly 10 digits
    if (!/^\d{10}$/.test(accountNum)) {
      throw new Error('Account number must be exactly 10 digits');
    }
    
    // Routing number must be exactly 9 digits
    if (!/^\d{9}$/.test(routingNum)) {
      throw new Error('Routing number must be exactly 9 digits');
    }

    const url = `${getContactSageUrl()}/contacts/${claims.acct}/${encodeURIComponent(contactLabel)}`;
    
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          label: contactData.name.trim(),
          account_num: accountNum,
          routing_num: routingNum,
          is_external: contactData.isExternal || false
        })
      });

      if (!response.ok) {
        throw new Error('Failed to update contact');
      }

      return await response.json();
    } catch (error) {
      console.error('Contact update error:', error);
      throw error;
    }
  },

  /**
   * Delete a contact
   */
  async deleteContact(contactLabel) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getContactSageUrl()}/contacts/${claims.acct}/${encodeURIComponent(contactLabel)}`;
    
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to delete contact');
      }

      return true;
    } catch (error) {
      console.error('Contact deletion error:', error);
      throw error;
    }
  },

  /**
   * Fuzzy search for contacts using the resolve endpoint
   * Falls back to local filtering if the API call fails
   */
  async fuzzySearch(query, allContacts = []) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getContactSageUrl()}/contacts/resolve`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          recipient: query,
          account_id: claims.acct
        })
      });

      if (!response.ok) {
        // Fall back to local filtering
        return this.localFilter(query, allContacts);
      }

      const data = await response.json();
      if (data.status === 'success' && data.contact_name) {
        return [{
          id: data.contact_name,
          name: data.contact_name,
          accountNumber: data.account_id,
          confidence: data.confidence,
          isExternal: false
        }];
      }
      // No match from API, try local filtering
      return this.localFilter(query, allContacts);
    } catch (error) {
      console.error('Fuzzy search error:', error);
      // Fall back to local filtering
      return this.localFilter(query, allContacts);
    }
  },

  /**
   * Local contact filtering as a fallback
   */
  localFilter(query, contacts) {
    if (!query || !contacts.length) return contacts;
    const lowerQuery = query.toLowerCase();
    return contacts.filter(contact =>
      (contact.name && contact.name.toLowerCase().includes(lowerQuery)) ||
      (contact.accountNumber && contact.accountNumber.includes(query)) ||
      (contact.email && contact.email.toLowerCase().includes(lowerQuery))
    );
  }
};

/**
 * Money-Sage API - Budget and Financial Data
 */
export const moneySageAPI = {
  /**
   * Get all budgets for the current user
   */
  async getBudgets() {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/budgets/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch budgets');
      }

      const data = await response.json();
      // Transform to frontend format with colors
      // Note: Backend now returns dollars
      const colors = ['#10B981', '#F59E0B', '#EF4444', '#3B82F6', '#8B5CF6', '#06B6D4'];
      return (data || []).map((budget, index) => ({
        id: budget.id,
        name: budget.category,
        category: budget.category,
        limit: budget.budget_limit, 
        spent: (budget.spent || 0), 
        color: colors[index % colors.length],
        periodStart: budget.period_start,
        periodEnd: budget.period_end
      }));
    } catch (error) {
      console.error('Budgets fetch error:', error);
      throw error;
    }
  },

  /**
   * Create a new budget
   */
  async createBudget(budgetData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/budgets/${claims.acct}`;
    
    // Calculate period dates (default to current month)
    const now = new Date();
    const periodStart = budgetData.periodStart || new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
    const periodEnd = budgetData.periodEnd || new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

    try {
      // Backend expects dollars now
      
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          category: budgetData.name || budgetData.category,
          budget_limit: budgetData.limit,
          period_start: periodStart,
          period_end: periodEnd
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create budget');
      }

      const data = await response.json();
      return {
        id: data.id,
        name: data.category,
        category: data.category,
        limit: data.budget_limit,
        spent: 0,
        color: budgetData.color || '#3B82F6',
        periodStart: data.period_start,
        periodEnd: data.period_end
      };
    } catch (error) {
      console.error('Budget creation error:', error);
      throw error;
    }
  },

  /**
   * Update an existing budget
   */
  async updateBudget(budgetId, budgetData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    // Use budgetId (original category) for the URL to ensure we find the record
    const category = budgetId;
    const url = `${getMoneySageUrl()}/budgets/${claims.acct}/${encodeURIComponent(category)}`;
    
    try {
      // Backend expects dollars now
      const limit = budgetData.limit;
      
      const response = await fetch(url, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          category: budgetData.name || budgetData.category,
          budget_limit: limit,
          period_start: budgetData.periodStart,
          period_end: budgetData.periodEnd
        })
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to update budget');
      }

      const data = await response.json();
      return {
        id: data.id,
        name: data.category,
        category: data.category,
        limit: data.budget_limit, 
        spent: (data.spent || 0),
        color: budgetData.color || '#3B82F6',
        periodStart: data.period_start,
        periodEnd: data.period_end
      };
    } catch (error) {
      console.error('Budget update error:', error);
      throw error;
    }
  },

  /**
   * Delete a budget
   */
  async deleteBudget(budgetId, category) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/budgets/${claims.acct}/${encodeURIComponent(category || budgetId)}`;
    
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to delete budget');
      }

      return true;
    } catch (error) {
      console.error('Budget deletion error:', error);
      throw error;
    }
  },

  /**
   * Get budget overview with spending summary
   */
  async getOverview() {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/overview/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch overview');
      }

      const data = await response.json();
      
      // Calculate totals from overview
      const overview = data.overview || {};
      let totalBudget = 0;
      let totalSpent = 0;
      
      Object.values(overview).forEach(item => {
        totalBudget += item.limit || 0;
        totalSpent += item.spent || 0;
      });

      return {
        totalBudget,
        totalSpent,
        overview,
        message: data.message
      };
    } catch (error) {
      console.error('Overview fetch error:', error);
      throw error;
    }
  },

  /**
   * Get AI-powered saving tips
   */
  async getTips() {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/tips/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch tips');
      }

      const data = await response.json();
      return data.tips || [];
    } catch (error) {
      console.error('Tips fetch error:', error);
      throw error;
    }
  },

  /**
   * Get account balance
   */
  async getBalance() {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const url = `${getMoneySageUrl()}/balance/${claims.acct}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch balance');
      }

      const data = await response.json();
      return data.balance;
    } catch (error) {
      console.error('Balance fetch error:', error);
      throw error;
    }
  }
};

/**
 * Transaction API - Transaction History and Monitoring
 */
export const transactionAPI = {
  /**
   * Get transactions with optional filters
   */
  async getTransactions(limit = 20, options = {}) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const params = new URLSearchParams({
      limit: limit.toString(),
      order: options.order || 'desc'
    });
    
    if (options.transactionType) {
      params.append('transaction_type', options.transactionType);
    }
    if (options.anomalyStatus) {
      params.append('anomaly_status', options.anomalyStatus);
    }

    const url = `${getMoneySageUrl()}/transactions/${claims.acct}?${params}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch transactions');
      }

      const data = await response.json();
      // Transform to frontend format
      return (data.transactions || []).map(txn => ({
        id: txn.id || txn.transaction_id,
        date: txn.created_at,
        amount: txn.transaction_type === 'debit' 
          ? -(txn.amount_dollars || txn.amount / 100) 
          : (txn.amount_dollars || txn.amount / 100),
        description: txn.description || 'Transaction',
        category: txn.category || 'Other',
        status: txn.anomaly_status || 'normal',
        riskScore: txn.risk_score,
        anomalyReasons: Array.isArray(txn.anomaly_reasons) ? txn.anomaly_reasons : [],
        recipientAccount: txn.receiver_account_id,
        transactionType: txn.transaction_type
      }));
    } catch (error) {
      console.error('Transactions fetch error:', error);
      throw error;
    }
  },

  /**
   * Get total transaction count
   */
  async getTransactionCount(options = {}) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const params = new URLSearchParams();
    if (options.transactionType) {
      params.append('transaction_type', options.transactionType);
    }
    if (options.anomalyStatus) {
      params.append('anomaly_status', options.anomalyStatus);
    }

    const url = `${getMoneySageUrl()}/transactions/${claims.acct}/count?${params}`;
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: getAuthHeaders()
      });

      if (!response.ok) {
        throw new Error('Failed to fetch transaction count');
      }

      const data = await response.json();
      return data.total_count;
    } catch (error) {
      console.error('Transaction count fetch error:', error);
      throw error;
    }
  },

  /**
   * Get suspicious transactions (flagged by anomaly detection)
   */
  async getSuspiciousTransactions() {
    return this.getTransactions(50, { anomalyStatus: 'suspicious' });
  },

  /**
   * Send money to another account
   * @param {Object} paymentData - Payment details
   * @param {string} paymentData.recipientAccountNumber - Recipient's account number
   * @param {string} paymentData.recipientRoutingNumber - Recipient's routing number (optional, defaults to local)
   * @param {number} paymentData.amount - Amount in dollars
   * @param {string} paymentData.description - Payment description/memo
   * @param {string} paymentData.category - Transaction category
   * @param {boolean} paymentData.isExternal - Whether recipient is external
   */
  async sendMoney(paymentData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    // Validate inputs
    const recipientAccount = (paymentData.recipientAccountNumber || '').trim();
    const recipientRouting = (paymentData.recipientRoutingNumber || '').trim() || '883745000';
    const amount = parseFloat(paymentData.amount);
    const description = (paymentData.description || '').trim();
    const category = (paymentData.category || 'Other').trim();

    if (!recipientAccount) {
      throw new Error('Recipient account number is required');
    }

    if (isNaN(amount) || amount <= 0) {
      throw new Error('Please enter a valid amount greater than 0');
    }

    // Convert to cents
    const amountCents = Math.round(amount * 100);

    const url = `${getTransactionSageUrl()}/v1/execute-transaction`;
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          account_id: claims.acct,
          recipient_id: recipientAccount,
          recipient_routing_num: recipientRouting,
          amount_cents: amountCents,
          description: description,
          category: category,
          is_external: paymentData.isExternal || recipientRouting !== '883745000',
          uuid: crypto.randomUUID()
        })
      });

      let data;
      const text = await response.text();
      try {
        data = text ? JSON.parse(text) : {};
      } catch (jsonErr) {
        data = {};
      }

      if (!response.ok) {
        throw new Error(data.detail || data.message || text || 'Failed to send payment');
      }

      return {
        success: true,
        transactionId: data.transaction_id,
        status: data.status,
        message: data.message || 'Payment sent successfully!'
      };
    } catch (error) {
      console.error('Send money error:', error);
      throw error;
    }
  },

  /**
   * Deposit money from an external account
   * @param {Object} depositData
   * @param {string} depositData.externalAccountNumber
   * @param {string} depositData.externalRoutingNumber
   * @param {number} depositData.amount
   * @param {string} depositData.description
   */
  async depositMoney(depositData) {
    const claims = authService.getUserClaims();
    if (!claims?.acct) {
      throw new Error('User not authenticated');
    }

    const externalAccount = (depositData.externalAccountNumber || '').trim();
    const externalRouting = (depositData.externalRoutingNumber || '').trim();
    const amount = parseFloat(depositData.amount);
    const description = (depositData.description || 'Manual Deposit').trim();

    if (!externalAccount || !externalRouting) {
      throw new Error('External account details required');
    }

    if (isNaN(amount) || amount <= 0) {
      throw new Error('Please enter a valid amount greater than 0');
    }

    const url = `${getTransactionSageUrl()}/v1/deposit`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          account_id: claims.acct,
          external_account_id: externalAccount,
          external_routing_num: externalRouting,
          amount_cents: Math.round(amount * 100),
          description: description,
          uuid: crypto.randomUUID()
        })
      });

      if (!response.ok) {
        const text = await response.text();
        let errorMsg = 'Deposit failed';
        try {
          const errData = JSON.parse(text);
          errorMsg = errData.detail || errorMsg;
        } catch(e) { /* ignore */ }
        throw new Error(errorMsg);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Deposit error:', error);
      throw error;
    }
  }
};

export default {
  orchestratorAPI,
  contactSageAPI,
  moneySageAPI,
  transactionAPI
};
