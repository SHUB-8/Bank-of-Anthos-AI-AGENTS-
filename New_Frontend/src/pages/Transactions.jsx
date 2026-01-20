import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { transactionAPI, contactSageAPI } from '../api/ai_agents.js';
import { databaseAPI } from '../api/database.js';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import { format, parseISO, isValid } from 'date-fns';
import { 
  CreditCard, AlertTriangle, CheckCircle, XCircle, Filter, 
  ChevronDown, RefreshCw, ShieldAlert, Clock, Timer
} from 'lucide-react';

const Transactions = () => {
  const [activeTab, setActiveTab] = useState('all');
  const [transactions, setTransactions] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [contacts, setContacts] = useState([]); // Store contacts for name lookup
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(50);
  const [hasMore, setHasMore] = useState(true);
  
  // Filter states
  const [filterType, setFilterType] = useState('all'); // 'all', 'debit', 'credit'
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [sortOrder, setSortOrder] = useState('desc'); // 'desc' = newest first
  const [showFilters, setShowFilters] = useState(false);

  // Get unique categories from transactions
  const categories = useMemo(() => {
    if (!Array.isArray(transactions)) return ['all'];
    const cats = new Set(transactions.map(t => t.category).filter(Boolean));
    return ['all', ...Array.from(cats)];
  }, [transactions]);

  // Filtered and sorted transactions
  const filteredTransactions = useMemo(() => {
    if (!Array.isArray(transactions)) return [];
    let filtered = [...transactions];
    
    // Filter by type
    if (filterType === 'debit') {
      filtered = filtered.filter(t => t.amount < 0 || t.transactionType === 'debit');
    } else if (filterType === 'credit') {
      filtered = filtered.filter(t => t.amount > 0 || t.transactionType === 'credit');
    }
    
    // Filter by category
    if (filterCategory !== 'all') {
      filtered = filtered.filter(t => t.category === filterCategory);
    }

    // Filter by status
    if (filterStatus !== 'all') {
      filtered = filtered.filter(t => (t.status || 'normal') === filterStatus);
    }
    
    // Sort by date
    filtered.sort((a, b) => {
      const dateA = a.date ? new Date(a.date) : new Date(0);
      const dateB = b.date ? new Date(b.date) : new Date(0);
      return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
    });
    
    return filtered;
  }, [transactions, filterType, filterCategory, filterStatus, sortOrder]);

  // Categorize anomalies for Security Review based on DB status values:
  // DB status values: 'normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud'
  const securitySections = useMemo(() => {
    const actionRequired = [];  // pending transactions needing confirmation (not expired)
    const activityLog = [];     // confirmed, expired, cancelled (past pending/blocked activity)
    const fraudDetected = [];   // fraud status

    const now = new Date();

    if (Array.isArray(anomalies)) {
      anomalies.forEach(anomaly => {
        if (!anomaly) return;
        const expiresAt = anomaly.expires_at ? new Date(anomaly.expires_at) : null;
        const isExpired = expiresAt && expiresAt < now;

        if (anomaly.status === 'pending') {
          if (!isExpired) {
            // Action Required: pending and not yet expired
            actionRequired.push(anomaly);
          } else {
            // Expired pending goes to activity log
            activityLog.push({ ...anomaly, status: 'expired' });
          }
        } else if (anomaly.status === 'fraud') {
          // Fraud Detected section
          fraudDetected.push(anomaly);
        } else if (['cancelled', 'confirmed', 'expired'].includes(anomaly.status)) {
          // These statuses go to activity log
          activityLog.push(anomaly);
        }
      });
    }

    return { actionRequired, activityLog, fraudDetected };
  }, [anomalies]);

  const fetchData = useCallback(async (isLoadMore = false) => {
    if (!isLoadMore) setLoading(true);
    try {
      // Fetch contacts for name resolution if not already loaded
      if (contacts.length === 0) {
        try {
           const contactsData = await contactSageAPI.getContacts();
           setContacts(contactsData);
        } catch (e) {
           console.warn("Could not load contacts for name resolution", e);
        }
      }

      if (activeTab === 'all') {
        const currentLimit = isLoadMore ? limit + 50 : 50;
        const data = await transactionAPI.getTransactions(currentLimit, { order: sortOrder });
        const transactionsData = Array.isArray(data) ? data : [];
        setTransactions(transactionsData);
        setLimit(currentLimit);
        setHasMore(transactionsData.length === currentLimit);
      } else {
        // For Security Tab, fetch more records to ensure we get all non-normal transactions
        const anomaliesData = await databaseAPI.fetchAnomalyLogs(200);
        // Filter out 'normal' status - security review only shows anomalies
        const securityAnomalies = (Array.isArray(anomaliesData) ? anomaliesData : []).filter(a => 
          a && a.status && a.status !== 'normal'
        );
        setAnomalies(securityAnomalies);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      if (!isLoadMore) {
        setTransactions([]);
        setAnomalies([]);
      }
    } finally {
      if (!isLoadMore) setLoading(false);
    }
  }, [activeTab, sortOrder, limit, contacts.length]);

  useEffect(() => {
    setLimit(50);
    fetchData(false);
  }, [activeTab, sortOrder, fetchData]); // Refresh on tab or sort change

  const handleLoadMore = () => {
    fetchData(true);
  };

  // Helper to find contact name by account number
  const getContactName = (accountNum) => {
    if (!accountNum) return null;
    const contact = contacts.find(c => c.accountNumber === accountNum);
    return contact ? contact.name : null;
  };

  // Helper to safely format date
  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown date';
    try {
      const date = typeof dateStr === 'string' ? parseISO(dateStr) : new Date(dateStr);
      if (!isValid(date)) return 'Invalid date';
      return format(date, 'MMM dd, yyyy HH:mm');
    } catch {
      return 'Invalid date';
    }
  };

  const getRiskColor = (riskScore) => {
    const score = parseFloat(riskScore);
    if (score >= 0.8) return 'bg-red-50 text-red-700 border-red-100';
    if (score >= 0.5) return 'bg-orange-50 text-orange-700 border-orange-100';
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  };

  const getStatusColor = (status) => {
    const s = status || 'normal';
    const styles = {
      normal: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      confirmed: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      approved: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      pending: 'bg-amber-50 text-amber-600 border-amber-100',
      fraud: 'bg-red-50 text-red-600 border-red-100',
      cancelled: 'bg-slate-50 text-slate-500 border-slate-100',
      expired: 'bg-gray-50 text-gray-500 border-gray-100',
      resolved: 'bg-emerald-50 text-emerald-600 border-emerald-100'
    };
    return styles[s] || 'bg-gray-50 text-gray-600 border-gray-200';
  };

  const displayStatus = (status) => {
    const s = String(status || 'normal');
    // Map suspicious back to pending visually just in case
    if (s === 'suspicious') return 'Pending';
    return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ');
  };

  // Get icon and color based on transaction status
  const getStatusIcon = (status) => {
    const s = String(status || 'normal');
    switch (s) {
      case 'fraud':
        return { icon: ShieldAlert, bgColor: 'bg-red-50', iconColor: 'text-red-500' };
      case 'cancelled':
      case 'denied':
        return { icon: XCircle, bgColor: 'bg-slate-50', iconColor: 'text-slate-400' };
      case 'confirmed':
      case 'cleared':
      case 'approved':
        return { icon: CheckCircle, bgColor: 'bg-emerald-50', iconColor: 'text-emerald-500' };
      case 'expired':
        return { icon: Timer, bgColor: 'bg-gray-50', iconColor: 'text-gray-400' };
      case 'pending':
      case 'suspicious':
        return { icon: Clock, bgColor: 'bg-amber-50', iconColor: 'text-amber-500' };
      default:
        // normal
        return { icon: CheckCircle, bgColor: 'bg-emerald-50', iconColor: 'text-emerald-500' };
    }
  };

  const handleApproveTransaction = async (logId) => {
    try {
      const anomaly = anomalies.find(a => a.log_id === logId || a.id === logId);
      if (!anomaly) {
         console.error('Anomaly not found for ID:', logId);
         return;
      }

      // 1. Confirm the anomaly in the risk service
      await databaseAPI.confirmAnomaly(logId);
      
      // 2. Retry the transaction
      // Since the backend blocks execution on pending/fraud, we must re-submit 
      // the transaction after confirmation. The anomaly service will recognize it as confirmed.
      if (anomaly.recipient_id && anomaly.amount_cents) {
        await transactionAPI.sendMoney({
          recipientAccountNumber: anomaly.recipient_id,
          recipientRoutingNumber: '883745000', // Default intra-bank routing
          amount: (anomaly.amount_cents / 100).toFixed(2),
          description: 'Approved Transaction', // Original description lost in anomaly log
          category: 'General',
          isExternal: false
        });
        
        // Show success message since money is actually moving now
        alert('Transaction confirmed and executed successfully.');
      }

      // Optimistic update
      setAnomalies(prev => prev.map(a => 
        a.log_id === logId || a.id === logId ? { ...a, status: 'confirmed' } : a
      ));
      
      // Refresh to show the new transaction
      fetchData();

    } catch (error) {
      console.error('Failed to approve transaction:', error);
      alert('Failed to execute transaction after approval. Please try again.');
    }
  };

  const handleDenyTransaction = async (logId) => {
    try {
      await databaseAPI.cancelAnomaly(logId);
      // Optimistic update
      setAnomalies(prev => prev.map(a => 
        a.log_id === logId || a.id === logId ? { ...a, status: 'cancelled' } : a
      ));
    } catch (error) {
      console.error('Failed to deny transaction:', error);
      alert('Failed to deny transaction. Please try again.');
    }
  };
  
  const renderAnomalyCard = (anomaly, showActions = false) => {
     if (!anomaly) return null;
     // Ensure we have an ID to work with (log_id or id)
     const anomalyId = anomaly.log_id || anomaly.id || Math.random().toString();
     const riskScore = anomaly.risk_score ?? anomaly.riskScore ?? 0;
     const amountDollars = anomaly.amount_cents ? (anomaly.amount_cents / 100) : (anomaly.amount || 0);
     const reasons = Array.isArray(anomaly.anomaly_reasons) ? anomaly.anomaly_reasons : [];
     const iconInfo = getStatusIcon(anomaly.status);
     const IconComponent = iconInfo.icon;
     
     return (
      <div key={anomalyId} className="p-6 hover:bg-gray-50 transition-colors">
        {/* Header Row */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-4">
            <div className={`p-2 rounded-full ${iconInfo.bgColor}`}>
               <IconComponent className={`h-5 w-5 ${iconInfo.iconColor}`} />
            </div>
            <div>
              <p className="font-semibold text-gray-800">
                 {anomaly.description || `Transfer to ${anomaly.recipient_id || 'Unknown'}`}
              </p>
              <div className="flex items-center space-x-2 text-sm text-gray-500">
                <span>{formatDate(anomaly.created_at || anomaly.requested_at || anomaly.timestamp)}</span>
                {anomaly.account_id && (
                  <>
                    <span>•</span>
                    <span>From: {anomaly.account_id}</span>
                  </>
                )}
                {anomaly.recipient_id && (
                  <>
                    <span>•</span>
                    <span>To: {anomaly.recipient_id}</span>
                  </>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-4">
             {/* Risk Score Badge */}
             <div className={`px-3 py-1 rounded-full border text-xs font-medium ${getRiskColor(riskScore)}`}>
               Risk: {(Number(riskScore) * (riskScore <= 1 ? 100 : 1)).toFixed(0)}%
             </div>
             {/* Amount */}
             <span className="font-semibold text-gray-800 text-lg">
                ${Number(amountDollars).toFixed(2)}
             </span>
          </div>
        </div>

        {/* Reasons Section - Always shown for Security Review */}
        {reasons.length > 0 && (
            <div className="mb-4">
                <p className="text-[10px] uppercase font-bold text-gray-400 mb-2 tracking-wider">Risk Factors:</p>
                <div className="flex flex-wrap gap-2">
                    {reasons.map((reason, i) => (
                      <span key={i} className="px-2 py-1 bg-red-50 text-red-600 border border-red-100 rounded text-xs font-medium">
                        {String(reason)}
                      </span>
                    ))}
                </div>
            </div>
        )}

        {/* Status & Actions Row */}
        <div className="flex items-center justify-between pt-3 border-t border-gray-100">
            <div className="flex items-center space-x-3">
              <div className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(anomaly.status)}`}>
                  {displayStatus(anomaly.status)}
              </div>
              {anomaly.expires_at && (anomaly.status === 'pending' || anomaly.status === 'suspicious') && (
                <span className="text-xs text-gray-500">
                  Expires: {formatDate(anomaly.expires_at)}
                </span>
              )}
              {anomaly.confirmed_at && anomaly.status === 'confirmed' && (
                <span className="text-xs text-gray-500">
                  Confirmed: {formatDate(anomaly.confirmed_at)}
                </span>
              )}
            </div>
            
            {showActions && (
                <div className="flex space-x-3">
                    <button
                    onClick={() => handleApproveTransaction(anomalyId)}
                    className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-sm"
                    >
                    <CheckCircle className="h-4 w-4" />
                    <span>Approve</span>
                    </button>
                    <button
                    onClick={() => handleDenyTransaction(anomalyId)}
                    className="flex items-center space-x-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
                    >
                    <XCircle className="h-4 w-4" />
                    <span>Deny</span>
                    </button>
                </div>
            )}
        </div>
      </div>
    );
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
        
        {/* Only show Filters and Refresh on All Transactions tab */}
        {activeTab === 'all' && (
        <div className="flex items-center space-x-4">
          <button
            onClick={fetchData}
            className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            <span className="text-sm">Refresh</span>
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center space-x-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            <Filter className="h-4 w-4 text-gray-600" />
            <span className="text-sm text-gray-700">Filters</span>
            <ChevronDown className={`h-4 w-4 text-gray-600 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </button>
        </div>
        )}
      </div>

      {/* Filter Panel (Only for All Transactions) */}
      {activeTab === 'all' && showFilters && (
        <div className="bg-white p-4 rounded-lg shadow-sm border animate-in slide-in-from-top duration-200">
           {/* ... existing filter controls ... */}
           {/* Reusing the same filter UI structure as before for brevity in this replace block, 
               but realistically in a full rewrite I'd include the JSX. 
               Assuming the user hasn't asked to change filter logic, just keeping it consistent. */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Transaction Type</label>
              <select value={filterType} onChange={(e) => setFilterType(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="all">All Types</option>
                <option value="debit">Sent (Debit)</option>
                <option value="credit">Received (Credit)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="all">All</option>
                <option value="normal">Normal</option>
                <option value="pending">Pending</option>
                <option value="confirmed">Confirmed</option>
                <option value="cancelled">Cancelled</option>
                <option value="fraud">Fraud</option>
                <option value="expired">Expired</option>
              </select>
            </div>
            <div>
             <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
             <select value={filterCategory} onChange={(e) => setFilterCategory(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
               {categories.map(cat => <option key={cat} value={cat}>{cat === 'all' ? 'All' : cat}</option>)}
             </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sort Order</label>
              <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm">
                <option value="desc">Newest First</option>
                <option value="asc">Oldest First</option>
              </select>
            </div>
          </div>
          
          {/* Active Filters Summary */}
          {(filterType !== 'all' || filterCategory !== 'all' || filterStatus !== 'all') && (
            <div className="mt-3 flex items-center space-x-2">
               {/* Simplified summary */}
              <span className="text-sm text-gray-600">Active filters applied</span>
              <button
                onClick={() => { setFilterType('all'); setFilterCategory('all'); setFilterStatus('all'); }}
                className="text-xs text-red-600 hover:text-red-800"
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      )}

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
             <h2 className="text-lg font-semibold text-gray-900">Recent Activity</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {filteredTransactions.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <CreditCard className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                <p>No transactions found.</p>
              </div>
            ) : (
              filteredTransactions.map((transaction) => {
                const statusIconInfo = getStatusIcon(transaction.status);
                const IconComponent = statusIconInfo?.icon || CreditCard;
                const bgColor = statusIconInfo?.bgColor || 'bg-gray-100';
                const iconColor = statusIconInfo?.iconColor || 'text-gray-600';
                
                return (
                <div key={transaction.id} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-4">
                      <div className={`p-2.5 rounded-full ${bgColor} mt-1`}>
                        <IconComponent className={`h-5 w-5 ${iconColor}`} />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <p className="font-semibold text-gray-800">{transaction.description}</p>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] uppercase font-black tracking-wider ${
                            transaction.transactionType === 'debit' ? 'bg-amber-50 text-amber-600 border border-amber-100' : 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                          }`}>
                            {transaction.transactionType}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-gray-400">
                          <span>{formatDate(transaction.date)}</span>
                          <span>ID: <span className="font-mono">{String(transaction.id).substring(0, 12)}</span></span>
                          
                          {transaction.recipientAccount && (
                            <span>
                                <span className="font-medium text-gray-500 mr-1">{transaction.transactionType === 'credit' ? 'From:' : 'To:'}</span>
                                <span className="font-medium text-gray-700">
                                   {getContactName(transaction.recipientAccount) && (
                                     <span className="font-bold text-gray-900 mr-1">{getContactName(transaction.recipientAccount)}</span>
                                   )}
                                   ({transaction.recipientAccount})
                                </span>
                            </span>
                          )}
                          <span>Category: <span className="text-gray-600 font-medium">{transaction.category || 'Other'}</span></span>
                        </div>
                        
                        {/* Show reasons for non-normal transactions - Small Blocks/Chips */}
                        {transaction.status && transaction.status !== 'normal' && 
                         Array.isArray(transaction.anomalyReasons) && transaction.anomalyReasons.length > 0 && (
                          <div className="mt-3">
                            <div className="flex flex-wrap gap-2">
                              {transaction.anomalyReasons.map((reason, i) => (
                                <span key={i} className="px-2 py-0.5 bg-red-50 text-red-500 border border-red-100 rounded text-[10px] font-medium uppercase tracking-tight">
                                  {String(reason)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end space-y-2">
                       <span className={`text-lg font-semibold ${transaction.amount > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {transaction.amount > 0 ? '+' : '-'}${Math.abs(transaction.amount).toFixed(2)}
                      </span>
                      {/* Show risk score for non-normal transactions */}
                      {transaction.status && transaction.status !== 'normal' && 
                       transaction.riskScore !== undefined && transaction.riskScore !== null && (
                        <div className={`px-2 py-0.5 rounded border text-[10px] font-medium ${getRiskColor(transaction.riskScore)}`}>
                          RISK {(Number(transaction.riskScore) * (transaction.riskScore <= 1 ? 100 : 1)).toFixed(0)}%
                        </div>
                      )}
                      <div className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${getStatusColor(transaction.status)}`}>
                        {displayStatus(transaction.status)}
                      </div>
                    </div>
                  </div>
                </div>
              );})
            )}
            
            {hasMore && filteredTransactions.length > 0 && (
              <div className="p-6 text-center border-t border-gray-100">
                <button
                  onClick={handleLoadMore}
                  className="px-6 py-2 bg-blue-50 text-blue-600 font-bold rounded-lg hover:bg-blue-100 transition-colors flex items-center space-x-2 mx-auto"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  <span>Load 50 More Transactions</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Security Review Tab */}
      {activeTab === 'security' && (
        <div className="space-y-8">
            
          {/* Section 1: Action Required - Suspicious transactions needing confirmation */}
          <div className="space-y-4">
             <div className="flex items-center space-x-2 border-b border-gray-200 pb-2">
                 <ShieldAlert className="h-5 w-5 text-orange-600" />
                 <h2 className="text-lg font-semibold text-gray-900">Action Required</h2>
                 <span className="bg-orange-100 text-orange-800 text-xs px-2 py-0.5 rounded-full">{securitySections.actionRequired.length}</span>
             </div>
             
             {securitySections.actionRequired.length === 0 ? (
                 <div className="bg-white p-8 rounded-lg border border-dashed border-gray-300 text-center text-gray-500">
                     <CheckCircle className="h-10 w-10 mx-auto mb-2 text-green-500 opacity-50" />
                     <p>No transactions waiting for approval.</p>
                 </div>
             ) : (
                 <div className="bg-white rounded-lg shadow-sm border divide-y divide-gray-200">
                     {securitySections.actionRequired.map(anomaly => renderAnomalyCard(anomaly, true))}
                 </div>
             )}
          </div>

          {/* Section 2: Pending Activity Log - confirmed, expired, cancelled history */}
          <div className="space-y-4">
             <div className="flex items-center space-x-2 border-b border-gray-200 pb-2">
                 <Timer className="h-5 w-5 text-blue-600" />
                 <h2 className="text-lg font-semibold text-gray-900">Security Activity Log</h2>
                 <span className="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded-full">{securitySections.activityLog.length}</span>
             </div>
             
             {securitySections.activityLog.length === 0 ? (
                 <p className="text-sm text-gray-500 italic p-4">No historical security activity found.</p>
             ) : (
                 <div className="bg-white rounded-lg shadow-sm border divide-y divide-gray-200 opacity-90">
                     {securitySections.activityLog.map(anomaly => renderAnomalyCard(anomaly, false))}
                 </div>
             )}
          </div>

          {/* Section 3: Detected Fraud & Blocked - fraud status or cancelled/blocked */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2 border-b border-gray-200 pb-2">
                <ShieldAlert className="h-5 w-5 text-red-600" />
                <h2 className="text-lg font-semibold text-red-700">Detected Fraud & Blocked</h2>
                <span className="bg-red-100 text-red-800 text-xs px-2 py-0.5 rounded-full">{securitySections.fraudDetected.length}</span>
            </div>
            
            {securitySections.fraudDetected.length === 0 ? (
                <div className="bg-white p-8 rounded-lg border border-dashed border-gray-300 text-center text-gray-500">
                    <CheckCircle className="h-10 w-10 mx-auto mb-2 text-green-500 opacity-50" />
                    <p>No fraud or blocked transactions detected.</p>
                </div>
            ) : (
                <div className="bg-white rounded-lg shadow-sm border border-red-200 divide-y divide-red-100">
                    {securitySections.fraudDetected.map(anomaly => renderAnomalyCard(anomaly, false))}
                </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
};

export default Transactions;