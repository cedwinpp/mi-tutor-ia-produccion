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

            timerElement.innerHTML = `Tiempo restante: ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }, 1000);
    }

    window.addEventListener('load', () => {
        const initialMessage = "Hola"; // O cualquier otro mensaje inicial
        sendChatMessage(initialMessage, "initial_message");
    });

    // Handle "Mostrar Solución" buttons in the exercise list
    const exerciseSolutionButtons = document.querySelectorAll('#exercises-ul .show-solution-button');
    exerciseSolutionButtons.forEach(button => {
        button.addEventListener('click', () => {
            const listItem = button.closest('li');
            const exerciseText = listItem.querySelector('p:first-child').innerText.replace('Ejercicio ' + (listItem.dataset.exerciseIndex + 1) + ':', '').trim(); // Get exercise text
            
            // Simulate sending the exercise to the chat
            appendMessage('user', exerciseText); // Show user's action in chat
            sendChatMessage(exerciseText, "get_solution"); // Send to backend for solution

            // Hide the button and solution in the exercise list (optional, as solution will be in chat)
            button.style.display = 'none'; 
            listItem.querySelector('.solution-content').style.display = 'none'; // Hide solution in list
        });
    });


    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const userMessage = userMessageInput.value;
        if (!userMessage) return;

        appendMessage('user', userMessage);
        userMessageInput.value = '';

        await sendChatMessage(userMessage);
    });

    async function sendChatMessage(message, action = null, context = null) { // Removed context parameter
        let payload = {
            access_key: accessKey,
            user_message: message,
        };

        if (action) {
            payload.action = action;
        }

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        appendMessage('assistant', data.ai_response, action);
    }

    function appendMessage(sender, message, action = null) {
        console.log("appendMessage called with sender:", sender, "message:", message, "action:", action); // Debugging
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', `${sender}-message`);

        let processedMessage = message;

        // Procesar etiquetas de color (manteniendo la funcionalidad si el prompt las genera)
        processedMessage = processedMessage.replace(/<black>/g, '<span class="black-text">');
        processedMessage = processedMessage.replace(/<\/black>/g, '</span>');
        processedMessage = processedMessage.replace(/<green>/g, '<span class="green-text">');
        processedMessage = processedMessage.replace(/<\/green>/g, '</span>');

        // Procesar etiqueta de sugerencia
        processedMessage = processedMessage.replace(/<suggestion>/g, '<span class="suggestion-text">');
        processedMessage = processedMessage.replace(/<\/suggestion>/g, '</span>');

        // Si la acción es "get_solution", simplemente mostramos el mensaje como solución
        if (action === "get_solution") {
            messageElement.innerHTML = `<strong>Solución:</strong> ${processedMessage}`;
        } else {
            // Procesar ejercicio y solución usando "Ejercicio:" y "Solución:".
            const exerciseSolutionSplit = processedMessage.split('Solución:');
            let exerciseText = '';
            let solutionText = '';

            if (exerciseSolutionSplit.length > 1) {
                const fullExercisePart = exerciseSolutionSplit[0];
                const exerciseStart = fullExercisePart.indexOf('Ejercicio:');
                if (exerciseStart !== -1) {
                    exerciseText = fullExercisePart.substring(exerciseStart + 'Ejercicio:'.length).trim();
                } else {
                    exerciseText = fullExercisePart.trim();
                }
                
                solutionText = exerciseSolutionSplit.slice(1).join('Solución:').trim();

                const exerciseDiv = document.createElement('div');
                exerciseDiv.innerHTML = `<strong>Ejercicio:</strong> ${exerciseText}`;
                messageElement.appendChild(exerciseDiv);

                const solutionDiv = document.createElement('div');
                solutionDiv.innerHTML = `<strong>Solución:</strong> ${solutionText}`;
                solutionDiv.style.display = 'none';
                solutionDiv.classList.add('solution-content');
                messageElement.appendChild(solutionDiv);

                const showSolutionButton = document.createElement('button');
                showSolutionButton.innerText = 'Mostrar Solución';
                showSolutionButton.classList.add('show-solution-button');
                showSolutionButton.addEventListener('click', () => {
                    sendChatMessage(exerciseText, "get_solution");
                    showSolutionButton.style.display = 'none';
                });
                messageElement.appendChild(showSolutionButton);

            } else {
                messageElement.innerHTML = processedMessage;
            }
        }
        
        chatContainer.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight;
        
        if (typeof MathJax !== 'undefined') {
            MathJax.typeset();
        }
    }
});
