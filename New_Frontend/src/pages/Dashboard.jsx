import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { moneySageAPI, transactionAPI } from '../api/ai_agents.js';
import { BudgetDonutChart } from '../components/BudgetChart.jsx';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import { AlertTriangle, TrendingUp, Shield, DollarSign, Target } from 'lucide-react';

const Dashboard = () => {
  const [dashboardData, setDashboardData] = useState(null);
  const [budgets, setBudgets] = useState([]);
  const [insights, setInsights] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDashboardData = async () => {
      setLoading(true);
      try {
        const [budgetData, tipsData, transactionData] = await Promise.all([
          moneySageAPI.getBudgets(),
          moneySageAPI.getTips(),
          transactionAPI.getTransactions(10)
        ]);

        setBudgets(budgetData);
        setInsights(tipsData.map((tip, index) => ({
          title: `Financial Tip ${index + 1}`,
          description: tip,
          type: 'info'
        })));
        setDashboardData({
          totalBalance: transactionData.reduce((sum, t) => sum + t.amount, 0),
          monthlySpending: transactionData
            .filter(t => t.amount < 0)
            .reduce((sum, t) => sum + Math.abs(t.amount), 0),
          recentTransactions: transactionData.slice(0, 5)
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
        <div className="text-sm text-gray-600">
          Last updated: {new Date().toLocaleDateString()}
        </div>
      </div>

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
              <p className="text-sm font-medium text-gray-600">Security Score</p>
              <p className="text-2xl font-bold text-gray-900">95%</p>
            </div>
            <div className="p-3 bg-green-100 rounded-full">
              <Shield className="h-6 w-6 text-green-600" />
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
          <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Insights</h2>
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
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Recent Transactions</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {dashboardData?.recentTransactions?.map((transaction) => (
            <div key={transaction.id} className="p-6 hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className={`p-2 rounded-full ${
                    transaction.amount > 0 ? 'bg-green-100' : 'bg-red-100'
                  }`}>
                    <DollarSign className={`h-5 w-5 ${
                      transaction.amount > 0 ? 'text-green-600' : 'text-red-600'
                    }`} />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">{transaction.description}</p>
                    <p className="text-sm text-gray-600">
                      {new Date(transaction.date).toLocaleDateString()} • {transaction.category}
                    </p>
                  </div>
                </div>
                <span className={`font-semibold ${
                  transaction.amount > 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {transaction.amount > 0 ? '+' : ''}${Math.abs(transaction.amount).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
        <div className="px-6 py-4 border-t border-gray-200">
          <Link
            to="/transactions"
            className="text-blue-600 hover:text-blue-700 text-sm font-medium"
          >
            View all transactions →
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;