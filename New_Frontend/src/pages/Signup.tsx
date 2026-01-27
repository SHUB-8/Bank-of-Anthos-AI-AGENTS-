/**
 * Signup Page Component
 * 
 * Provides user registration interface matching the Bank of Anthos design.
 * Collects required user information for the userservice backend.
 */

import React, { useState } from 'react';
import { Navigate, Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { SignupData } from '../services/authService';

const Signup: React.FC = () => {
  const navigate = useNavigate();
  const { signup, login, isAuthenticated } = useAuth();
  
  const [formData, setFormData] = useState<SignupData>({
    username: '',
    password: '',
    'password-repeat': '',
    firstname: '',
    lastname: '',
    birthday: '',
    timezone: '-5',
    address: '',
    state: '',
    zip: '',
    ssn: '',
  });

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Redirect if already authenticated
  if (isAuthenticated && !success) {
    return <Navigate to="/" replace />;
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Basic validation
    if (formData.password !== formData['password-repeat']) {
      setError('Passwords do not match');
      return;
    }

    // SSN validation (9 digits)
    const cleanSSN = formData.ssn.replace(/\D/g, '');
    if (cleanSSN.length !== 9) {
      setError('SSN must be exactly 9 digits');
      return;
    }

    setIsLoading(true);

    try {
      await signup(formData);
      setSuccess(true);
      
      // Auto-login after signup (matching old frontend behavior)
      try {
        await login({ 
          username: formData.username, 
          password: formData.password 
        });
      } catch (loginErr) {
        console.error('Auto-login failed:', loginErr);
        // If auto-login fails, still show success but don't redirect to dashboard automatically
        setTimeout(() => navigate('/login'), 2000);
      }
    } catch (err: any) {
      setError(err.message || 'Signup failed. Please try again.');
      console.error('Signup error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-lg shadow-md text-center">
          <div className="mx-auto h-12 w-12 text-green-500">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Account Created!</h2>
          <p className="mt-2 text-gray-600">Your account has been successfully created. Logging you in...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto space-y-8 bg-white p-8 rounded-xl shadow-lg border border-gray-100">
        <div>
          <div className="mx-auto h-10 w-auto flex items-center justify-center">
            <h1 className="text-2xl font-bold text-blue-600">Bank of Anthos</h1>
          </div>
          <h2 className="mt-4 text-center text-3xl font-extrabold text-gray-900">
            Create your account
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Join thousands of users managing their finances with ease
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-8">
            {/* Account Information */}
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-900 border-b pb-2">Account Information</h3>
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Username</label>
                  <input
                    name="username"
                    type="text"
                    required
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="Choose a username"
                    value={formData.username}
                    onChange={handleChange}
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Password</label>
                    <input
                      name="password"
                      type="password"
                      required
                      className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="••••••••"
                      value={formData.password}
                      onChange={handleChange}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Confirm Password</label>
                    <input
                      name="password-repeat"
                      type="password"
                      required
                      className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                      placeholder="••••••••"
                      value={formData['password-repeat']}
                      onChange={handleChange}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Personal Information */}
            <div className="space-y-4">
              <div className="flex justify-between items-end border-b pb-2">
                <h3 className="text-xl font-bold text-gray-900">Personal Information</h3>
                <span className="text-xs text-gray-500 mb-1 italic">Some fields are read-only for security purposes</span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">First Name</label>
                  <input
                    name="firstname"
                    type="text"
                    required
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    value={formData.firstname}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Last Name</label>
                  <input
                    name="lastname"
                    type="text"
                    required
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    value={formData.lastname}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Birthday</label>
                  <input
                    name="birthday"
                    type="date"
                    required
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    value={formData.birthday}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">Timezone</label>
                  <select
                    name="timezone"
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    value={formData.timezone}
                    onChange={handleChange}
                  >
                    <option value="-8">Pacific Time (US & Canada)</option>
                    <option value="-7">Mountain Time (US & Canada)</option>
                    <option value="-6">Central Time (US & Canada)</option>
                    <option value="-5">Eastern Time (US & Canada)</option>
                    <option value="0">UTC</option>
                  </select>
                </div>
              </div>
            </div>
            {/* Contact & Legal Information */}
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-900 border-b pb-2">Address & Identification</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700">Street Address</label>
                  <input
                    name="address"
                    type="text"
                    required
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="123 Main St"
                    value={formData.address}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">State</label>
                  <input
                    name="state"
                    type="text"
                    required
                    maxLength={2}
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="NY"
                    value={formData.state}
                    onChange={handleChange}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">ZIP Code</label>
                  <input
                    name="zip"
                    type="text"
                    required
                    maxLength={5}
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    placeholder="10001"
                    value={formData.zip}
                    onChange={handleChange}
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700">Social Security Number (SSN)</label>
                  <input
                    name="ssn"
                    type="text"
                    required
                    placeholder="AAA-GG-SSSS"
                    className="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    value={formData.ssn}
                    onChange={handleChange}
                  />
                  <p className="mt-1 text-xs text-gray-500">SSN is used for identity verification.</p>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="text-sm text-red-700">{error}</div>
            </div>
          )}

          <div className="flex flex-col space-y-4">
            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center py-3 px-4 border border-transparent text-sm font-bold rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition-colors"
            >
              {isLoading ? (
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Creating Account...
                </div>
              ) : (
                'Create Account'
              )}
            </button>
            <div className="text-center text-sm">
              <span className="text-gray-600">Already have an account? </span>
              <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
                Sign in
              </Link>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Signup;
