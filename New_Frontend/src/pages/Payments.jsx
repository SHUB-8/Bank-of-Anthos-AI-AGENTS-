import React, { useState } from 'react';
import SendMoney from '../components/SendMoney.jsx';
import DepositMoney from '../components/DepositMoney.jsx';

const Payments = () => {
  const [activeTab, setActiveTab] = useState('send');

  const handlePaymentSuccess = (result) => {
    console.log('Transaction successful:', result);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Payments & Transfers</h1>
      </div>

      <div className="bg-white rounded-lg shadow-sm border p-6">
        <div className="max-w-xl mx-auto">
          {/* Tabs */}
          <div className="border-b border-gray-200 mb-6">
            <nav className="-mb-px flex space-x-8" aria-label="Tabs">
              <button
                onClick={() => setActiveTab('send')}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                  ${activeTab === 'send'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}
                `}
              >
                Send Money
              </button>
              <button
                onClick={() => setActiveTab('deposit')}
                className={`
                  whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm
                  ${activeTab === 'deposit'
                    ? 'border-green-500 text-green-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}
                `}
              >
                Deposit Funds
              </button>
            </nav>
          </div>

          {/* Content */}
          {activeTab === 'send' ? (
            <SendMoney onSuccess={handlePaymentSuccess} />
          ) : (
            <DepositMoney onSuccess={handlePaymentSuccess} />
          )}
        </div>
      </div>
    </div>
  );
};

export default Payments;
