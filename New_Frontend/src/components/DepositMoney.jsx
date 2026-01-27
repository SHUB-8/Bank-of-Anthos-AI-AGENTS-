import React, { useState, useEffect } from 'react';
import { transactionAPI, contactSageAPI } from '../api/ai_agents.js';
import { Download, Building, DollarSign, FileText, AlertCircle, CheckCircle, UserPlus } from 'lucide-react';

const DepositMoney = ({ onSuccess, compact = false }) => {
  const [formData, setFormData] = useState({
    externalAccountNumber: '1234567890',
    externalRoutingNumber: '123456789',
    externalLabel: '',
    amount: '',
    description: ''
  });
  const [contacts, setContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState('new'); // Default to 'new' with prefilled values
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
        
        // If the user already has external accounts, use the first one
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
           // Otherwise keep 'new' with our prefilled values
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
      // For 'new', use the prefilled defaults
      setFormData(prev => ({ 
        ...prev, 
        externalAccountNumber: '1234567890', 
        externalRoutingNumber: '123456789',
        externalLabel: '' 
      }));
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

    // Digit constraints validation
    if (!/^\d{10}$/.test(formData.externalAccountNumber.trim())) {
      setError('Account number must be exactly 10 digits.');
      return;
    }
    if (!/^\d{9}$/.test(formData.externalRoutingNumber.trim())) {
      setError('Routing number must be exactly 9 digits.');
      return;
    }

    if (formData.externalRoutingNumber.trim() === '883745000') {
      setError('Deposits must come from an EXTERNAL routing number. 883745000 is the internal Bank of Anthos routing number.');
      return;
    }

    setLoading(true);

    try {
      // If it's a new account and a label is provided, save it as a contact first
      if (selectedContact === 'new' && formData.externalLabel.trim()) {
        try {
          await contactSageAPI.createContact({
            name: formData.externalLabel,
            accountNumber: formData.externalAccountNumber,
            routingNumber: formData.externalRoutingNumber,
            isExternal: true
          });
        } catch (contactErr) {
          console.warn('Could not save contact, but proceeding with deposit:', contactErr);
        }
      }

      const result = await transactionAPI.depositMoney({
        externalAccountNumber: formData.externalAccountNumber,
        externalRoutingNumber: formData.externalRoutingNumber,
        amount: parseFloat(formData.amount),
        description: formData.description
      });

      setSuccess(`Deposit of $${formData.amount} initiated successfully!`);
      
      // Reset amount and description
      setFormData(prev => ({
        ...prev,
        amount: '',
        description: ''
      }));

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
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Building className="h-4 w-4 text-gray-400" />
                </div>
                <input
                  type="text"
                  maxLength={9}
                  value={formData.externalRoutingNumber}
                  onChange={(e) => setFormData({...formData, externalRoutingNumber: e.target.value})}
                  className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
                  placeholder="Routing Number (9 digits)"
                  required={selectedContact === 'new'}
                />
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Building className="h-4 w-4 text-gray-400" />
                </div>
                <input
                  type="text"
                  maxLength={10}
                  value={formData.externalAccountNumber}
                  onChange={(e) => setFormData({...formData, externalAccountNumber: e.target.value})}
                  className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
                  placeholder="Account Number (10 digits)"
                  required={selectedContact === 'new'}
                />
              </div>
            </div>
            
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <UserPlus className="h-4 w-4 text-gray-400" />
              </div>
              <input
                type="text"
                value={formData.externalLabel}
                onChange={(e) => setFormData({...formData, externalLabel: e.target.value})}
                className="pl-9 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
                placeholder="Account Label (e.g. My External Bank) - optional"
              />
              <p className="mt-1 text-xs text-gray-600 italic">Providing a label will save this account for future deposits.</p>
            </div>
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
