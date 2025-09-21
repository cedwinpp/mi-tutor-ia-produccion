javascript
  document.addEventListener('DOMContentLoaded', () => {
      const chatForm = document.getElementById('chat-form');
      const userMessageInput = document.getElementById('user-message');
      const chatContainer = document.getElementById('chat-container');
      const accessKey = window.location.pathname.split('/').pop();

      console.log('Chat.js simplificado para depuración final.');

      chatForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const userMessage = userMessageInput.value;
          if (!userMessage) return;

          // Añade el mensaje del usuario a la ventana
          const userMessageElement = document.createElement('div');
          userMessageElement.classList.add('message', 'user-message');
          userMessageElement.innerText = userMessage;
          chatContainer.appendChild(userMessageElement);
          userMessageInput.value = '';
          chatContainer.scrollTop = chatContainer.scrollHeight;

          // Envía el mensaje al backend y espera la respuesta de la IA
          try {
              const response = await fetch('/api/chat', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ access_key: accessKey, user_message: userMessage
  }),
              });
              const data = await response.json();

              // Añade la respuesta de la IA a la ventana
              const aiMessageElement = document.createElement('div');
              aiMessageElement.classList.add('message', 'assistant-message');
              aiMessageElement.innerHTML = data.ai_response; // Usamos innerHTML por si la
  IA envía formato
              chatContainer.appendChild(aiMessageElement);
              chatContainer.scrollTop = chatContainer.scrollHeight;
          } catch (error) {
              console.error('Error en el chat simplificado:', error);
              const errorMessageElement = document.createElement('div');
              errorMessageElement.classList.add('message', 'assistant-message');
              errorMessageElement.innerText = 'Error de conexión.';
              chatContainer.appendChild(errorMessageElement);
          }
      });
  });