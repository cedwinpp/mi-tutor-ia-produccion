document.addEventListener('DOMContentLoaded', () => {
      const chatForm = document.getElementById('chat-form');
      const userMessageInput = document.getElementById('user-message');
      const chatContainer = document.getElementById('chat-container');
      const accessKey = window.location.pathname.split('/').pop();
      const exercisesList = document.getElementById('exercises-ul');

      console.log('Simplified chat script for final debug.');

      chatForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const userMessage = userMessageInput.value;
          if (!userMessage) return;

          // Add user message to chat
          const userMessageElement = document.createElement('div');
          userMessageElement.classList.add('message', 'user-message');
          userMessageElement.innerText = userMessage;
          chatContainer.appendChild(userMessageElement);
          userMessageInput.value = '';
          chatContainer.scrollTop = chatContainer.scrollHeight;

          // Send to backend and wait for AI response
          try {
              const response = await fetch('/api/chat', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ access_key: accessKey, user_message: userMessage }),
              });
              const data = await response.json();

              // Add AI response to chat
              const aiMessageElement = document.createElement('div');
              aiMessageElement.classList.add('message', 'assistant-message');
              aiMessageElement.innerHTML = data.ai_response;
              chatContainer.appendChild(aiMessageElement);
              chatContainer.scrollTop = chatContainer.scrollHeight;
          } catch (error) {
              console.error('Simplified chat error:', error);
              const errorMessageElement = document.createElement('div');
              errorMessageElement.classList.add('message', 'assistant-message');
              errorMessageElement.innerText = 'Connection error.';
              chatContainer.appendChild(errorMessageElement);
          }
      });

      // New functionality for the "Mostrar Solución" button
      if (exercisesList) {
          exercisesList.addEventListener('click', (e) => {
              if (e.target && e.target.classList.contains('show-solution-button')) {
                  e.preventDefault(); // Prevent any default button action

                  const exerciseText = e.target.getAttribute('data-exercise');
                  if (exerciseText) {
                      // Copy the exercise text to the input field
                      userMessageInput.value = exerciseText;
                      userMessageInput.focus(); // Focus on the input for immediate sending
                  }
              }
          });
      }
  });