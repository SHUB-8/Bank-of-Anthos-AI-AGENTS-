import React, { useState, useEffect } from 'react';
import { transactionAPI } from '../api/ai_agents.js';
import { databaseAPI } from '../api/database.js';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import { format } from 'date-fns';
import { CreditCard, AlertTriangle, CheckCircle, XCircle, Eye, Filter } from 'lucide-react';

const Transactions = () => {
  const [activeTab, setActiveTab] = useState('all');
  const [transactions, setTransactions] = useState([]);
  const [suspiciousTransactions, setSuspiciousTransactions] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedAnomaly, setExpandedAnomaly] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        if (activeTab === 'all') {
          const data = await transactionAPI.getTransactions();
          setTransactions(data);
        } else {
          const [suspiciousData, anomaliesData] = await Promise.all([
            transactionAPI.getSuspiciousTransactions(),
            databaseAPI.fetchAnomalyLogs()
          ]);
          setSuspiciousTransactions(suspiciousData);
          setAnomalies(anomaliesData);
        }
      } catch (error) {
        console.error('Failed to fetch transactions:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [activeTab]);

  const handleApproveTransaction = async (transactionId) => {
    try {
      // Update transaction status
      setTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, status: 'approved' } : t)
      );
      setSuspiciousTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, status: 'approved' } : t)
      );
    } catch (error) {
      console.error('Failed to approve transaction:', error);
    }
  };

  const handleDenyTransaction = async (transactionId) => {
    try {
      // Update transaction status
      setTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, status: 'denied' } : t)
      );
      setSuspiciousTransactions(prev =>
        prev.map(t => t.id === transactionId ? { ...t, status: 'denied' } : t)
      );
    } catch (error) {
      console.error('Failed to deny transaction:', error);
    }
  };

  const handleUpdateAnomalyStatus = async (anomalyId, status) => {
    try {
      await databaseAPI.updateAnomalyStatus(anomalyId, status);
      setAnomalies(prev =>
        prev.map(a => a.id === anomalyId ? { ...a, status } : a)
      );
    } catch (error) {
      console.error('Failed to update anomaly status:', error);
    }
  };

  const getRiskColor = (riskScore) => {
    if (riskScore >= 80) return 'text-red-600 bg-red-50 border-red-200';
    if (riskScore >= 60) return 'text-yellow-600 bg-yellow-50 border-yellow-200';
    return 'text-green-600 bg-green-50 border-green-200';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'approved': return 'text-green-600 bg-green-50';
      case 'denied': return 'text-red-600 bg-red-50';
      case 'flagged': return 'text-red-600 bg-red-50';
      case 'review': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
        <div className="flex items-center space-x-2">
          <Filter className="h-5 w-5 text-gray-400" />
          <span className="text-sm text-gray-600">Filter & Sort</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('all')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'all'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            All Transactions
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'security'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Security Review
          </button>
        </nav>
      </div>

      {/* All Transactions Tab */}
      {activeTab === 'all' && (
        <div className="bg-white rounded-lg shadow-sm border">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Transactions</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {transactions.map((transaction) => (
              <div key={transaction.id} className="p-6 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className={`p-2 rounded-full ${
                      transaction.amount > 0 ? 'bg-green-100' : 'bg-red-100'
                    }`}>
                      <CreditCard className={`h-5 w-5 ${
                        transaction.amount > 0 ? 'text-green-600' : 'text-red-600'
                      }`} />
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{transaction.description}</p>
                      <p className="text-sm text-gray-600">
                        {format(new Date(transaction.date), 'MMM dd, yyyy')} • {transaction.category}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-4">
                    {transaction.riskScore && (
                      <div className={`px-2 py-1 rounded-full border text-xs font-medium ${getRiskColor(transaction.riskScore)}`}>
                        Risk: {transaction.riskScore}%
                      </div>
                    )}
                    <div className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(transaction.status)}`}>
                      {transaction.status}
                    </div>
                    <span className={`font-semibold ${
                      transaction.amount > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {transaction.amount > 0 ? '+' : ''}${Math.abs(transaction.amount).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Security Review Tab */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          {/* Suspicious Transactions */}
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900 flex items-center">
                <AlertTriangle className="h-5 w-5 text-red-600 mr-2" />
                Suspicious Transactions
              </h2>
            </div>
            <div className="divide-y divide-gray-200">
              {suspiciousTransactions.map((transaction) => (
                <div key={transaction.id} className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-4">
                      <div className="p-2 rounded-full bg-red-100">
                        <AlertTriangle className="h-5 w-5 text-red-600" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{transaction.description}</p>
                        <p className="text-sm text-gray-600">
                          {format(new Date(transaction.date), 'MMM dd, yyyy')} • {transaction.reason}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-4">
                      <div className={`px-2 py-1 rounded-full border text-xs font-medium ${getRiskColor(transaction.riskScore)}`}>
                        Risk: {transaction.riskScore}%
                      </div>
                      <span className="font-semibold text-red-600">
                        -${Math.abs(transaction.amount).toFixed(2)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-600">
                      <p><strong>Recipient:</strong> {transaction.recipient || 'N/A'}</p>
                      {transaction.location && <p><strong>Location:</strong> {transaction.location}</p>}
                    </div>
                    
                    <div className="flex space-x-3">
                      <button
                        onClick={() => handleApproveTransaction(transaction.id)}
                        className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                        disabled={transaction.status === 'approved' || transaction.status === 'denied'}
                      >
                        <CheckCircle className="h-4 w-4" />
                        <span>Approve</span>
                      </button>
                      <button
                        onClick={() => handleDenyTransaction(transaction.id)}
                        className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                        disabled={transaction.status === 'approved' || transaction.status === 'denied'}
                      >
                        <XCircle className="h-4 w-4" />
                        <span>Deny</span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Anomaly Logs */}
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Security Anomalies</h2>
            </div>
            <div className="divide-y divide-gray-200">
              {anomalies.map((anomaly) => (
                <div key={anomaly.id} className="p-6">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center space-x-3">
                      <div className={`px-2 py-1 rounded-full border text-xs font-medium ${getRiskColor(anomaly.riskScore)}`}>
                        {anomaly.riskLevel.toUpperCase()}
                      </div>
                      <h3 className="font-medium text-gray-900">{anomaly.description}</h3>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm text-gray-600">
                        {format(new Date(anomaly.timestamp), 'MMM dd, HH:mm')}
                      </span>
                      <button
                        onClick={() => setExpandedAnomaly(expandedAnomaly === anomaly.id ? null : anomaly.id)}
                        className="text-blue-600 hover:text-blue-700"
                      >
                        <Eye className="h-4 w-4" />
                      </button>
                    </div>
                  </div>

                  {expandedAnomaly === anomaly.id && (
                    <div className="mt-4 p-4 bg-gray-50 rounded-lg space-y-3">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="font-medium text-gray-700">Type:</p>
                          <p className="text-gray-600">{anomaly.type.replace(/_/g, ' ')}</p>
                        </div>
                        <div>
                          <p className="font-medium text-gray-700">Risk Score:</p>
                          <p className="text-gray-600">{anomaly.riskScore}%</p>
                        </div>
                      </div>

                      {anomaly.details && (
                        <div>
                          <p className="font-medium text-gray-700 mb-2">Details:</p>
                          <div className="space-y-1 text-sm text-gray-600">
                            {Object.entries(anomaly.details).map(([key, value]) => (
                              <p key={key}>
                                <strong>{key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase())}:</strong> {value}
                              </p>
                            ))}
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between pt-3 border-t border-gray-200">
                        <div className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(anomaly.status)}`}>
                          {anomaly.status.replace(/_/g, ' ')}
                        </div>
                        
                        {anomaly.status === 'pending_review' && (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleUpdateAnomalyStatus(anomaly.id, 'resolved')}
                              className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
                            >
                              Resolve
                            </button>
                            <button
                              onClick={() => handleUpdateAnomalyStatus(anomaly.id, 'investigating')}
                              className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                            >
                              Investigate
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Transactions;