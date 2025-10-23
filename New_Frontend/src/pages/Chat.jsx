import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User } from 'lucide-react';
import { orchestratorAPI } from '../api/ai_agents.js';
import LoadingSpinner from '../components/LoadingSpinner.jsx';

const Chat = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Hello! I'm your AI financial assistant. I can help you with budgets, transactions, contacts, and security alerts. How can I assist you today?",
      sender: 'ai',
      timestamp: new Date(),
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = { 
      id: Date.now(), 
      text: inputMessage, 
      sender: 'user', 
      timestamp: new Date() 
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await orchestratorAPI.chat(inputMessage, messages);
      const aiMessage = {
        id: Date.now() + 1,
        text: response.response,
        sender: 'ai',
        timestamp: new Date(),
        suggestions: response.suggestions
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        text: 'I apologize, but I encountered an error processing your request. Please try again or contact support if the issue persists.',
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

  const handleSuggestionClick = (suggestion) => {
    setInputMessage(suggestion);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] bg-white rounded-lg shadow-sm border">
      {/* Chat header */}
      <div className="bg-blue-600 text-white p-4 rounded-t-lg">
        <h1 className="text-xl font-semibold flex items-center">
          <Bot className="h-6 w-6 mr-2" />
          AI Financial Assistant
        </h1>
        <p className="text-blue-100 text-sm mt-1">
          Ask me anything about your finances, budgets, or transactions
        </p>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex items-start space-x-3 ${
              message.sender === 'user' ? 'flex-row-reverse space-x-reverse' : ''
            }`}
          >
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
              message.sender === 'user' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-100 text-gray-600'
            }`}>
              {message.sender === 'user' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            
            <div className={`max-w-3xl ${message.sender === 'user' ? 'text-right' : ''}`}>
              <div
                className={`p-4 rounded-lg ${
                  message.sender === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900'
                }`}
              >
                <p className="whitespace-pre-wrap">{message.text}</p>
              </div>
              
              {/* Suggestions */}
              {message.suggestions && message.suggestions.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-sm text-gray-600 font-medium">Suggested actions:</p>
                  <div className="flex flex-wrap gap-2">
                    {message.suggestions.map((suggestion, index) => (
                      <button
                        key={index}
                        onClick={() => handleSuggestionClick(suggestion)}
                        className="px-3 py-2 text-sm bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              
              <p className="text-xs text-gray-500 mt-2">
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 text-gray-600 flex items-center justify-center">
              <Bot className="h-4 w-4" />
            </div>
            <div className="bg-gray-100 p-4 rounded-lg">
              <div className="flex space-x-2 items-center">
                <LoadingSpinner size="sm" />
                <span className="text-gray-600 text-sm">AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 border-t bg-gray-50 rounded-b-lg">
        <div className="flex space-x-3">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message here... (Press Enter to send)"
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            rows="3"
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            <Send className="h-5 w-5" />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default Chat;