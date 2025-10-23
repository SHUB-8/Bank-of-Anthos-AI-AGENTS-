import React, { useState, useEffect } from 'react';
import { moneySageAPI } from '../api/ai_agents.js';
import { BudgetBarChart } from '../components/BudgetChart.jsx';
import Modal from '../components/Modal.jsx';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import { Plus, Edit3, Trash2, Target, TrendingUp } from 'lucide-react';

const Budgets = () => {
  const [budgets, setBudgets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBudget, setEditingBudget] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    limit: '',
    category: '',
    color: '#3B82F6'
  });

  const categories = [
    'Food', 'Transportation', 'Entertainment', 'Utilities', 'Healthcare',
    'Shopping', 'Education', 'Travel', 'Insurance', 'Other'
  ];

  const colors = [
    '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#06B6D4', '#84CC16', '#F97316', '#EC4899', '#6B7280'
  ];

  useEffect(() => {
    fetchBudgets();
  }, []);

  const fetchBudgets = async () => {
    try {
      const data = await moneySageAPI.getBudgets();
      setBudgets(data);
    } catch (error) {
      console.error('Failed to fetch budgets:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBudget = () => {
    setEditingBudget(null);
    setFormData({ name: '', limit: '', category: '', color: '#3B82F6' });
    setModalOpen(true);
  };

  const handleEditBudget = (budget) => {
    setEditingBudget(budget);
    setFormData({
      name: budget.name,
      limit: budget.limit.toString(),
      category: budget.category,
      color: budget.color
    });
    setModalOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const budgetData = {
        name: formData.name,
        limit: parseFloat(formData.limit),
        category: formData.category,
        color: formData.color,
        spent: editingBudget ? editingBudget.spent : 0
      };

      if (editingBudget) {
        const updatedBudget = await moneySageAPI.updateBudget(editingBudget.id, budgetData);
        setBudgets(prev => prev.map(b => b.id === editingBudget.id ? updatedBudget : b));
      } else {
        const newBudget = await moneySageAPI.createBudget(budgetData);
        setBudgets(prev => [...prev, newBudget]);
      }

      setModalOpen(false);
      setFormData({ name: '', limit: '', category: '', color: '#3B82F6' });
    } catch (error) {
      console.error('Failed to save budget:', error);
    }
  };

  const handleDeleteBudget = async (budgetId) => {
    if (window.confirm('Are you sure you want to delete this budget?')) {
      try {
        await moneySageAPI.deleteBudget(budgetId);
        setBudgets(prev => prev.filter(b => b.id !== budgetId));
      } catch (error) {
        console.error('Failed to delete budget:', error);
      }
    }
  };

  const getBudgetStatus = (spent, limit) => {
    const percentage = (spent / limit) * 100;
    if (percentage < 60) return { status: 'On Track', color: 'text-green-600', bg: 'bg-green-50' };
    if (percentage < 80) return { status: 'Watch Out', color: 'text-yellow-600', bg: 'bg-yellow-50' };
    return { status: 'Over Budget', color: 'text-red-600', bg: 'bg-red-50' };
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
        <h1 className="text-2xl font-bold text-gray-900">Budget Management</h1>
        <button
          onClick={handleCreateBudget}
          className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-5 w-5" />
          <span>Create Budget</span>
        </button>
      </div>

      {/* Budget Overview */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Budget Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-blue-50 p-4 rounded-lg">
            <div className="flex items-center">
              <Target className="h-8 w-8 text-blue-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-blue-600">Total Budgets</p>
                <p className="text-2xl font-bold text-blue-900">{budgets.length}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-green-50 p-4 rounded-lg">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-green-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-green-600">Total Allocated</p>
                <p className="text-2xl font-bold text-green-900">
                  ${budgets.reduce((sum, b) => sum + b.limit, 0)}
                </p>
              </div>
            </div>
          </div>
          
          <div className="bg-orange-50 p-4 rounded-lg">
            <div className="flex items-center">
              <TrendingUp className="h-8 w-8 text-orange-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-orange-600">Total Spent</p>
                <p className="text-2xl font-bold text-orange-900">
                  ${budgets.reduce((sum, b) => sum + b.spent, 0)}
                </p>
              </div>
            </div>
          </div>
        </div>
        
        {budgets.length > 0 && <BudgetBarChart budgets={budgets} />}
      </div>

      {/* Budget Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {budgets.map((budget) => {
          const percentage = (budget.spent / budget.limit) * 100;
          const remaining = budget.limit - budget.spent;
          const status = getBudgetStatus(budget.spent, budget.limit);

          return (
            <div key={budget.id} className="bg-white rounded-lg shadow-sm border p-6 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">{budget.name}</h3>
                <div className="flex space-x-2">
                  <button
                    onClick={() => handleEditBudget(budget)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDeleteBudget(budget.id)}
                    className="text-gray-400 hover:text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Spent</span>
                  <span className="font-medium">${budget.spent}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Budget</span>
                  <span className="font-medium">${budget.limit}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Remaining</span>
                  <span className={`font-medium ${remaining >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${remaining.toFixed(2)}
                  </span>
                </div>

                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${Math.min(percentage, 100)}%`,
                      backgroundColor: budget.color
                    }}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{budget.category}</span>
                  <div className={`px-2 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>
                    {status.status}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Create/Edit Budget Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingBudget ? 'Edit Budget' : 'Create New Budget'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Budget Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="e.g., Groceries, Entertainment"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Budget Limit
            </label>
            <input
              type="number"
              step="0.01"
              value={formData.limit}
              onChange={(e) => setFormData(prev => ({ ...prev, limit: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="500.00"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Category
            </label>
            <select
              value={formData.category}
              onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            >
              <option value="">Select a category</option>
              {categories.map(category => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Color
            </label>
            <div className="flex space-x-2">
              {colors.map(color => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, color }))}
                  className={`w-8 h-8 rounded-full border-2 ${
                    formData.color === color ? 'border-gray-400' : 'border-gray-200'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          <div className="flex space-x-3 pt-4">
            <button
              type="submit"
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
            >
              {editingBudget ? 'Update Budget' : 'Create Budget'}
            </button>
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              className="flex-1 bg-gray-200 text-gray-800 py-2 px-4 rounded-lg hover:bg-gray-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default Budgets;