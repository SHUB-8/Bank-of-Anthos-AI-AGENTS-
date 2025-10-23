// AI Agents API Service
const API_BASE_URL = import.meta.env.VITE_REACT_APP_API_BASE_URL || 'https://api.bankofanthos.ai';

// Orchestrator service
export const orchestratorAPI = {
  async chat(message, conversationHistory = []) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return {
        response: `I understand you're asking about "${message}". As your AI financial assistant, I can help you with budgets, transactions, contacts, and security alerts. How can I assist you further?`,
        suggestions: ['Check my budget status', 'Show recent transactions', 'Security overview'],
        timestamp: new Date().toISOString()
      };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify({
          message,
          history: conversationHistory,
          timestamp: new Date().toISOString()
        })
      });

      if (!response.ok) throw new Error('Chat request failed');
      return await response.json();
    } catch (error) {
      console.error('Chat API Error:', error);
      // Return mock response for demo
      return {
        response: `I understand you're asking about "${message}". As your AI financial assistant, I can help you with budgets, transactions, contacts, and security alerts. How can I assist you further?`,
        suggestions: ['Check my budget status', 'Show recent transactions', 'Security overview'],
        timestamp: new Date().toISOString()
      };
    }
  }
};

// Contact-Sage service
export const contactSageAPI = {
  async getContacts(search = '') {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        { id: 1, name: 'Alice Johnson', email: 'alice@example.com', phone: '+1-555-0123', isExternal: false },
        { id: 2, name: 'Bob Smith', email: 'bob@external.com', phone: '+1-555-0124', isExternal: true },
        { id: 3, name: 'Charlie Davis', email: 'charlie@bank.com', phone: '+1-555-0125', isExternal: false }
      ].filter(contact => 
        contact.name.toLowerCase().includes(search.toLowerCase()) ||
        contact.email.toLowerCase().includes(search.toLowerCase())
      );
    }

    try {
      const response = await fetch(`${API_BASE_URL}/contacts?search=${encodeURIComponent(search)}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch contacts');
      return await response.json();
    } catch (error) {
      console.error('Contacts fetch error:', error);
      return [
        { id: 1, name: 'Alice Johnson', email: 'alice@example.com', phone: '+1-555-0123', isExternal: false },
        { id: 2, name: 'Bob Smith', email: 'bob@external.com', phone: '+1-555-0124', isExternal: true },
        { id: 3, name: 'Charlie Davis', email: 'charlie@bank.com', phone: '+1-555-0125', isExternal: false }
      ].filter(contact => 
        contact.name.toLowerCase().includes(search.toLowerCase()) ||
        contact.email.toLowerCase().includes(search.toLowerCase())
      );
    }
  },

  async createContact(contactData) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return { ...contactData, id: Date.now() };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/contacts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify(contactData)
      });
      if (!response.ok) throw new Error('Failed to create contact');
      return await response.json();
    } catch (error) {
      console.error('Contact creation error:', error);
      return { ...contactData, id: Date.now() };
    }
  },

  async updateContact(id, contactData) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return { ...contactData, id };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/contacts/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify(contactData)
      });
      if (!response.ok) throw new Error('Failed to update contact');
      return await response.json();
    } catch (error) {
      console.error('Contact update error:', error);
      return { ...contactData, id };
    }
  },

  async deleteContact(id) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return true;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/contacts/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to delete contact');
      return true;
    } catch (error) {
      console.error('Contact deletion error:', error);
      return false;
    }
  },

  async fuzzySearch(query) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return this.getContacts(query);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/contacts/search?q=${encodeURIComponent(query)}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Search failed');
      return await response.json();
    } catch (error) {
      console.error('Fuzzy search error:', error);
      return this.getContacts(query);
    }
  }
};

// Money-Sage service
export const moneySageAPI = {
  async getBudgets() {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        { id: 1, name: 'Groceries', limit: 500, spent: 320, category: 'Food', color: '#10B981' },
        { id: 2, name: 'Entertainment', limit: 200, spent: 180, category: 'Leisure', color: '#F59E0B' },
        { id: 3, name: 'Transportation', limit: 300, spent: 280, category: 'Transport', color: '#EF4444' },
        { id: 4, name: 'Utilities', limit: 150, spent: 120, category: 'Bills', color: '#3B82F6' }
      ];
    }

    try {
      const response = await fetch(`${API_BASE_URL}/budgets`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch budgets');
      return await response.json();
    } catch (error) {
      console.error('Budgets fetch error:', error);
      return [
        { id: 1, name: 'Groceries', limit: 500, spent: 320, category: 'Food', color: '#10B981' },
        { id: 2, name: 'Entertainment', limit: 200, spent: 180, category: 'Leisure', color: '#F59E0B' },
        { id: 3, name: 'Transportation', limit: 300, spent: 280, category: 'Transport', color: '#EF4444' },
        { id: 4, name: 'Utilities', limit: 150, spent: 120, category: 'Bills', color: '#3B82F6' }
      ];
    }
  },

  async createBudget(budgetData) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return { ...budgetData, id: Date.now() };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/budgets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify(budgetData)
      });
      if (!response.ok) throw new Error('Failed to create budget');
      return await response.json();
    } catch (error) {
      console.error('Budget creation error:', error);
      return { ...budgetData, id: Date.now() };
    }
  },

  async updateBudget(id, budgetData) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return { ...budgetData, id };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/budgets/${id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify(budgetData)
      });
      if (!response.ok) throw new Error('Failed to update budget');
      return await response.json();
    } catch (error) {
      console.error('Budget update error:', error);
      return { ...budgetData, id };
    }
  },

  async deleteBudget(id) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return true;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/budgets/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to delete budget');
      return true;
    } catch (error) {
      console.error('Budget deletion error:', error);
      return false;
    }
  },

  async getOverview() {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return {
        totalBudget: 1150,
        totalSpent: 900,
        savingsGoal: 2000,
        currentSavings: 1500,
        monthlyIncome: 5000
      };
    }

    try {
      const response = await fetch(`${API_BASE_URL}/overview`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch overview');
      return await response.json();
    } catch (error) {
      console.error('Overview fetch error:', error);
      return {
        totalBudget: 1150,
        totalSpent: 900,
        savingsGoal: 2000,
        currentSavings: 1500,
        monthlyIncome: 5000
      };
    }
  },

  async getTips() {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        'Consider reducing entertainment spending by 10%',
        'Your grocery spending is within healthy limits',
        'Set up automatic savings of $200/month'
      ];
    }

    try {
      const response = await fetch(`${API_BASE_URL}/tips`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch tips');
      return await response.json();
    } catch (error) {
      console.error('Tips fetch error:', error);
      return [
        'Consider reducing entertainment spending by 10%',
        'Your grocery spending is within healthy limits',
        'Set up automatic savings of $200/month'
      ];
    }
  }
};

// Transaction History service
export const transactionAPI = {
  async getTransactions(limit = 50, offset = 0) {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        { id: 1, date: '2024-01-15', amount: -85.50, description: 'Grocery Store', category: 'Groceries', status: 'cleared' },
        { id: 2, date: '2024-01-14', amount: -120.00, description: 'Gas Station', category: 'Transportation', status: 'cleared' },
        { id: 3, date: '2024-01-13', amount: 2500.00, description: 'Salary Deposit', category: 'Income', status: 'cleared' },
        { id: 4, date: '2024-01-12', amount: -45.99, description: 'Streaming Service', category: 'Entertainment', status: 'cleared' },
        { id: 5, date: '2024-01-11', amount: -1200.00, description: 'Unusual Wire Transfer', category: 'Transfer', status: 'flagged', riskScore: 85 }
      ];
    }

    try {
      const response = await fetch(`${API_BASE_URL}/transactions?limit=${limit}&offset=${offset}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch transactions');
      return await response.json();
    } catch (error) {
      console.error('Transactions fetch error:', error);
      return [
        { id: 1, date: '2024-01-15', amount: -85.50, description: 'Grocery Store', category: 'Groceries', status: 'cleared' },
        { id: 2, date: '2024-01-14', amount: -120.00, description: 'Gas Station', category: 'Transportation', status: 'cleared' },
        { id: 3, date: '2024-01-13', amount: 2500.00, description: 'Salary Deposit', category: 'Income', status: 'cleared' },
        { id: 4, date: '2024-01-12', amount: -45.99, description: 'Streaming Service', category: 'Entertainment', status: 'cleared' },
        { id: 5, date: '2024-01-11', amount: -1200.00, description: 'Unusual Wire Transfer', category: 'Transfer', status: 'flagged', riskScore: 85 }
      ];
    }
  },

  async getSuspiciousTransactions() {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        {
          id: 5,
          date: '2024-01-11',
          amount: -1200.00,
          description: 'Unusual Wire Transfer',
          category: 'Transfer',
          status: 'flagged',
          riskScore: 85,
          reason: 'Large amount to unfamiliar recipient',
          recipient: 'Unknown Account 12345'
        },
        {
          id: 8,
          date: '2024-01-10',
          amount: -250.00,
          description: 'ATM Withdrawal',
          category: 'Cash',
          status: 'review',
          riskScore: 65,
          reason: 'ATM usage in unusual location',
          location: 'Downtown ATM #4521'
        }
      ];
    }

    try {
      const response = await fetch(`${API_BASE_URL}/transactions/suspicious`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      if (!response.ok) throw new Error('Failed to fetch suspicious transactions');
      return await response.json();
    } catch (error) {
      console.error('Suspicious transactions fetch error:', error);
      return [
        {
          id: 5,
          date: '2024-01-11',
          amount: -1200.00,
          description: 'Unusual Wire Transfer',
          category: 'Transfer',
          status: 'flagged',
          riskScore: 85,
          reason: 'Large amount to unfamiliar recipient',
          recipient: 'Unknown Account 12345'
        },
        {
          id: 8,
          date: '2024-01-10',
          amount: -250.00,
          description: 'ATM Withdrawal',
          category: 'Cash',
          status: 'review',
          riskScore: 65,
          reason: 'ATM usage in unusual location',
          location: 'Downtown ATM #4521'
        }
      ];
    }
  }
};