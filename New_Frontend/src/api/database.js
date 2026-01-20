/**
 * Database API Service
 * 
 * Integrates with Bank of Anthos services for anomaly detection and security data.
 * Anomaly data comes from the Anomaly-Sage service via the orchestrator.
 */

import authService from '../services/authService';

// Get base URLs - in development, use Vite proxy paths to avoid CORS
const getAnomalySageUrl = () => {
  if (import.meta.env.DEV) {
    // Use Vite proxy path in development
    return '/api/anomaly-sage';
  }
  return import.meta.env.VITE_ANOMALY_SAGE_URL || 'http://anomaly-sage:8085';
};

const getMoneySageUrl = () => {
  if (import.meta.env.DEV) {
    // Use Vite proxy path in development
    return '/api/money-sage';
  }
  return import.meta.env.VITE_MONEY_SAGE_URL || 'http://money-sage:8084';
};

// Helper to get auth headers
const getAuthHeaders = () => {
  const token = authService.getToken();
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

/**
 * Anomaly Log Summary - Get aggregated anomaly statistics
 */
export const fetchAnomalyLogSummary = async () => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const url = `${getAnomalySageUrl()}/summary/${claims.acct}`;
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('Failed to fetch anomaly summary');
    }

    const data = await response.json();
    
    // Transform to frontend format
    return {
      totalAnomalies: data.total_anomalies || 0,
      highRisk: data.high_risk || 0,
      mediumRisk: data.medium_risk || 0,
      lowRisk: data.low_risk || 0,
      resolved: data.resolved || 0,
      pending: data.pending || 0,
      recentTrend: data.trend || 'stable', // 'increasing', 'decreasing', 'stable'
      lastUpdated: data.last_updated || new Date().toISOString()
    };
  } catch (error) {
    console.error('Anomaly summary fetch error:', error);
    throw error;
  }
};

/**
 * Fetch detailed anomaly logs for the current user
 */
export const fetchAnomalyLogs = async (limit = 50, options = {}) => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const params = new URLSearchParams({
    limit: limit.toString()
  });
  
  if (options.riskLevel) {
    params.append('risk_level', options.riskLevel);
  }
  if (options.status) {
    params.append('status', options.status);
  }

  const url = `${getAnomalySageUrl()}/anomalies/${claims.acct}?${params}`;
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('Failed to fetch anomaly logs');
    }

    const data = await response.json();
    
    // Ensure we are working with an array
    const anomaliesList = Array.isArray(data.anomalies) ? data.anomalies : (Array.isArray(data) ? data : []);
    
    // Transform to frontend format - map all fields from anomaly_logs table
    // DB fields: log_id, transaction_id, account_id, recipient_id, amount_cents, 
    //            risk_score, status, anomaly_reasons, requested_at, confirmed_at, expires_at, created_at
    return anomaliesList.map(anomaly => ({
      // Primary identifiers
      id: anomaly.log_id || anomaly.id || anomaly.anomaly_id,
      log_id: anomaly.log_id,
      transaction_id: anomaly.transaction_id,
      
      // Account info
      account_id: anomaly.account_id,
      recipient_id: anomaly.recipient_id,
      
      // Amount (keep original cents + converted dollars)
      amount_cents: anomaly.amount_cents,
      amount: anomaly.amount_cents ? anomaly.amount_cents / 100 : anomaly.amount,
      
      // Risk info
      risk_score: anomaly.risk_score || 0,
      riskScore: anomaly.risk_score || 0,
      riskLevel: getRiskLevel(anomaly.risk_score),
      
      // Status - valid values: normal, suspicious, fraud, pending, confirmed, expired, cancelled
      status: anomaly.status || 'pending',
      
      // Reasons array
      anomaly_reasons: anomaly.anomaly_reasons || [],
      
      // Timestamps
      requested_at: anomaly.requested_at,
      confirmed_at: anomaly.confirmed_at,
      expires_at: anomaly.expires_at,
      created_at: anomaly.created_at,
      timestamp: anomaly.created_at || anomaly.requested_at,
      
      // Legacy fields for compatibility
      type: anomaly.anomaly_type || 'transaction',
      description: anomaly.description || null,
      details: anomaly.details || {}
    }));
  } catch (error) {
    console.error('Anomaly logs fetch error:', error);
    throw error;
  }
};

