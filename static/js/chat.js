document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const userMessageInput = document.getElementById('user-message');
    const chatContainer = document.getElementById('chat-container');
    const accessKey = window.location.pathname.split('/').pop();

    // Desactivamos temporalmente todas las demás funcionalidades
    console.log('Chat.js cargado en modo de depuración simple.');

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userMessage = userMessageInput.value;
        if (!userMessage) return;

        // Añadir mensaje del usuario al chat
        const userMessageElement = document.createElement('div');
        userMessageElement.classList.add('message', 'user-message');
        userMessageElement.innerText = userMessage;
        chatContainer.appendChild(userMessageElement);
        userMessageInput.value = '';
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // Enviar al backend y añadir la respuesta (eco)
        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ access_key: accessKey, user_message: userMessage }),
            });
            const data = await response.json();

            const aiMessageElement = document.createElement('div');
            aiMessageElement.classList.add('message', 'assistant-message');
            aiMessageElement.innerText = data.ai_response;
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