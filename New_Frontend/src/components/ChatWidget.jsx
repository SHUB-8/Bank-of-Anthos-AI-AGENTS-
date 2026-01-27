import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { MessageCircle, X, Send, Clock, Trash2 } from 'lucide-react';
import { orchestratorAPI } from '../api/ai_agents.js';

const ChatWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]); // Array of {id, title, messages}
  const [currentChatId, setCurrentChatId] = useState(null);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  
  const messagesEndRef = useRef(null);
  const location = useLocation();

  // Frequent questions
  const quickQuestions = [
    "What's my balance?",
    "Show my latest transactions",
    "How can I save money?",
    "Exchange rate for EUR?" 
  ];

  // Load chat history from local storage on mount
  useEffect(() => {
    try {
      const savedHistory = localStorage.getItem('chat_history');
      if (savedHistory) {
        let parsedHistory = JSON.parse(savedHistory);
        // Backfill sessionId for older data if missing
        parsedHistory = parsedHistory.map(c => ({
            ...c,
            sessionId: c.sessionId || crypto.randomUUID()
        }));
        setHistory(parsedHistory);
        if (parsedHistory.length > 0 && !currentChatId) {
            setCurrentChatId(parsedHistory[0].id);
        }
      } else {
        createNewChat();
      }
    } catch (e) {
      console.error("Failed to load chat history", e);
      createNewChat();
    }
  }, []);

  // Save history whenever it changes
  useEffect(() => {
    if (history.length > 0) {
      localStorage.setItem('chat_history', JSON.stringify(history));
    }
  }, [history]);

  // Update current messages when chat ID changes
  useEffect(() => {
    if (currentChatId) {
      const chat = history.find(c => c.id === currentChatId);
      if (chat) {
        setMessages(chat.messages);
      }
    }
  }, [currentChatId, history]);

  const createNewChat = () => {
    const newId = Date.now().toString();
    const newChat = {
      id: newId,
      sessionId: crypto.randomUUID(), // Unique session for backend context
      title: `Chat ${new Date().toLocaleTimeString()}`,
      messages: []
    };
    
    setHistory(prev => [newChat, ...prev]);
    setCurrentChatId(newId);
    setMessages([]);
    setShowHistory(false);
  };

  const deleteChat = (e, id) => {
    e.stopPropagation();
    const newHistory = history.filter(h => h.id !== id);
    setHistory(newHistory);
    localStorage.setItem('chat_history', JSON.stringify(newHistory));
    
    if (currentChatId === id) {
      if (newHistory.length > 0) {
        setCurrentChatId(newHistory[0].id);
      } else {
        createNewChat();
      }
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  const handleSendMessage = async (textOverride = null) => {
    const textToSend = textOverride || inputMessage;
    if (!textToSend.trim() || isLoading) return;

    // Add user message
    const userMsg = { type: 'user', content: textToSend.trim(), timestamp: new Date().toISOString() };
    const updatedMessages = [...messages, userMsg];
    
    setMessages(updatedMessages);
    setInputMessage('');
    setIsLoading(true);
    
    // Update history immediately
    updateChatHistory(currentChatId, updatedMessages);

    try {
      // Get session ID for current chat
      const currentChat = history.find(c => c.id === currentChatId);
      const sessionId = currentChat ? currentChat.sessionId : null;

      // Use the chat method from orchestratorAPI (which calls /chat endpoint)
      const response = await orchestratorAPI.chat(textToSend, [], sessionId);
      
      const botMsg = { 
        type: 'assistant', 
        content: response.response, 
        timestamp: new Date().toISOString() 
      };
      
      const finalMessages = [...updatedMessages, botMsg];
      setMessages(finalMessages);
      updateChatHistory(currentChatId, finalMessages);
      
      // Update title if it's the first message
      if (updatedMessages.length === 1) {
         updateChatTitle(currentChatId, textToSend);
      }
      
    } catch (error) {
      console.error('Chat error:', error);
      const errorMsg = { 
        type: 'assistant', 
        content: 'Sorry, I encountered an error. Please try again later. (Quota may be exceeded)',
        isError: true
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const updateChatHistory = (chatId, newMessages) => {
    setHistory(prev => prev.map(chat => 
      chat.id === chatId ? { ...chat, messages: newMessages } : chat
    ));
  };
  
  const updateChatTitle = (chatId, firstMessage) => {
    const title = firstMessage.length > 20 ? firstMessage.substring(0, 20) + '...' : firstMessage;
    setHistory(prev => prev.map(chat => 
        chat.id === chatId ? { ...chat, title: title } : chat
    ));
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const ChatHistoryView = () => (
    <div className="flex-1 overflow-y-auto p-2 space-y-2 bg-gray-50">
        <button 
           onClick={createNewChat}
           className="w-full py-2 px-4 bg-white border border-blue-200 text-blue-600 rounded-lg hover:bg-blue-50 font-medium text-sm flex items-center justify-center gap-2 mb-3"
        >
           <MessageCircle className="h-4 w-4" /> New Conversation
        </button>
        
        {history.map(chat => (
            <div 
               key={chat.id}
               onClick={() => { setCurrentChatId(chat.id); setShowHistory(false); }}
               className={`p-3 rounded-lg border cursor-pointer hover:bg-gray-100 flex justify-between items-center group ${currentChatId === chat.id ? 'border-blue-500 bg-white shadow-sm' : 'border-gray-200 bg-white'}`}
            >
               <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-gray-900 truncate">{chat.title}</p>
                  <p className="text-xs text-gray-500 truncate">{new Date(parseInt(chat.id)).toLocaleDateString()}</p>
               </div>
               <button 
                  onClick={(e) => deleteChat(e, chat.id)}
                  className="p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
               >
                  <Trash2 className="h-4 w-4" />
               </button>
            </div>
        ))}
    </div>
  );

  return (
    <>
      {/* Chat Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 bg-blue-600 hover:bg-blue-700 text-white p-4 rounded-full shadow-lg transition-all duration-200 z-50 flex items-center justify-center"
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
      </button>

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed bottom-24 right-6 w-96 h-[500px] bg-white rounded-xl shadow-2xl border border-gray-200 z-50 flex flex-col overflow-hidden font-sans">
          {/* Header */}
          <div className="bg-blue-600 text-white p-4 flex justify-between items-center shadow-md">
            <div>
              <h3 className="font-semibold text-lg">AI Assistant</h3>
              <p className="text-xs text-blue-100">Bank of Anthos</p>
            </div>
            <button 
                onClick={() => setShowHistory(!showHistory)}
                className="p-2 hover:bg-blue-700 rounded-lg transition-colors"
                title="Chat History"
            >
                {showHistory ? <X className="h-5 w-5" /> : <Clock className="h-5 w-5" />}
            </button>
          </div>

          {/* Content Area */}
          {showHistory ? (
              <ChatHistoryView />
          ) : (
          <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full space-y-4">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 mb-2">
                    <MessageCircle className="h-6 w-6" />
                </div>
                <p className="text-gray-500 text-sm text-center">
                  Hi! How can I help you today?
                </p>
                <div className="grid grid-cols-1 gap-2 w-full max-w-xs">
                    {quickQuestions.map((q, i) => (
                        <button key={i} 
                            onClick={() => handleSendMessage(q)}
                            className="text-xs text-left p-2 bg-white border border-gray-200 rounded-lg hover:bg-blue-50 hover:border-blue-200 transition-colors text-gray-700"
                        >
                            {q}
                        </button>
                    ))}
                </div>
              </div>
            )}
            
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] px-4 py-3 rounded-2xl text-sm shadow-sm ${
                    message.type === 'user'
                      ? 'bg-blue-600 text-white rounded-br-none'
                      : message.isError 
                        ? 'bg-red-50 text-red-800 border border-red-200 rounded-bl-none'
                        : 'bg-white text-gray-800 border border-gray-100 rounded-bl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="flex justify-start">
                  <div className="bg-white px-4 py-3 rounded-2xl rounded-bl-none shadow-sm border border-gray-100">
                  <div className="flex space-x-1.5">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 bg-white border-t border-gray-100">
            <div className="flex space-x-2">
              <input
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about deposits, transfers..."
                className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm transition-shadow"
                disabled={isLoading}
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={!inputMessage.trim() || isLoading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white p-2.5 rounded-full shadow-md transition-all duration-200"
              >
                <Send className="h-5 w-5" />
              </button>
            </div>
          </div>
          </>
          )}
        </div>
      )}
    </>
  );
};

export default ChatWidget;
