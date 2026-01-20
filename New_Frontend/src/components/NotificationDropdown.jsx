import React, { useState, useEffect, useRef } from 'react';
import { Bell, ShieldAlert, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { databaseAPI } from '../api/database';
import { moneySageAPI } from '../api/ai_agents';

const NotificationDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const newNotifications = [];

      // 1. Fetch Security Alerts (Pending Anomalies)
      try {
        const anomalies = await databaseAPI.fetchAnomalyLogs(50, { status: 'pending' });
        const pendingAnomalies = (Array.isArray(anomalies) ? anomalies : [])
          .filter(a => a.status === 'pending' || a.status === 'suspicious');
        
        pendingAnomalies.forEach(anomaly => {
          newNotifications.push({
            id: `sec-${anomaly.log_id || anomaly.id}`,
            type: 'security',
            title: 'Action Required',
            message: `Transaction of $${anomaly.amount?.toFixed(2) || '0.00'} needs approval.`,
            timestamp: anomaly.created_at || anomaly.requested_at,
            read: false,
            link: '/transactions', 
            state: { tab: 'security' } // Pass state to navigate
          });
        });
      } catch (err) {
        console.warn('Failed to fetch security alerts:', err);
      }

      // 2. Fetch Budget Alerts
      try {
        const budgets = await moneySageAPI.getBudgets();
        (budgets || []).forEach(budget => {
          if (budget.limit > 0 && budget.spent) {
             const percentage = (budget.spent / budget.limit) * 100;
             if (percentage >= 100) {
                newNotifications.push({
                  id: `bug-${budget.id}`,
                  type: 'budget_critical',
                  title: 'Budget Exceeded',
                  message: `You have exceeded your ${budget.category} budget!`,
                  timestamp: new Date().toISOString(), // Budgets don't have "alert time" so use current
                  read: false,
                  link: '/budgets',
                  state: {}
                });
             } else if (percentage >= 80) {
                newNotifications.push({
                  id: `bug-${budget.id}`,
                  type: 'budget_warning',
                  title: 'Budget Warning',
                  message: `You have used ${percentage.toFixed(0)}% of your ${budget.category} budget.`,
                  timestamp: new Date().toISOString(),
                  read: false,
                  link: '/budgets',
                  state: {}
                });
             }
          }
        });
      } catch (err) {
        console.warn('Failed to fetch budget alerts:', err);
      }

      // Sort by timestamp if available (newest first)
      newNotifications.sort((a, b) => {
          return new Date(b.timestamp) - new Date(a.timestamp);
      });

      setNotifications(newNotifications);
      setUnreadCount(newNotifications.length);

    } catch (error) {
      console.error('Error fetching notifications:', error);
    } finally {
      setLoading(false);
    }
  };

  // Poll for notifications every 30 seconds
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleNotificationClick = (notification) => {
     setIsOpen(false);
     if (notification.link) {
         if (notification.link === '/transactions') {
             // To trigger tab switch, we might need to handle this in destination or query param
             // For now, standard navigation
             navigate(notification.link);
             // Dispatch a custom event if we need to switch tabs deeply (optional hack)
             if (notification.state?.tab === 'security') {
                window.location.hash = '#security'; // Simple hash routing for tab support
             }
         } else {
             navigate(notification.link);
         }
     }
  };

  const getIcon = (type) => {
      switch(type) {
          case 'security': return <ShieldAlert className="h-5 w-5 text-red-500" />;
          case 'budget_critical': return <AlertTriangle className="h-5 w-5 text-red-500" />;
          case 'budget_warning': return <Info className="h-5 w-5 text-amber-500" />;
          default: return <Bell className="h-5 w-5 text-blue-500" />;
      }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button 
        className="relative p-2 text-gray-400 hover:text-gray-500 hover:bg-gray-100 rounded-full transition-colors"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Notifications"
      >
        <Bell className="h-6 w-6" />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 h-2 w-2 bg-red-500 rounded-full animate-pulse"></span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-xl border border-gray-100 py-1 z-50 overflow-hidden transform origin-top-right transition-all">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
            {unreadCount > 0 && (
                <span className="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-medium">
                    {unreadCount} New
                </span>
            )}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading && notifications.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                    Loading...
                </div>
            ) : notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-400">
                    <CheckCircle className="h-8 w-8 mx-auto mb-2 opacity-50 text-green-500" />
                    <p className="text-sm">All caught up!</p>
                </div>
            ) : (
                notifications.map((note) => (
                    <div 
                        key={note.id}
                        onClick={() => handleNotificationClick(note)}
                        className="px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-50 last:border-0 transition-colors"
                    >
                        <div className="flex items-start space-x-3">
                            <div className="flex-shrink-0 mt-0.5">
                                {getIcon(note.type)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                    {note.title}
                                </p>
                                <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                                    {note.message}
                                </p>
                                <p className="text-[10px] text-gray-400 mt-1">
                                    {new Date(note.timestamp).toLocaleString()}
                                </p>
                            </div>
                        </div>
                    </div>
                ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default NotificationDropdown;
