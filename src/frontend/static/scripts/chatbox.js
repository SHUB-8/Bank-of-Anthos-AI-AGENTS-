/**
 * Copyright 2024 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

class Chatbox {
    constructor() {
        this.isOpen = false;
        this.isMinimized = false;
        this.sessionId = this.generateSessionId();
        
        this.initializeElements();
        this.bindEvents();
        this.setWelcomeTime();
    }

    initializeElements() {
        this.trigger = document.getElementById('chatbox-trigger');
        this.container = document.getElementById('chatbox-container');
        this.toggleBtn = document.getElementById('chatbox-toggle');
        this.closeBtn = document.getElementById('chatbox-close');
        this.messages = document.getElementById('chatbox-messages');
        this.input = document.getElementById('chatbox-input');
        this.sendBtn = document.getElementById('chatbox-send');
    }

    bindEvents() {
        this.trigger.addEventListener('click', () => this.open());
        this.toggleBtn.addEventListener('click', () => this.toggle());
        this.closeBtn.addEventListener('click', () => this.close());
        
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Auto-resize input on typing
        this.input.addEventListener('input', () => {
            this.sendBtn.disabled = this.input.value.trim() === '';
        });
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    setWelcomeTime() {
        const timeElement = document.getElementById('welcome-time');
        if (timeElement) {
            timeElement.textContent = new Date().toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit'
            });
        }
    }

    open() {
        this.isOpen = true;
        this.container.style.display = 'flex';
        this.trigger.style.display = 'none';
        this.input.focus();
    }

    close() {
        this.isOpen = false;
        this.container.style.display = 'none';
        this.trigger.style.display = 'flex';
        this.isMinimized = false;
        this.container.classList.remove('chatbox-minimized');
    }

    toggle() {
        this.isMinimized = !this.isMinimized;
        if (this.isMinimized) {
            this.container.classList.add('chatbox-minimized');
            this.toggleBtn.textContent = '+';
        } else {
            this.container.classList.remove('chatbox-minimized');
            this.toggleBtn.textContent = '−';
        }
    }

    async sendMessage() {
        const message = this.input.value.trim();
        if (!message) return;

        // Clear input and disable send button
        this.input.value = '';
        this.sendBtn.disabled = true;

        // Add user message to chat
        this.addMessage(message, 'user');

        // Show typing indicator
        const typingId = this.showTypingIndicator();

        try {
            // Send request to backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    session_id: this.sessionId
                })
            });

            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            if (response.ok) {
                const data = await response.json();
                
                const botResponse = data.response || data.reply || 'I received your message but couldn\'t generate a response.';
                this.addMessage(botResponse, 'bot');
                
                // Handle action confirmations
                if (data.requires_confirmation) {
                    this.addConfirmationButtons(data);
                }
                
                // Show action success/failure feedback
                if (data.action_taken !== undefined) {
                    const actionStatus = data.action_taken ? 'Action completed successfully!' : 'Action could not be completed.';
                    console.log(actionStatus);
                }
            } else {
                const errorData = await response.json().catch(() => ({}));
                this.addMessage(
                    errorData.error || 'Sorry, I\'m having trouble connecting to the service. Please try again.',
                    'bot'
                );
            }
        } catch (error) {
            // Remove typing indicator
            this.removeTypingIndicator(typingId);
            console.error('Chat error:', error);
            this.addMessage(
                'Sorry, I\'m having trouble connecting to the service. Please try again.',
                'bot'
            );
        }
    }

    addMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = content;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        messageDiv.appendChild(contentDiv);
        messageDiv.appendChild(timeDiv);
        
        this.messages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        const typingId = 'typing_' + Date.now();
        typingDiv.id = typingId;
        typingDiv.className = 'message bot-message';
        
        const indicatorDiv = document.createElement('div');
        indicatorDiv.className = 'typing-indicator';
        indicatorDiv.innerHTML = `
            <span>Assistant is typing</span>
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        
        typingDiv.appendChild(indicatorDiv);
        this.messages.appendChild(typingDiv);
        this.scrollToBottom();
        
        return typingId;
    }

    removeTypingIndicator(typingId) {
        const typingElement = document.getElementById(typingId);
        if (typingElement) {
            typingElement.remove();
        }
    }

    addConfirmationButtons(data) {
        const confirmationDiv = document.createElement('div');
        confirmationDiv.className = 'message bot-message confirmation-message';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = `
            <div class="confirmation-buttons">
                <button class="confirm-btn" onclick="chatbox.handleConfirmation(true, '${data.intent}')">
                    ✓ Confirm
                </button>
                <button class="cancel-btn" onclick="chatbox.handleConfirmation(false, '${data.intent}')">
                    ✗ Cancel
                </button>
            </div>
        `;
        
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = new Date().toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        confirmationDiv.appendChild(contentDiv);
        confirmationDiv.appendChild(timeDiv);
        this.messages.appendChild(confirmationDiv);
        this.scrollToBottom();
    }

    async handleConfirmation(confirmed, intent) {
        // Remove confirmation buttons
        const confirmationMsg = document.querySelector('.confirmation-message');
        if (confirmationMsg) {
            confirmationMsg.remove();
        }

        // Send confirmation response
        const confirmationMessage = confirmed ? 'Yes, please proceed' : 'No, cancel that';
        this.addMessage(confirmationMessage, 'user');

        // Show typing indicator
        const typingId = this.showTypingIndicator();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: confirmationMessage,
                    session_id: this.sessionId,
                    confirmation: confirmed,
                    original_intent: intent
                })
            });

            this.removeTypingIndicator(typingId);

            if (response.ok) {
                const data = await response.json();
                const botResponse = data.response || data.reply || 'Confirmation processed.';
                this.addMessage(botResponse, 'bot');
            } else {
                this.addMessage('Sorry, there was an error processing your confirmation.', 'bot');
            }
        } catch (error) {
            this.removeTypingIndicator(typingId);
            console.error('Confirmation error:', error);
            this.addMessage('Sorry, there was an error processing your confirmation.', 'bot');
        }
    }

    scrollToBottom() {
        this.messages.scrollTop = this.messages.scrollHeight;
    }
}

// Initialize chatbox when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new Chatbox();
});
