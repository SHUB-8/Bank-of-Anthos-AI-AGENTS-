import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Clock, Plus, MessageSquare, ChevronRight, Trash2 } from 'lucide-react';
import { orchestratorAPI } from '../api/ai_agents.js';
import LoadingSpinner from '../components/LoadingSpinner.jsx';

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const messagesEndRef = useRef(null);
  
  const faqs = [
    "What is my current balance?",
    "Show my recent transactions",
    "How much did I spend on Dining?",
    "Create a budget for Groceries",
    "Send $50 to Alice"
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);
  
  useEffect(() => {
    loadSessions();
    const storedSession = localStorage.getItem('boa_session_id');
    if (storedSession) {
        switchSession(storedSession);
    } else {
        handleNewChat(false); // Don't create on server yet, just UI state
    }
  }, []);

  const loadSessions = async () => {
      try {
          const sessionList = await orchestratorAPI.getUserSessions();
          setSessions(sessionList);
      } catch (e) {
          console.error("Failed to load sessions", e);
      }
  };

  const handleNewChat = async (createOnServer = true) => {
      setMessages([]);
      setCurrentSessionId(null);
      localStorage.removeItem('boa_session_id'); // Clear active session
      
      if (createOnServer) {
          try {
              const newId = await orchestratorAPI.startNewSession();
              setCurrentSessionId(newId);
              loadSessions();
          } catch (e) {
              console.error("Failed to start new session", e);
          }
      }
  };

  const switchSession = async (sessionId) => {
      if (sessionId === currentSessionId) return;
      
      setIsLoading(true);
      try {
          const history = await orchestratorAPI.getSessionMessages(sessionId);
          setMessages(history.map(msg => ({
              ...msg,
              id: msg.id || Date.now(),
              // Ensure timestamp is a Date object if needed, checking format
              timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date()
          })));
          
          localStorage.setItem('boa_session_id', sessionId);
          setCurrentSessionId(sessionId);
      } catch (e) {
          console.error("Failed to load session history", e);
      } finally {
          setIsLoading(false);
      }
  };

  const deleteSession = async (e, sessionId) => {
      e.stopPropagation(); // Prevent ensuring click doesn't trigger switchSession
      if (window.confirm("Are you sure you want to delete this conversation?")) {
          await orchestratorAPI.deleteSession(sessionId);
          await loadSessions();
          if (currentSessionId === sessionId) {
              handleNewChat(false);
          }
      }
  };

  const handleSendMessage = async (textOverride = null) => {
    const textToSend = textOverride || inputMessage;
    if (!textToSend.trim() || isLoading) return;

    // Local echo
    const userMessage = { 
      id: Date.now(), 
      text: textToSend, 
      sender: 'user', 
      timestamp: new Date() 
    };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Ensure we have a session ID before sending
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
          // First message of a new chat -> create session implicitly or explicitly
          // The Chat API handles missing ID usually, but our frontend logic relies on having one
          // Let's create one now if missing
           activeSessionId = await orchestratorAPI.startNewSession();
           setCurrentSessionId(activeSessionId);
           localStorage.setItem('boa_session_id', activeSessionId);
      } else {
        // Ensure localStorage matches state
         localStorage.setItem('boa_session_id', activeSessionId);
      }
      
      // Pass the session ID we just ensured exists
      // Note: We don't pass 'messages' array anymore as history is managed by backend
      const response = await orchestratorAPI.chat(textToSend); 
      
      const aiMessage = {
        id: Date.now() + 1,
        text: response.response,
        sender: 'ai',
        timestamp: new Date(),
        suggestions: response.suggestions
      };
      setMessages(prev => [...prev, aiMessage]);
      loadSessions(); // Update sidebar "Last Activity"
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        text: 'I apologize, but I encountered an error processing your request. Please try again.',
        sender: 'ai',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    }

    setIsLoading(false);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTime = (dateStr) => {
      if (!dateStr) return '';
      return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] bg-white rounded-lg shadow-sm border overflow-hidden">
      {/* Sidebar - History */}
      <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col hidden md:flex">
        <div className="p-4 border-b border-gray-200">
            <button 
                onClick={() => handleNewChat(false)}
                className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg transition-colors"
            >
                <Plus className="h-4 w-4" />
                <span>New Chat</span>
            </button>
        </div>
        <div className="flex-1 overflow-y-auto">
            <div className="p-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-2">Recent Sessions</h3>
                <div className="space-y-1">
                    {sessions.map(session => (
                        <div
                            key={session.session_id}
                            className={`w-full flex items-center justify-between px-3 py-2 rounded-md text-sm group transition-colors cursor-pointer ${
                                currentSessionId === session.session_id 
                                ? 'bg-blue-100 text-blue-700 font-medium' 
                                : 'text-gray-700 hover:bg-gray-200'
                            }`}
                            onClick={() => switchSession(session.session_id)}
                        >
                            <div className="flex items-center min-w-0 flex-1">
                                <MessageSquare className={`h-4 w-4 mr-2 flex-shrink-0 ${
                                    currentSessionId === session.session_id ? 'text-blue-500' : 'text-gray-400'
                                }`} />
                                <div className="flex-1 min-w-0">
                                    <div className="truncate">Conversation</div>
                                    <div className="text-xs text-gray-500 truncate">{formatTime(session.last_activity)}</div>
                                </div>
                            </div>
                            <button
                                onClick={(e) => deleteSession(e, session.session_id)}
                                className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity"
                                title="Delete session"
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </button>
                        </div>
                    ))}
                    {sessions.length === 0 && (
                        <div className="text-center py-8 text-gray-400 text-xs">No history available</div>
                    )}
                </div>
            </div>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Chat header */}
        <div className="bg-white border-b border-gray-200 p-4 flex justify-between items-center shadow-sm z-10">
            <div className="flex items-center">
                <div className="h-8 w-8 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600 mr-3">
                    <Bot className="h-5 w-5" />
                </div>
                <div>
                    <h1 className="text-lg font-semibold text-gray-900">AI Financial Assistant</h1>
                     <p className="text-xs text-gray-500 flex items-center">
                        <span className="w-2 h-2 bg-green-500 rounded-full mr-1"></span>
                        Online | Gemini 2.5 Flash
                    </p>
                </div>
            </div>
            {/* Mobile New Chat Button */}
            <button 
                onClick={() => handleNewChat(false)}
                className="md:hidden p-2 text-gray-500 hover:bg-gray-100 rounded-full"
            >
                <Plus className="h-5 w-5" />
            </button>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.length === 0 && (
             <div className="h-full flex flex-col items-center justify-center p-8 text-center opacity-75">
                <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mb-6 text-blue-600">
                    <Bot className="h-8 w-8" />
                </div>
                <h2 className="text-2xl font-semibold text-gray-900 mb-2">How can I help you today?</h2>
                <p className="max-w-md text-gray-500 mb-8">
                    I can help you check balances, transfer money, analyze spending habits, and answer financial questions.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                    {faqs.map((faq, i) => (
                        <button 
                            key={i}
                            onClick={() => handleSendMessage(faq)}
                            className="text-left p-4 bg-white border border-gray-200 rounded-xl hover:border-blue-400 hover:shadow-md transition-all text-sm text-gray-700 hover:text-blue-600 flex items-center justify-between group"
                        >
                            <span>{faq}</span>
                            <ChevronRight className="h-4 w-4 text-gray-300 group-hover:text-blue-500 transition-colors" />
                        </button>
                    ))}
                </div>
             </div>
            )}

            {messages.map((message) => (
            <div
                key={message.id}
                className={`flex items-start space-x-3 ${
                message.sender === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
                }`}
            >
                {/* Avatar */}
                <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center shadow-sm mt-1 ${
                message.sender === 'user' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-white border border-gray-200 text-blue-600'
                }`}>
                {message.sender === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                </div>
                
                {/* Message Bubble */}
                <div className={`max-w-2xl ${message.sender === 'user' ? 'text-right' : 'w-full'}`}>
                    <div
                        className={`p-4 rounded-2xl text-sm shadow-sm leading-relaxed ${
                        message.sender === 'user'
                            ? 'bg-blue-600 text-white rounded-tr-none'
                            : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none'
                        }`}
                    >
                        <p className="whitespace-pre-wrap">{message.text}</p>
                    </div>
                    
                    {/* Timestamp */}
                    <p className={`text-[10px] text-gray-400 mt-1 mx-1 ${message.sender === 'user' ? 'text-right' : 'text-left'}`}>
                        {message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : ''}
                    </p>
                    
                    {/* Suggestions (only for latest AI message) */}
                    {message.suggestions && message.suggestions.length > 0 && (
                        <div className="mt-3 space-y-2">
                        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide ml-1 text-left">Suggested actions</p>
                        <div className="flex flex-wrap gap-2">
                            {message.suggestions.map((suggestion, index) => (
                            <button
                                key={index}
                                onClick={() => setInputMessage(suggestion)}
                                className="px-3 py-1.5 text-xs font-medium bg-white border border-blue-200 text-blue-700 rounded-full hover:bg-blue-50 transition-colors"
                            >
                                {suggestion}
                            </button>
                            ))}
                        </div>
                        </div>
                    )}
                </div>
            </div>
            ))}
            
            {/* Loading indicator */}
            {isLoading && (
            <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-white border border-gray-200 text-blue-600 flex items-center justify-center shadow-sm mt-1">
                 <Bot className="h-4 w-4" />
                </div>
                <div className="bg-white px-4 py-3 rounded-2xl rounded-tl-none border border-gray-100 shadow-sm">
                 <div className="flex space-x-2 items-center">
                    <LoadingSpinner size="sm" />
                    <span className="text-gray-500 text-xs font-medium">Processing...</span>
                 </div>
                </div>
            </div>
            )}
            <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-gray-200">
             <div className="relative flex items-center max-w-4xl mx-auto">
                <input
                    type="text"
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask about your finances..."
                    disabled={isLoading}
                    className="flex-1 py-3 pl-4 pr-12 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm disabled:opacity-60 text-sm"
                />
                <button
                    onClick={() => handleSendMessage()}
                    disabled={!inputMessage.trim() || isLoading}
                    className="absolute right-2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:hover:bg-blue-600 transition-colors shadow-sm"
                >
                    <Send className="h-4 w-4" />
                </button>
             </div>
             <p className="text-center text-xs text-gray-400 mt-2">
                 AI responses are generated by Gemini 2.5 and may be inaccurate.
             </p>
        </div>
      </div>
    </div>
  );
};

export default Chat;