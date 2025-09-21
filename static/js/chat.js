document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', 'assistant-message');
        messageElement.innerText = 'Hola, esto es una prueba desde chat.js. Si ves este mensaje, el archivo se está cargando correctamente.';
        chatContainer.appendChild(messageElement);
    } else {
        alert('Error: No se encontró el contenedor del chat.');
    }
});