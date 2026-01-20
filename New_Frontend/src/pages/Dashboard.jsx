import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { moneySageAPI, transactionAPI } from '../api/ai_agents.js';
import { BudgetDonutChart } from '../components/BudgetChart.jsx';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import SendMoney from '../components/SendMoney.jsx';
import { 
  AlertTriangle, TrendingUp, Shield, DollarSign, Target, 
  Send, PieChart, RefreshCw, ShieldAlert, Clock, 
  CheckCircle, CreditCard, XCircle, Timer
} from 'lucide-react';

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [budgets, setBudgets] = useState([]);
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tipsLoading, setTipsLoading] = useState(false);
  const [showSendMoney, setShowSendMoney] = useState(false);

  const refreshData = async () => {
    try {
      const [transactionData, balanceData, overviewData] = await Promise.all([
        transactionAPI.getTransactions(10),
        moneySageAPI.getBalance(),
        moneySageAPI.getOverview()
      ]);
      
      setDashboardData(prev => ({
        ...prev,
        totalBalance: balanceData ?? prev?.totalBalance ?? 0,
        monthlySpending: overviewData?.totalSpent ?? prev?.monthlySpending ?? 0,
        recentTransactions: (transactionData || []).slice(0, 5)
      }));
    } catch (error) {
      console.error('Failed to refresh data:', error);
    }
  };

  const handleRefreshTips = async () => {
    try {
      setTipsLoading(true);
      console.log('Refreshing tips - calling API...');
      const tipsData = await moneySageAPI.getTips();
      console.log('Tips API response:', tipsData);
      
      if (tipsData && tipsData.length > 0) {
        const selectedTips = tipsData.slice(0, 3);
        
        const today = new Date().toDateString();
        localStorage.removeItem('financial_tips'); // Clear old explicitly
        localStorage.setItem('financial_tips', JSON.stringify(selectedTips));
        localStorage.setItem('financial_tips_date', today);
        
        setInsights(selectedTips.map((tip, index) => ({
          title: `Financial Tip ${index + 1}`,
          description: tip,
          type: 'info'
        })));
        console.log('Tips updated successfully:', selectedTips);
      } else {
        // No tips returned, keep existing
        console.log('No new tips returned from API - keeping existing');
      }
    } catch (e) {
      console.error('Failed to refresh tips:', e);
      // Keep showing cached tips on error - don't clear state
    } finally {
      setTipsLoading(false);
    }
  };

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        console.log('Fetching dashboard data...');
        
        // Fetch each separately so we can handle individual failures
        let budgetData = [];
        let tipsData = [];
        let transactionData = [];
        let balanceData = null;
        let overviewData = null;
        
        try {
          budgetData = await moneySageAPI.getBudgets();
        } catch (e) {
          console.error('Failed to fetch budgets:', e);
        }
        
        try {
          // Check cache for tips first
          const today = new Date().toDateString();
          const cachedDate = localStorage.getItem('financial_tips_date');
          const cachedTips = localStorage.getItem('financial_tips');

          if (cachedDate === today && cachedTips) {
            tipsData = JSON.parse(cachedTips);
          } else {
            // Fetch fresh if no cache or old cache
            tipsData = await moneySageAPI.getTips();
            if (tipsData && tipsData.length > 0) {
              tipsData = tipsData.slice(0, 3);
              localStorage.setItem('financial_tips', JSON.stringify(tipsData));
              localStorage.setItem('financial_tips_date', today);
            }
          }
        } catch (e) {
          console.error('Failed to fetch tips:', e);
        }
        
        try {
          transactionData = await transactionAPI.getTransactions(10);
        } catch (e) {
          console.error('Failed to fetch transactions:', e);
        }
        
        try {
          balanceData = await moneySageAPI.getBalance();
        } catch (e) {
          console.error('Failed to fetch balance:', e);
        }

        try {
          overviewData = await moneySageAPI.getOverview();
        } catch (e) {
          console.error('Failed to fetch overview:', e);
        }

        // Filter for active budgets only
        const activeBudgets = (budgetData || []).filter(b => {
            if (!b.periodEnd) return true;
            return new Date(b.periodEnd) >= new Date(new Date().setHours(0,0,0,0));
        });

        setBudgets(activeBudgets);
        setInsights((tipsData || []).map((tip, index) => ({
          title: `Financial Tip ${index + 1}`,
          description: tip,
          type: 'info'
        })));
        
        // Use real balance if available, otherwise calculate from transactions
        const totalBalance = balanceData ?? (transactionData || []).reduce((sum, t) => sum + t.amount, 0);
        
        setDashboardData({
          totalBalance,
          monthlySpending: overviewData?.totalSpent ?? (transactionData || [])
            .filter(t => t.amount < 0)
            .reduce((sum, t) => sum + Math.abs(t.amount), 0),
          recentTransactions: (transactionData || []).slice(0, 5),
          budgetUsage: overviewData?.totalBudget > 0 
            ? Math.round((overviewData.totalSpent / overviewData.totalBudget) * 100)
            : 0
        });
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
        // Set fallback data to prevent blank screen
        setBudgets([]);
        setInsights([]);
        setDashboardData({
          totalBalance: 0,
          monthlySpending: 0,
          recentTransactions: []
        });
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  const getStatusIcon = (status, amount) => {
    const s = String(status || 'normal');
    switch (s) {
      case 'fraud':
        return { icon: ShieldAlert, bgColor: 'bg-red-50', iconColor: 'text-red-500' };
      case 'suspicious':
        return { icon: AlertTriangle, bgColor: 'bg-orange-50', iconColor: 'text-orange-500' };
      case 'cancelled':
      case 'denied':
        return { icon: XCircle, bgColor: 'bg-slate-50', iconColor: 'text-slate-400' };
      case 'confirmed':
      case 'approved':
        return { icon: CheckCircle, bgColor: 'bg-emerald-50', iconColor: 'text-emerald-500' };
      case 'expired':
        return { icon: Timer, bgColor: 'bg-gray-50', iconColor: 'text-gray-400' };
      case 'pending':
        return { icon: Clock, bgColor: 'bg-amber-50', iconColor: 'text-amber-500' };
      default:
        // normal
        return { icon: CheckCircle, bgColor: 'bg-emerald-50', iconColor: 'text-emerald-500' };
    }
  };

  const getStatusStyle = (status) => {
    const s = status || 'normal';
    const styles = {
      normal: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      confirmed: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      approved: 'bg-emerald-50 text-emerald-600 border-emerald-100',
      suspicious: 'bg-orange-50 text-orange-600 border-orange-100',
      pending: 'bg-amber-50 text-amber-600 border-amber-100',
      fraud: 'bg-red-50 text-red-600 border-red-100',
      cancelled: 'bg-slate-50 text-slate-500 border-slate-100',
      denied: 'bg-slate-50 text-slate-500 border-slate-100',
      expired: 'bg-gray-50 text-gray-500 border-gray-100'
    };
    return styles[s] || 'bg-gray-50 text-gray-600 border-gray-100';
  };

  const getRiskColor = (riskScore) => {
    const score = parseFloat(riskScore);
    if (score >= 0.8) return 'bg-red-50 text-red-700 border-red-100';
    if (score >= 0.5) return 'bg-orange-50 text-orange-700 border-orange-100';
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
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
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setShowSendMoney(!showSendMoney)}
            className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
          >
            <Send className="h-4 w-4" />
            <span>Send Money</span>
          </button>
          <div className="text-sm text-gray-600">
            Last updated: {new Date().toLocaleDateString()}
          </div>
        </div>
      </div>

      {/* Send Money Panel - Collapsible */}
      {showSendMoney && (
        <div className="animate-in slide-in-from-top duration-200">
          <SendMoney 
            compact={true}
            onSuccess={() => {
              refreshData();
              // Optionally close after success: setShowSendMoney(false);
            }}
            onClose={() => setShowSendMoney(false)}
          />
        </div>
      )}

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Balance</p>
              <p className="text-2xl font-bold text-gray-900">
                ${dashboardData?.totalBalance?.toFixed(2) || '0.00'}
              </p>
            </div>
            <div className="p-3 bg-green-100 rounded-full">
              <DollarSign className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Monthly Spending</p>
              <p className="text-2xl font-bold text-gray-900">
                ${dashboardData?.monthlySpending?.toFixed(2) || '0.00'}
              </p>
            </div>
            <div className="p-3 bg-red-100 rounded-full">
              <TrendingUp className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Active Budgets</p>
              <p className="text-2xl font-bold text-gray-900">{budgets.length}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-full">
              <Target className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>

        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Budget Usage</p>
              <p className="text-2xl font-bold text-gray-900">{dashboardData?.budgetUsage || 0}%</p>
            </div>
            <div className={`p-3 rounded-full ${(dashboardData?.budgetUsage || 0) > 90 ? 'bg-red-100' : 'bg-green-100'}`}>
              <PieChart className={`h-6 w-6 ${(dashboardData?.budgetUsage || 0) > 90 ? 'text-red-600' : 'text-green-600'}`} />
            </div>
          </div>
        </div>
      </div>

      {/* Budget Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Budget Overview</h2>
          <div className="space-y-4">
            {budgets.slice(0, 3).map((budget) => (
              <div key={budget.id} className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <BudgetDonutChart budget={budget} />
                  <div>
                    <p className="font-medium text-gray-900">{budget.name}</p>
                    <p className="text-sm text-gray-600">
                      ${budget.spent.toFixed(2)} of ${budget.limit.toFixed(2)}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">
                    ${(budget.limit - budget.spent).toFixed(2)} left
                  </p>
                  <p className="text-xs text-gray-500">
                    {((budget.spent / budget.limit) * 100).toFixed(0)}% used
                  </p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t">
            <Link
              to="/budgets"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              View all budgets →
            </Link>
          </div>
        </div>

        {/* AI Insights */}
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">AI Insights</h2>
            <button 
              onClick={handleRefreshTips}
              className="p-1 hover:bg-gray-100 rounded-full transition-colors text-gray-500"
              title="Get new tips"
            >
              <RefreshCw className={`h-4 w-4 ${tipsLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="space-y-4">
            {insights.slice(0, 3).map((insight, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className={`p-2 rounded-full ${
                  insight.type === 'warning' ? 'bg-yellow-100' : 
                  insight.type === 'alert' ? 'bg-red-100' : 'bg-blue-100'
                }`}>
                  <AlertTriangle className={`h-4 w-4 ${
                    insight.type === 'warning' ? 'text-yellow-600' : 
                    insight.type === 'alert' ? 'text-red-600' : 'text-blue-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{insight.title}</p>
                  <p className="text-sm text-gray-600">{insight.description}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t">
            <Link
              to="/chat"
              className="text-blue-600 hover:text-blue-700 text-sm font-medium"
            >
              Chat with AI for more insights →
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Recent Transactions</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {dashboardData?.recentTransactions?.map((transaction) => {
            const statusIconInfo = getStatusIcon(transaction.status, transaction.amount);
            const IconComponent = statusIconInfo?.icon || CreditCard;
            const bgColor = statusIconInfo?.bgColor || 'bg-gray-100';
            const iconColor = statusIconInfo?.iconColor || 'text-gray-600';

            return (
            <div key={transaction.id} className="p-4 hover:bg-gray-50 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-3">
                  <div className={`p-2 rounded-full ${bgColor} mt-0.5`}>
                    <IconComponent className={`h-4 w-4 ${iconColor}`} />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                       <p className="font-semibold text-gray-800 text-sm">{transaction.description}</p>
                       <span className={`px-1 rounded text-[8px] uppercase font-bold tracking-tight ${
                         transaction.transactionType === 'debit' ? 'bg-amber-50 text-amber-600 border border-amber-100' : 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                       }`}>
                         {transaction.transactionType}
                       </span>
                    </div>
                    <p className="text-[11px] text-gray-400 mt-0.5">
                      {new Date(transaction.date).toLocaleDateString()} • {transaction.category || 'Other'}
                    </p>
                    
                    {/* Show reasons as small blocks if any */}
                    {transaction.status && transaction.status !== 'normal' && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                           {Array.isArray(transaction.anomalyReasons) && transaction.anomalyReasons.length > 0 ? (
                             transaction.anomalyReasons.map((reason, i) => (
                               <span key={i} className="px-1.5 py-0.5 bg-red-50 text-red-500 border border-red-100 rounded text-[9px] font-medium uppercase">
                                 {String(reason)}
                               </span>
                             ))
                           ) : (
                            <span className={`px-1.5 py-0.5 border rounded text-[9px] font-medium uppercase tracking-wider ${getStatusStyle(transaction.status)}`}>
                              {transaction.status}
                            </span>
                           )}
                           
                           {transaction.riskScore !== undefined && (
                             <div className={`px-1.5 py-0.5 rounded border text-[9px] font-medium ${getRiskColor(transaction.riskScore)}`}>
                               RISK: {(Number(transaction.riskScore) * (transaction.riskScore <= 1 ? 100 : 1)).toFixed(0)}%
                             </div>
                           )}
                        </div>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <p className={`font-semibold text-sm ${
                    transaction.amount > 0 ? 'text-emerald-600' : 'text-red-600'
                  }`}>
                    {transaction.amount > 0 ? '+' : '-'}${Math.abs(transaction.amount).toFixed(2)}
                  </p>
                  <p className="text-[9px] font-mono text-gray-300 mt-0.5 uppercase">ID: {transaction.id.substring(0, 8)}</p>
                </div>
              </div>
            </div>
          );})}
        </div>
        <div className="px-6 py-4 border-t border-gray-200">
          <Link
            to="/transactions"
            className="text-blue-600 hover:text-blue-700 text-sm font-bold flex items-center space-x-2 transition-all group"
          >
            <span>View all transactions</span>
            <span className="group-hover:translate-x-1 transition-transform">→</span>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;