/**
 * Get suspicious transactions from transaction-sage
 */
export const fetchSuspiciousTransactions = async (limit = 20) => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const params = new URLSearchParams({
    limit: limit.toString(),
    anomaly_status: 'suspicious'
  });

  const url = `${getMoneySageUrl()}/transactions/${claims.acct}?${params}`;
  
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('Failed to fetch suspicious transactions');
    }

    const data = await response.json();
    
    return (data.transactions || []).map(txn => ({
      id: txn.id || txn.transaction_id,
      date: txn.created_at,
      amount: txn.amount_dollars || txn.amount / 100,
      description: txn.description || 'Transaction',
      riskScore: txn.risk_score || 0,
      riskLevel: getRiskLevel(txn.risk_score),
      status: txn.anomaly_status || 'suspicious',
      recipientAccount: txn.receiver_account_id,
      transactionType: txn.transaction_type
    }));
  } catch (error) {
    console.error('Suspicious transactions fetch error:', error);
    throw error;
  }
};

/**
 * Mark an anomaly as resolved/dismissed
 */
export const resolveAnomaly = async (anomalyId) => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const url = `${getAnomalySageUrl()}/anomalies/${anomalyId}/resolve`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({
        resolved_by: claims.user,
        resolution: 'dismissed'
      })
    });

    if (!response.ok) {
      throw new Error('Failed to resolve anomaly');
    }

    return await response.json();
  } catch (error) {
    console.error('Anomaly resolution error:', error);
    throw error;
  }
};

/**
 * Confirm a pending transaction (allow it to proceed)
 */
export const confirmAnomaly = async (anomalyId) => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const url = `${getAnomalySageUrl()}/confirm-pending/${anomalyId}`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('Failed to confirm transaction');
    }

    return await response.json();
  } catch (error) {
    console.error('Anomaly confirmation error:', error);
    throw error;
  }
};

/**
 * Cancel a pending transaction (prevent execution)
 */
export const cancelAnomaly = async (anomalyId) => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  const url = `${getAnomalySageUrl()}/cancel-pending/${anomalyId}`;
  
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders()
    });

    if (!response.ok) {
      throw new Error('Failed to cancel transaction');
    }

    return await response.json();
  } catch (error) {
    console.error('Anomaly cancellation error:', error);
    throw error;
  }
};

/**
 * Get security alerts summary for dashboard
 */
export const fetchSecurityAlerts = async () => {
  const claims = authService.getUserClaims();
  if (!claims?.acct) {
    throw new Error('User not authenticated');
  }

  try {
    // Fetch both anomaly summary and suspicious transactions
    const [summary, suspicious] = await Promise.all([
      fetchAnomalyLogSummary().catch(() => null),
      fetchSuspiciousTransactions(5).catch(() => [])
    ]);

    return {
      summary: summary || {
        totalAnomalies: 0,
        highRisk: 0,
        mediumRisk: 0,
        lowRisk: 0
      },
      recentAlerts: suspicious.slice(0, 5),
      hasActiveAlerts: (summary?.highRisk || 0) > 0 || suspicious.length > 0
    };
  } catch (error) {
    console.error('Security alerts fetch error:', error);
    throw error;
  }
};

/**
 * Helper function to determine risk level from score
 */
const getRiskLevel = (score) => {
  if (score === undefined || score === null) return 'unknown';
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  return 'low';
};

/**
 * Database API object for compatibility
 */
export const databaseAPI = {
  fetchAnomalyLogSummary,
  fetchAnomalyLogs,
  fetchSuspiciousTransactions,
  resolveAnomaly,
  confirmAnomaly,
  cancelAnomaly,
  fetchSecurityAlerts
};

export default databaseAPI;
