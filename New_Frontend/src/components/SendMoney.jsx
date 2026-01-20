import React, { useState, useEffect } from 'react';
import { transactionAPI, contactSageAPI } from '../api/ai_agents.js';
import { Send, User, DollarSign, FileText, AlertCircle, CheckCircle, ChevronDown, X } from 'lucide-react';

const SendMoney = ({ onSuccess, onClose, compact = false }) => {
  const [contacts, setContacts] = useState([]);
  const [formData, setFormData] = useState({
    recipientType: 'contact', // 'contact' or 'manual'
    selectedContact: '',
    recipientAccountNumber: '',
    recipientRoutingNumber: '',
    amount: '',
    description: '',
    category: 'Other'
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showContactDropdown, setShowContactDropdown] = useState(false);

  // Category options for better transaction categorization
  const categories = [
    'Housing', 'Dining', 'Groceries', 'Transport', 'Travel', 
    'Utilities', 'Telecom', 'Healthcare', 'Entertainment', 'Education', 
    'Insurance', 'Services', 'Subscription', 'Shopping', 'Transfer', 
    'Taxes', 'Charity', 'Other'
  ];

  useEffect(() => {
    fetchContacts();
  }, []);

  const fetchContacts = async () => {
    try {
      const data = await contactSageAPI.getContacts();
      setContacts(data);
    } catch (err) {
      console.error('Failed to fetch contacts:', err);
    }
  };

  const handleContactSelect = (contact) => {
    setFormData(prev => ({
      ...prev,
      selectedContact: contact.name,
      recipientAccountNumber: contact.accountNumber,
      recipientRoutingNumber: contact.routingNumber || '883745000'
    }));
    setShowContactDropdown(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const result = await transactionAPI.sendMoney({
        recipientAccountNumber: formData.recipientAccountNumber,
        recipientRoutingNumber: formData.recipientRoutingNumber || '883745000',
        amount: parseFloat(formData.amount),
        description: formData.description,
        category: formData.category,
        isExternal: formData.recipientRoutingNumber && formData.recipientRoutingNumber !== '883745000'
      });

      setSuccess(`Payment of $${formData.amount} sent successfully!`);
      
      // Reset form
      setFormData({
        recipientType: 'contact',
        selectedContact: '',
        recipientAccountNumber: '',
        recipientRoutingNumber: '',
        amount: '',
        description: '',
        category: 'Other'
      });

      if (onSuccess) {
        onSuccess(result);
      }
    } catch (err) {
      setError(err.message || 'Failed to send payment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${compact ? 'p-4' : 'p-6'}`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-blue-100 rounded-full">
            <Send className="h-5 w-5 text-blue-600" />
          </div>
          <h2 className={`font-semibold text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
            Send Money
          </h2>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        )}
      </div>

      {/* Success Message */}
      {success && (
        <div className="mb-4 flex items-center space-x-2 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700">
          <CheckCircle className="h-5 w-5 flex-shrink-0" />
          <span className="text-sm">{success}</span>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-4 flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Recipient Type Toggle */}
        <div className="flex space-x-2">
          <button
            type="button"
            onClick={() => setFormData(prev => ({ ...prev, recipientType: 'contact', recipientAccountNumber: '', recipientRoutingNumber: '', selectedContact: '' }))}
            className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors ${
              formData.recipientType === 'contact'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Pay Contact
          </button>
          <button
            type="button"
            onClick={() => setFormData(prev => ({ ...prev, recipientType: 'manual', selectedContact: '' }))}
            className={`flex-1 py-2 px-3 text-sm font-medium rounded-lg transition-colors ${
              formData.recipientType === 'manual'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            Enter Account
          </button>
        </div>

        {/* Contact Selection */}
        {formData.recipientType === 'contact' && (
          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Select Contact
            </label>
            <button
              type="button"
              onClick={() => setShowContactDropdown(!showContactDropdown)}
              className="w-full flex items-center justify-between px-3 py-2 border border-gray-300 rounded-lg bg-white text-left focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <div className="flex items-center space-x-2">
                <User className="h-4 w-4 text-gray-400" />
                <span className={formData.selectedContact ? 'text-gray-900' : 'text-gray-400'}>
                  {formData.selectedContact || 'Choose a contact...'}
                </span>
              </div>
              <ChevronDown className="h-4 w-4 text-gray-400" />
            </button>
            
            {showContactDropdown && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
                {contacts.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500 text-center">
                    No contacts found. Add contacts first.
                  </div>
                ) : (
                  contacts.map((contact) => (
                    <button
                      key={contact.id || contact.name}
                      type="button"
                      onClick={() => handleContactSelect(contact)}
                      className="w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                    >
                      <div>
                        <div className="font-medium text-gray-900">{contact.name}</div>
                        <div className="text-xs text-gray-500">
                          Acct: {contact.accountNumber}
                        </div>
                      </div>
                      {contact.isExternal && (
                        <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">
                          External
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {/* Manual Account Entry */}
        {formData.recipientType === 'manual' && (
          <>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Recipient Account Number
              </label>
              <input
                type="text"
                value={formData.recipientAccountNumber}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  recipientAccountNumber: e.target.value.replace(/\D/g, '').slice(0, 10)
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="10-digit account number"
                maxLength={10}
                required
              />
              <p className="text-xs text-gray-500 mt-1">{formData.recipientAccountNumber.length}/10 digits</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Routing Number (optional)
              </label>
              <input
                type="text"
                value={formData.recipientRoutingNumber}
                onChange={(e) => setFormData(prev => ({ 
                  ...prev, 
                  recipientRoutingNumber: e.target.value.replace(/\D/g, '').slice(0, 9)
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="883745000 (Bank of Anthos default)"
                maxLength={9}
              />
              <p className="text-xs text-gray-500 mt-1">Leave empty for Bank of Anthos transfers</p>
            </div>
          </>
        )}

        {/* Amount */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Amount
          </label>
          <div className="relative">
            <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={formData.amount}
              onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
              className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="0.00"
              required
            />
          </div>
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Category
          </label>
          <select
            value={formData.category}
            onChange={(e) => setFormData(prev => ({ ...prev, category: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description
          </label>
          <div className="relative">
            <FileText className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="What's this payment for? (Optional)"
              rows={2}
            />
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || !formData.recipientAccountNumber || !formData.amount}
          className="w-full flex items-center justify-center space-x-2 bg-blue-600 text-white py-2.5 px-4 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <>
              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
              <span>Processing...</span>
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              <span>Send ${formData.amount || '0.00'}</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default SendMoney;
