from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
import os
import secrets
import string
from openai import OpenAI
from database import init_db, add_prompt, get_prompt_by_key, add_exercise_history, get_predefined_exercises_by_prompt_id, add_predefined_exercise
import re # Import regular expression module
import datetime # Import datetime module

# Cargar variables de entorno desde .env
load_dotenv()

# Inicializar la base de datos
init_db()

app = Flask(__name__)

# Instanciar el cliente de OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Definir el límite de tiempo de la sesión en minutos
SESSION_TIME_LIMIT_MINUTES = 30

def generate_unique_access_key(length=16):
    """Genera una clave de acceso única y segura."""
    alphabet = string.ascii_letters + string.digits
    while True:
        access_key = ''.join(secrets.choice(alphabet) for i in range(length))
        # Aquí deberíamos verificar si la clave ya existe en la base de datos
        # para garantizar la unicidad. Por ahora, la probabilidad de colisión
        # es extremadamente baja para el MVP.
        return access_key

def get_ai_response(system_prompt, user_message):
    """Obtiene una respuesta del modelo de OpenAI."""
    print(f"\n--- PROMPT ENVIADO A OPENAI ---\nSystem Prompt: {system_prompt}\nUser Message: {user_message}\n-------------------------------\n") # Debugging
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error al llamar a la API de OpenAI: {e}")
        return "Lo siento, ha ocurrido un error al procesar tu solicitud."

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        access_key = request.form['access_key']
        prompt_data = get_prompt_by_key(access_key)
        if prompt_data:
            return redirect(url_for('chat', access_key=access_key))
        else:
            error = "Clave de acceso no válida. Inténtalo de nuevo."
    return render_template('index.html', error=error)

@app.route('/chat/<access_key>')
def chat(access_key):
    prompt_data = get_prompt_by_key(access_key)
    if not prompt_data:
        return "Error: Clave de acceso no válida." # Or redirect to error page

    prompt_id, system_prompt, session_start_time = prompt_data # Unpack prompt_id, system_prompt, and session_start_time

    # Retrieve predefined exercises from the database
    exercises_from_db = get_predefined_exercises_by_prompt_id(prompt_id)
    
    # Format exercises for the template
    exercises = [{'exercise': ex_text, 'solution': ''} for ex_text in exercises_from_db]
    
    return render_template('chat.html', exercises=exercises, session_start_time=session_start_time.isoformat())

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    access_key = data['access_key']
    user_message = data['user_message']
    action = data.get('action') # Nuevo campo para la acción

    prompt_data = get_prompt_by_key(access_key)
    if not prompt_data:
        return jsonify({'ai_response': 'Error: Clave de acceso no válida.'})
    
    prompt_id, system_prompt, session_start_time_str = prompt_data # Unpack prompt_id, system_prompt, and session_start_time_str

    # Check session time limit
    session_start_time = datetime.datetime.fromisoformat(session_start_time_str)
    time_elapsed = datetime.datetime.now() - session_start_time
    if time_elapsed.total_seconds() > SESSION_TIME_LIMIT_MINUTES * 60:
        return jsonify({'ai_response': 'Tu sesión ha expirado. Por favor, contacta a tu tutor para una nueva sesión.'})

    if action == "get_solution":
        # Si la acción es obtener la solución, el user_message es el ejercicio
        ai_response = get_ai_response(system_prompt + "\n\nPor favor, proporciona la solución paso a paso para el siguiente ejercicio:", user_message)
    else: # Removed the elif for "proponer ejercicio similar"
        ai_response = get_ai_response(system_prompt, user_message)
    
    # Intentar extraer ejercicio y solución para guardar en el historial
    # Modificado para manejar la repetición de "Ejercicio:" y hacer "Solución:" opcional
    exercise_match = re.search(r'(?:Ejercicio:\s*)?(.*?)(?:\s*Solución:|$)', ai_response, re.DOTALL) # Made Ejercicio: optional
    solution_match = re.search(r'Solución:\s*(.*)', ai_response, re.DOTALL)
    
    print(f"--- DEBUG: exercise_match={exercise_match} ---") # Debugging
    print(f"--- DEBUG: solution_match={solution_match} ---") # Debugging

    if exercise_match:
        extracted_exercise_text = exercise_match.group(1).strip()
        # Eliminar la posible repetición de "Ejercicio:" al inicio
        if extracted_exercise_text.lower().startswith("ejercicio:"):
            extracted_exercise_text = extracted_exercise_text[len("ejercicio:"):
].strip()

        extracted_solution_text = solution_match.group(1).strip() if solution_match else ""
        
        # Intentar extraer el tipo de ejercicio del texto del ejercicio
        type_match = re.search(r'\((.*?)\):', extracted_exercise_text)
        extracted_exercise_type = type_match.group(1).strip() if type_match else None
        
        # Guardar en el historial
        add_exercise_history(access_key, extracted_exercise_text, extracted_solution_text, extracted_exercise_type)
        print(f"--- EJERCICIO GUARDADO EN HISTORIAL: Tipo={extracted_exercise_type} ---\n") # Debugging

    # Removed: Añadir la pregunta de seguimiento solo si no es una solicitud de solución
    # Removed: if action != "get_solution":
    # Removed:     follow_up_question = "<suggestion>¿Tienes otro ejercicio en que te pueda ayudar o te propongo yo uno similar?</suggestion>"
    # Removed:     ai_response_with_follow_up = f"{ai_response}\n\n{follow_up_question}"
    # Removed: else:
    # Removed:     ai_response_with_follow_up = ai_response # No añadir la pregunta si es una solución
        
    return jsonify({'ai_response': ai_response}) # Return ai_response directly

@app.route('/admin/create_prompt', methods=['GET', 'POST'])
def admin_create_prompt():
    access_key = None
    if request.method == 'POST':
        student_email = request.form['student_email']
        topic = request.form['topic']
        prompt_content = request.form['prompt_content']
        exercises_text = request.form.get('exercises_text', '') # New field for exercises
        
        access_key = generate_unique_access_key()
        prompt_id = add_prompt(student_email, topic, prompt_content, access_key) # Get prompt_id here

        # Retrieve the prompt_id for the newly added prompt
        # Removed: prompt_data = get_prompt_by_key(access_key)
        if prompt_id: # Check if prompt_id was successfully added
            # Removed: prompt_id, _, _ = prompt_data # Unpack prompt_id, prompt_content, session_start_time
            # Add predefined exercises
            exercise_lines = exercises_text.strip().split('\n')
            for i, line in enumerate(exercise_lines):
                if line.strip(): # Only add non-empty lines
                    add_predefined_exercise(prompt_id, line.strip(), i + 1)
        
    return render_template('admin_create.html', access_key=access_key)

if __name__ == '__main__':
    app.run(debug=True)