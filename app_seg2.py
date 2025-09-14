from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
import os
import secrets
import string
from openai import OpenAI
from database import init_db, add_prompt, get_prompt_by_key, add_exercise_history, get_predefined_exercises_by_prompt_id, add_predefined_exercise
import re
import datetime
import logging

# Cargar variables de entorno desde .env
load_dotenv()

# Inicializar la base de datos
init_db()

app = Flask(__name__)

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Instanciar el cliente de OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Definir el límite de tiempo de la sesión en minutos
SESSION_TIME_LIMIT_MINUTES = 30

def generate_unique_access_key(length=16):
    """Genera una clave de acceso única y segura."""
    alphabet = string.ascii_letters + string.digits
    while True:
        access_key = ''.join(secrets.choice(alphabet) for i in range(length))
        # Verificar si la clave ya existe en la base de datos
        if not get_prompt_by_key(access_key):
            return access_key

def get_ai_response(system_prompt, user_message):
    """Obtiene una respuesta del modelo de OpenAI."""
    logger.debug(f"System Prompt: {system_prompt}\nUser Message: {user_message}")
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
        logger.error(f"Error al llamar a la API de OpenAI: {e}")
        return "Lo siento, ha ocurrido un error al procesar tu solicitud."

def parse_session_start_time(session_start_time):
    """Convierte session_start_time a objeto datetime si es una cadena."""
    if isinstance(session_start_time, str):
        try:
            return datetime.datetime.fromisoformat(session_start_time)
        except ValueError:
            logger.warning(f"No se pudo analizar la fecha de inicio de sesión: {session_start_time}")
            return datetime.datetime.now()
    elif isinstance(session_start_time, datetime.datetime):
        return session_start_time
    else:
        logger.warning(f"Tipo de fecha de inicio de sesión no reconocido: {type(session_start_time)}")
        return datetime.datetime.now()

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        access_key = request.form['access_key'].strip()
        if not access_key:
            error = "Por favor, ingresa una clave de acceso."
        else:
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
        return redirect(url_for('index', error="Clave de acceso no válida."))

    prompt_id, system_prompt, session_start_time = prompt_data
    
    # Asegurarse de que session_start_time es un objeto datetime
    session_start_time = parse_session_start_time(session_start_time)

    # Recuperar ejercicios predefinidos de la base de datos
    exercises_from_db = get_predefined_exercises_by_prompt_id(prompt_id)
    
    # Formatear ejercicios para la plantilla
    exercises = [{'exercise': ex_text, 'solution': ''} for ex_text in exercises_from_db]
    
    return render_template('chat.html', exercises=exercises, session_start_time=session_start_time.isoformat())

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        access_key = data['access_key']
        user_message = data['user_message']
        action = data.get('action')

        prompt_data = get_prompt_by_key(access_key)
        if not prompt_data:
            return jsonify({'ai_response': 'Error: Clave de acceso no válida.'})
        
        prompt_id, system_prompt, session_start_time = prompt_data
        
        # Asegurarse de que session_start_time es un objeto datetime
        session_start_time = parse_session_start_time(session_start_time)

        # Verificar límite de tiempo de sesión
        time_elapsed = datetime.datetime.now() - session_start_time
        if time_elapsed.total_seconds() > SESSION_TIME_LIMIT_MINUTES * 60:
            return jsonify({'ai_response': 'Tu sesión ha expirado. Por favor, contacta a tu tutor para una nueva sesión.'})

        if action == "get_solution":
            ai_response = get_ai_response(system_prompt + "\n\nPor favor, proporciona la solución paso a paso para el siguiente ejercicio:", user_message)
        else:
            ai_response = get_ai_response(system_prompt, user_message)
        
        # Intentar extraer ejercicio y solución para guardar en el historial
        exercise_match = re.search(r'(?:Ejercicio:\s*)?(.*?)(?:\s*Solución:|$)', ai_response, re.DOTALL)
        solution_match = re.search(r'Solución:\s*(.*)', ai_response, re.DOTALL)
        
        logger.debug(f"exercise_match={exercise_match}")
        logger.debug(f"solution_match={solution_match}")

        if exercise_match:
            extracted_exercise_text = exercise_match.group(1).strip()
            # Eliminar la posible repetición de "Ejercicio:" al inicio
            if extracted_exercise_text.lower().startswith("ejercicio:"):
                extracted_exercise_text = extracted_exercise_text[len("ejercicio:"):].strip()

            extracted_solution_text = solution_match.group(1).strip() if solution_match else ""
            
            # Intentar extraer el tipo de ejercicio del texto del ejercicio
            type_match = re.search(r'\((.*?)\):', extracted_exercise_text)
            extracted_exercise_type = type_match.group(1).strip() if type_match else None
            
            # Guardar en el historial
            add_exercise_history(access_key, extracted_exercise_text, extracted_solution_text, extracted_exercise_type)
            logger.debug(f"Ejercicio guardado en historial: Tipo={extracted_exercise_type}")
        
        return jsonify({'ai_response': ai_response})
    
    except Exception as e:
        logger.error(f"Error en api_chat: {e}")
        return jsonify({'ai_response': 'Lo siento, ha ocurrido un error al procesar tu solicitud.'})

@app.route('/admin/create_prompt', methods=['GET', 'POST'])
def admin_create_prompt():
    access_key = None
    error = None
    
    if request.method == 'POST':
        student_email = request.form['student_email'].strip()
        topic = request.form['topic'].strip()
        prompt_content = request.form['prompt_content'].strip()
        exercises_text = request.form.get('exercises_text', '').strip()
        
        # Validar campos obligatorios
        if not all([student_email, topic, prompt_content]):
            error = "Todos los campos marcados con * son obligatorios."
        else:
            access_key = generate_unique_access_key()
            prompt_id = add_prompt(student_email, topic, prompt_content, access_key)
            
            if prompt_id:
                # Agregar ejercicios predefinidos
                exercise_lines = exercises_text.split('\n') if exercises_text else []
                for i, line in enumerate(exercise_lines):
                    if line.strip():
                        add_predefined_exercise(prompt_id, line.strip(), i + 1)
            else:
                error = "Error al crear el prompt. Por favor, intenta nuevamente."
        
    return render_template('admin_create.html', access_key=access_key, error=error)

if __name__ == '__main__':
    app.run(debug=True, port=8000)