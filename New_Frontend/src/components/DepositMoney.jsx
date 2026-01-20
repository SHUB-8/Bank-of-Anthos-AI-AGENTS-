import React, { useState, useEffect } from 'react';
import { transactionAPI, contactSageAPI } from '../api/ai_agents.js';
import { Download, Building, DollarSign, FileText, AlertCircle, CheckCircle, UserPlus } from 'lucide-react';

const DepositMoney = ({ onSuccess, compact = false }) => {
  const [formData, setFormData] = useState({
    externalAccountNumber: '',
    externalRoutingNumber: '',
    amount: '',
    description: ''
  });
  const [contacts, setContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(''); // '' = none, 'new' = new, or json string
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    const fetchContacts = async () => {
      try {
        const data = await contactSageAPI.getContacts();
        // Filter only external contacts as per legacy behavior
        const external = data.filter(c => c.isExternal);
        setContacts(external);
        // Default to first contact if available, or 'new'
        if (external.length > 0) {
           const first = external[0];
           const val = JSON.stringify({acc: first.accountNumber, rout: first.routingNumber});
           setSelectedContact(val);
           setFormData(prev => ({
             ...prev, 
             externalAccountNumber: first.accountNumber,
             externalRoutingNumber: first.routingNumber
           }));
        } else {
           setSelectedContact('new');
        }
      } catch (err) {
        console.error("Failed to load contacts", err);
        setSelectedContact('new');
      }
    };
    fetchContacts();
  }, []);

  const handleContactChange = (e) => {
    const val = e.target.value;
    setSelectedContact(val);
    if (val === 'new') {
      setFormData(prev => ({ ...prev, externalAccountNumber: '', externalRoutingNumber: '' }));
    } else {
      try {
        const parsed = JSON.parse(val);
        setFormData(prev => ({ ...prev, externalAccountNumber: parsed.acc, externalRoutingNumber: parsed.rout }));
      } catch (e) {
        // ignore
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const result = await transactionAPI.depositMoney({
        externalAccountNumber: formData.externalAccountNumber,
        externalRoutingNumber: formData.externalRoutingNumber,
        amount: parseFloat(formData.amount),
        description: formData.description
      });

      setSuccess(`Deposit of $${formData.amount} initiated successfully!`);
      
      // Reset form
      setFormData({
        externalAccountNumber: '',
        externalRoutingNumber: '',
        amount: '',
        description: ''
      });

      if (onSuccess) {
        onSuccess(result);
      }
    } catch (err) {
      setError(err.message || 'Failed to initiate deposit. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`bg-white rounded-lg shadow-sm border ${compact ? 'p-4' : 'p-6'}`}>
      <div className="flex items-center space-x-2 mb-4">
        <div className="p-2 bg-green-100 rounded-full">
          <Download className="h-5 w-5 text-green-600" />
        </div>
        <h2 className={`font-semibold text-gray-900 ${compact ? 'text-base' : 'text-lg'}`}>
          Deposit Money
        </h2>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 text-sm rounded-md flex items-start">
          <AlertCircle className="h-5 w-5 mr-2 flex-shrink-0" />
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-50 text-green-700 text-sm rounded-md flex items-start">
          <CheckCircle className="h-5 w-5 mr-2 flex-shrink-0" />
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Source Account (External) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            From External Account
          </label>
          
          {/* Contact Dropdown */}
          <div className="mb-3 relative">
            <select
               value={selectedContact}
               onChange={handleContactChange}
               className="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
            >
              <option disabled value="">Select an account...</option>
              {contacts.map(c => (
                <option key={c.id} value={JSON.stringify({acc: c.accountNumber, rout: c.routingNumber})}>
                  {c.name} - {c.accountNumber} - {c.routingNumber}
                </option>
              ))}
              <option disabled>──────────</option>
              <option value="new">New External Account</option>
            </select>
          </div>

          {/* Manual Inputs - Only if 'new' is selected */}
          {selectedContact === 'new' && (
          <div className="grid grid-cols-2 gap-4">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Building className="h-4 w-4 text-gray-400" />
              </div>
              <input
                type="text"
                value={formData.externalRoutingNumber}
                onChange={(e) => setFormData({...formData, externalRoutingNumber: e.target.value})}
                className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
                placeholder="Routing Number"
                required={selectedContact === 'new'}
              />
            </div>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Building className="h-4 w-4 text-gray-400" />
              </div>
              <input
                type="text"
                value={formData.externalAccountNumber}
                onChange={(e) => setFormData({...formData, externalAccountNumber: e.target.value})}
                className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
                placeholder="Account Number"
                required={selectedContact === 'new'}
              />
            </div>
            <p className="col-span-2 mt-1 text-xs text-gray-500">Provide details of your external bank account.</p>
          </div>
          )}
        </div>

        {/* Amount */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Amount
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <DollarSign className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={formData.amount}
              onChange={(e) => setFormData({...formData, amount: e.target.value})}
              className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
              placeholder="0.00"
              required
            />
          </div>
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Description (Optional)
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <FileText className="h-4 w-4 text-gray-400" />
            </div>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
              placeholder="e.g. Salary, Refund"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full text-white bg-green-600 hover:bg-green-700 focus:ring-4 focus:ring-green-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center flex items-center justify-center space-x-2 disabled:opacity-50"
        >
          {loading ? (
            <span>Processing...</span>
          ) : (
            <>
              <Download className="w-4 h-4" />
              <span>Deposit Funds</span>
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default DepositMoney;
