// Database API Service for security and anomaly data

const DB_API_BASE_URL = import.meta.env.VITE_REACT_APP_DB_API_BASE_URL || 'https://db.bankofanthos.ai';

export const databaseAPI = {
  async fetchAnomalyLogSummary() {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return {
        totalAnomalies: 12,
        highRisk: 3,
        mediumRisk: 5,
        lowRisk: 4,
        lastUpdated: new Date().toISOString(),
        trendsLast30Days: {
          totalAnomalies: 45,
          avgRiskScore: 42,
          mostCommonType: 'unusual_transaction_pattern'
        }
      };
    }

    try {
      const response = await fetch(`${DB_API_BASE_URL}/anomaly_logs/summary`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      
      if (!response.ok) throw new Error('Failed to fetch anomaly summary');
      return await response.json();
    } catch (error) {
      console.error('Anomaly summary fetch error:', error);
      // Return mock data for demo
      return {
        totalAnomalies: 12,
        highRisk: 3,
        mediumRisk: 5,
        lowRisk: 4,
        lastUpdated: new Date().toISOString(),
        trendsLast30Days: {
          totalAnomalies: 45,
          avgRiskScore: 42,
          mostCommonType: 'unusual_transaction_pattern'
        }
      };
    }
  },

  async fetchAnomalyLogs(limit = 20, riskLevel = 'all') {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return [
        {
          id: 1,
          timestamp: '2024-01-15T10:30:00Z',
          type: 'unusual_transaction_pattern',
          riskLevel: 'high',
          riskScore: 85,
          description: 'Large wire transfer to unfamiliar recipient',
          transactionId: 5,
          userId: 'user_123',
          details: {
            amount: 1200.00,
            recipient: 'Unknown Account 12345',
            location: 'Online Banking',
            deviceInfo: 'Chrome on Windows'
          },
          status: 'pending_review',
          reviewedBy: null,
          resolvedAt: null
        },
        {
          id: 2,
          timestamp: '2024-01-14T15:45:00Z',
          type: 'location_anomaly',
          riskLevel: 'medium',
          riskScore: 65,
          description: 'ATM usage in unusual location',
          transactionId: 8,
          userId: 'user_123',
          details: {
            amount: 250.00,
            location: 'Downtown ATM #4521',
            distanceFromHome: '125 miles',
            timeOfDay: '3:45 PM'
          },
          status: 'investigating',
          reviewedBy: 'security_team',
          resolvedAt: null
        },
        {
          id: 3,
          timestamp: '2024-01-13T09:15:00Z',
          type: 'velocity_check',
          riskLevel: 'low',
          riskScore: 35,
          description: 'Multiple small transactions in short time',
          transactionId: null,
          userId: 'user_123',
          details: {
            transactionCount: 8,
            timeWindow: '15 minutes',
            totalAmount: 45.99,
            merchantTypes: ['coffee', 'convenience', 'gas']
          },
          status: 'resolved',
          reviewedBy: 'ai_system',
          resolvedAt: '2024-01-13T10:00:00Z'
        }
      ];
    }

    try {
      const params = new URLSearchParams({ limit: limit.toString() });
      if (riskLevel !== 'all') {
        params.append('risk_level', riskLevel);
      }

      const response = await fetch(`${DB_API_BASE_URL}/anomaly_logs?${params}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('authToken')}` }
      });
      
      if (!response.ok) throw new Error('Failed to fetch anomaly logs');
      return await response.json();
    } catch (error) {
      console.error('Anomaly logs fetch error:', error);
      // Return mock data for demo
      return [
        {
          id: 1,
          timestamp: '2024-01-15T10:30:00Z',
          type: 'unusual_transaction_pattern',
          riskLevel: 'high',
          riskScore: 85,
          description: 'Large wire transfer to unfamiliar recipient',
          transactionId: 5,
          userId: 'user_123',
          details: {
            amount: 1200.00,
            recipient: 'Unknown Account 12345',
            location: 'Online Banking',
            deviceInfo: 'Chrome on Windows'
          },
          status: 'pending_review',
          reviewedBy: null,
          resolvedAt: null
        },
        {
          id: 2,
          timestamp: '2024-01-14T15:45:00Z',
          type: 'location_anomaly',
          riskLevel: 'medium',
          riskScore: 65,
          description: 'ATM usage in unusual location',
          transactionId: 8,
          userId: 'user_123',
          details: {
            amount: 250.00,
            location: 'Downtown ATM #4521',
            distanceFromHome: '125 miles',
            timeOfDay: '3:45 PM'
          },
          status: 'investigating',
          reviewedBy: 'security_team',
          resolvedAt: null
        },
        {
          id: 3,
          timestamp: '2024-01-13T09:15:00Z',
          type: 'velocity_check',
          riskLevel: 'low',
          riskScore: 35,
          description: 'Multiple small transactions in short time',
          transactionId: null,
          userId: 'user_123',
          details: {
            transactionCount: 8,
            timeWindow: '15 minutes',
            totalAmount: 45.99,
            merchantTypes: ['coffee', 'convenience', 'gas']
          },
          status: 'resolved',
          reviewedBy: 'ai_system',
          resolvedAt: '2024-01-13T10:00:00Z'
        }
      ];
    }
  },

  async updateAnomalyStatus(anomalyId, status, reviewNotes = '') {
    if (import.meta.env.VITE_USE_MOCK_API === 'true') {
      return { success: true, message: 'Status updated successfully' };
    }

    try {
      const response = await fetch(`${DB_API_BASE_URL}/anomaly_logs/${anomalyId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify({
          status,
          reviewNotes,
          reviewedBy: 'current_user',
          reviewedAt: new Date().toISOString()
        })
      });
      
      if (!response.ok) throw new Error('Failed to update anomaly status');
      return await response.json();
    } catch (error) {
      console.error('Anomaly status update error:', error);
      return { success: false, error: error.message };
    }
  }
};