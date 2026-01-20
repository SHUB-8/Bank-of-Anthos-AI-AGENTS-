import React, { useState, useEffect } from 'react';
import { contactSageAPI } from '../api/ai_agents.js';
import Modal from '../components/Modal.jsx';
import LoadingSpinner from '../components/LoadingSpinner.jsx';
import { Search, Plus, Edit3, Trash2, User, ExternalLink, Mail, Phone, CreditCard, AlertCircle } from 'lucide-react';

const Contacts = () => {
  const [contacts, setContacts] = useState([]);
  const [filteredContacts, setFilteredContacts] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState(null);
  const [formError, setFormError] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    accountNumber: '',
    routingNumber: '',
    email: '',
    phone: '',
    isExternal: false
  });

  useEffect(() => {
    fetchContacts();
  }, []);

  useEffect(() => {
    handleSearch(searchQuery);
  }, [searchQuery, contacts]);

  const fetchContacts = async () => {
    try {
      const data = await contactSageAPI.getContacts();
      setContacts(data);
    } catch (error) {
      console.error('Failed to fetch contacts:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (query) => {
    if (!query.trim()) {
      setFilteredContacts(contacts);
      return;
    }

    try {
      // Pass all contacts as fallback for local filtering
      const results = await contactSageAPI.fuzzySearch(query, contacts);
      setFilteredContacts(results.length > 0 ? results : contacts.filter(contact =>
        contact.name.toLowerCase().includes(query.toLowerCase()) ||
        (contact.email && contact.email.toLowerCase().includes(query.toLowerCase())) ||
        (contact.accountNumber && contact.accountNumber.includes(query))
      ));
    } catch (error) {
      console.error('Search failed:', error);
      // Fallback to local filtering
      const filtered = contacts.filter(contact =>
        contact.name.toLowerCase().includes(query.toLowerCase()) ||
        (contact.email && contact.email.toLowerCase().includes(query.toLowerCase())) ||
        (contact.accountNumber && contact.accountNumber.includes(query))
      );
      setFilteredContacts(filtered);
    }
  };

  const handleCreateContact = () => {
    setEditingContact(null);
    setFormError('');
    setFormData({ name: '', accountNumber: '', routingNumber: '', email: '', phone: '', isExternal: false });
    setModalOpen(true);
  };

  const handleEditContact = (contact) => {
    setEditingContact(contact);
    setFormError('');
    setFormData({
      name: contact.name,
      accountNumber: contact.accountNumber || '',
      routingNumber: contact.routingNumber || '',
      email: contact.email || '',
      phone: contact.phone || '',
      isExternal: contact.isExternal
    });
    setModalOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    
    try {
      if (editingContact) {
        const updatedContact = await contactSageAPI.updateContact(editingContact.id, formData);
        setContacts(prev => prev.map(c => c.id === editingContact.id ? updatedContact : c));
      } else {
        const newContact = await contactSageAPI.createContact(formData);
        setContacts(prev => [...prev, newContact]);
      }

      setModalOpen(false);
      setFormData({ name: '', accountNumber: '', routingNumber: '', email: '', phone: '', isExternal: false });
    } catch (error) {
      console.error('Failed to save contact:', error);
      setFormError(error.message || 'Failed to save contact. Please check your inputs.');
    }
  };

  const handleDeleteContact = async (contactId) => {
    if (window.confirm('Are you sure you want to delete this contact?')) {
      try {
        await contactSageAPI.deleteContact(contactId);
        setContacts(prev => prev.filter(c => c.id !== contactId));
      } catch (error) {
        console.error('Failed to delete contact:', error);
      }
    }
  };

  const validateEmail = (email) => {
    return email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/);
  };

  const validatePhone = (phone) => {
    return phone.match(/^[\+]?[1-9][\d]{0,15}$/);
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
        <h1 className="text-2xl font-bold text-gray-900">Contact Management</h1>
        <button
          onClick={handleCreateContact}
          className="flex items-center space-x-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="h-5 w-5" />
          <span>Add Contact</span>
        </button>
      </div>

      {/* Search Bar */}
      <div className="bg-white rounded-lg shadow-sm border p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
          <input
            type="text"
            placeholder="Search contacts by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        {searchQuery && (
          <div className="mt-2 text-sm text-gray-600">
            Found {filteredContacts.length} contact{filteredContacts.length !== 1 ? 's' : ''} matching "{searchQuery}"
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <User className="h-8 w-8 text-blue-600 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-600">Total Contacts</p>
              <p className="text-2xl font-bold text-gray-900">{contacts.length}</p>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <ExternalLink className="h-8 w-8 text-green-600 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-600">Internal Contacts</p>
              <p className="text-2xl font-bold text-gray-900">
                {contacts.filter(c => !c.isExternal).length}
              </p>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-sm border">
          <div className="flex items-center">
            <ExternalLink className="h-8 w-8 text-orange-600 mr-3" />
            <div>
              <p className="text-sm font-medium text-gray-600">External Contacts</p>
              <p className="text-2xl font-bold text-gray-900">
                {contacts.filter(c => c.isExternal).length}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Contacts Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {(searchQuery ? filteredContacts : contacts).map((contact) => (
          <div key={contact.id} className="bg-white rounded-lg shadow-sm border p-6 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className={`p-2 rounded-full ${contact.isExternal ? 'bg-orange-100' : 'bg-blue-100'}`}>
                  <User className={`h-6 w-6 ${contact.isExternal ? 'text-orange-600' : 'text-blue-600'}`} />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{contact.name}</h3>
                  <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    contact.isExternal 
                      ? 'bg-orange-50 text-orange-700' 
                      : 'bg-blue-50 text-blue-700'
                  }`}>
                    {contact.isExternal ? (
                      <>
                        <ExternalLink className="h-3 w-3 mr-1" />
                        External
                      </>
                    ) : (
                      'Internal'
                    )}
                  </div>
                </div>
              </div>
              
              <div className="flex space-x-2">
                <button
                  onClick={() => handleEditContact(contact)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Edit3 className="h-4 w-4" />
                </button>
                <button
                  onClick={() => handleDeleteContact(contact.id)}
                  className="text-gray-400 hover:text-red-600"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center space-x-3 text-sm text-gray-600">
                <CreditCard className="h-4 w-4" />
                <span className="font-mono">
                  Account: {contact.accountNumber || 'N/A'}
                </span>
              </div>
              
              {contact.email && (
                <div className="flex items-center space-x-3 text-sm text-gray-600">
                  <Mail className="h-4 w-4" />
                  <a href={`mailto:${contact.email}`} className="hover:text-blue-600 truncate">
                    {contact.email}
                  </a>
                </div>
              )}
              
              {contact.phone && (
                <div className="flex items-center space-x-3 text-sm text-gray-600">
                  <Phone className="h-4 w-4" />
                  <a href={`tel:${contact.phone}`} className="hover:text-blue-600">
                    {contact.phone}
                  </a>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {(searchQuery ? filteredContacts : contacts).length === 0 && (
        <div className="text-center py-12">
          <User className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            {searchQuery ? 'No contacts found' : 'No contacts yet'}
          </h3>
          <p className="text-gray-600 mb-6">
            {searchQuery 
              ? `No contacts match "${searchQuery}". Try a different search term.`
              : 'Get started by adding your first contact.'
            }
          </p>
          {!searchQuery && (
            <button
              onClick={handleCreateContact}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
            >
              Add Your First Contact
            </button>
          )}
        </div>
      )}

      {/* Create/Edit Contact Modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title={editingContact ? 'Edit Contact' : 'Add New Contact'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <span className="text-sm">{formError}</span>
            </div>
          )}
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name / Label <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="John Doe"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Account Number <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.accountNumber}
              onChange={(e) => setFormData(prev => ({ ...prev, accountNumber: e.target.value.replace(/\D/g, '').slice(0, 10) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="1234567890"
              maxLength={10}
              pattern="\d{10}"
              required
            />
            <p className="text-xs text-gray-500 mt-1">Must be exactly 10 digits ({formData.accountNumber.length}/10)</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Routing Number
            </label>
            <input
              type="text"
              value={formData.routingNumber}
              onChange={(e) => setFormData(prev => ({ ...prev, routingNumber: e.target.value.replace(/\D/g, '').slice(0, 9) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="883745000"
              maxLength={9}
            />
            <p className="text-xs text-gray-500 mt-1">Leave empty for Bank of Anthos default (883745000). Must be 9 digits if specified.</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email (optional)
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="john@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Phone (optional)
            </label>
            <input
              type="tel"
              value={formData.phone}
              onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="+1-555-0123"
            />
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="isExternal"
              checked={formData.isExternal}
              onChange={(e) => {
                const isExt = e.target.checked;
                setFormData(prev => ({ 
                  ...prev, 
                  isExternal: isExt,
                  // Clear routing if switching to external (can't use local routing)
                  routingNumber: isExt ? (prev.routingNumber === '' || prev.routingNumber === '883745000' ? '' : prev.routingNumber) : prev.routingNumber
                }));
              }}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-2 focus:ring-blue-500"
            />
            <label htmlFor="isExternal" className="ml-2 text-sm text-gray-700">
              External contact (outside Bank of Anthos)
            </label>
          </div>
          <p className="text-xs text-gray-500">
            {formData.isExternal 
              ? "⚠️ External contacts require a different bank's routing number (not 883745000)"
              : "Internal contacts use Bank of Anthos routing (883745000)"
            }
          </p>

          <div className="flex space-x-3 pt-4">
            <button
              type="submit"
              disabled={!formData.name || !formData.accountNumber || formData.accountNumber.length !== 10}
              className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {editingContact ? 'Update Contact' : 'Add Contact'}
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

export default Contacts;