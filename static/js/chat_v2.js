javascript
  document.addEventListener('DOMContentLoaded', () => {
      const chatForm = document.getElementById('chat-form');
      const userMessageInput = document.getElementById('user-message');
      const chatContainer = document.getElementById('chat-container');
      const accessKey = window.location.pathname.split('/').pop();
      const timerElement = document.getElementById('timer');

      // Función del temporizador
      if (timerElement) {
          let remainingSeconds = parseInt(timerElement.dataset.remainingSeconds, 10);
          const timerInterval = setInterval(() => {
              if (remainingSeconds <= 0) {
                  clearInterval(timerInterval);
                  timerElement.innerHTML = "Sesión Expirada";
                  return;
              }
              remainingSeconds--;
              const minutes = Math.floor(remainingSeconds / 60);
              const seconds = remainingSeconds % 60;
              timerElement.innerHTML = Tiempo restante: ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')};
          }, 1000);
      }

      // Mensaje inicial de la IA
      window.addEventListener('load', () => {
          sendChatMessage("Hola", "initial_message");
      });

      // Botones de "Mostrar Solución" de la lista de ejercicios
      const exerciseSolutionButtons = document.querySelectorAll('#exercises-ul .show-solution-button');
      exerciseSolutionButtons.forEach((button, index) => {
          button.addEventListener('click', () => {
              const listItem = button.closest('li');
              const exerciseText = listItem.querySelector('p:first-child').innerText.replace(/Ejercicio \d+:/, '').trim();
              appendMessage('user', exerciseText);
              sendChatMessage(exerciseText, "get_solution");
              button.style.display = 'none';
          });
      });

      // Envío del formulario del chat
      chatForm.addEventListener('submit', async (e) => {
          e.preventDefault();
          const userMessage = userMessageInput.value;
          if (!userMessage) return;
          appendMessage('user', userMessage);
          userMessageInput.value = '';
          await sendChatMessage(userMessage);
      });

      // Función para enviar mensajes al backend
      async function sendChatMessage(message, action = null) {
          const payload = { access_key: accessKey, user_message: message };
          if (action) {
              payload.action = action;
          }

          const typingIndicator = document.createElement('div');
          typingIndicator.id = 'typing-indicator';
          typingIndicator.classList.add('message', 'assistant-message');
          typingIndicator.innerText = 'Escribiendo...';
          chatContainer.appendChild(typingIndicator);
          chatContainer.scrollTop = chatContainer.scrollHeight;

          try {
              const response = await fetch('/api/chat', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(payload),
              });
              const data = await response.json();
              document.getElementById('typing-indicator').remove();
              appendMessage('assistant', data.ai_response, action);
          } catch (error) {
              console.error('Error sending message:', error);
              document.getElementById('typing-indicator').remove();
              appendMessage('assistant', 'Lo siento, ha ocurrido un error de conexión.');
          }
      }

      // Función para añadir mensajes a la ventana del chat
      function appendMessage(sender, message, action = null) {
          const messageElement = document.createElement('div');
          messageElement.classList.add('message', ${sender}-message);

          if (sender === 'user') {
              messageElement.innerText = message;
          } else {
              const videoRegex = /\[video: (https?:\/\/[^\s\]]+)\]/g;
              let processedMessage = message.replace(videoRegex, (match, url) => {
                  return <a href="${url}" target="_blank" class="video-button">▶️ Ver Vídeo Explicativo</a>;
              });
              messageElement.innerHTML = processedMessage;
          }

          chatContainer.appendChild(messageElement);
          chatContainer.scrollTop = chatContainer.scrollHeight;

          if (typeof MathJax !== 'undefined') {
              MathJax.typesetPromise([messageElement]).catch(function (err) {
                  console.log('MathJax error: ', err.message);
              });
          }
      }
  });
  