import os
import secrets
import string
import re
import datetime
from datetime import timezone
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from dotenv import load_dotenv
from openai import OpenAI
from models import db, Prompt, ExerciseHistory, PredefinedExercise

# Cargar variables de entorno desde .env
load_dotenv()

app = Flask(__name__)

# --- Configuración --- #

# Configurar una clave secreta para la sesión
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# 🚨 IMPORTANTE: Usa el dialecto 'postgresql+psycopg' para psycopg3
database_url = os.getenv('DATABASE_URL')
if not database_url:
    # Fallback a SQLite para desarrollo local
    database_url = 'sqlite:///tutor_ia.db'
else:
    # Asegura que la URL use el nuevo dialecto para psycopg3
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Contraseña de administrador
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# Límite de tiempo de la sesión en minutos
SESSION_TIME_LIMIT_MINUTES = 30

# --- Inicialización ---

# Inicializar la base de datos con la app
db.init_app(app)

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Instanciar el cliente de OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# --- Funciones Auxiliares ---

def generate_unique_access_key(length=16):
    """Genera una clave de acceso única y segura."""
    alphabet = string.ascii_letters + string.digits
    while True:
        access_key = ''.join(secrets.choice(alphabet) for _ in range(length))
        if not Prompt.query.filter_by(access_key=access_key).first():
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

# --- Rutas ---

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        access_key = request.form['access_key'].strip()
        if not access_key:
            error = "Por favor, ingresa una clave de acceso."
        else:
            prompt = Prompt.query.filter_by(access_key=access_key).first()
            if prompt:
                return redirect(url_for('chat', access_key=access_key))
            else:
                error = "Clave de acceso no válida. Inténtalo de nuevo."
    return render_template('index.html', error=error)

@app.route('/chat/<access_key>')
def chat(access_key):
    prompt = Prompt.query.filter_by(access_key=access_key).first_or_404()

    session_start_time = prompt.session_start_time
    session_end_time = session_start_time + datetime.timedelta(minutes=SESSION_TIME_LIMIT_MINUTES)

    # Recuperar ejercicios a través de la relación de SQLAlchemy
    exercises_from_db = [exercise.exercise_text for exercise in prompt.predefined_exercises]
    
    logger.debug(f"Ejercicios recuperados para prompt_id {prompt.id}: {exercises_from_db}")
    
    exercises = [{'exercise': ex_text, 'solution': ''} for ex_text in exercises_from_db]
    
    initial_message = "¡Hola! Soy tu tutor de IA. Estoy aquí para ayudarte con tus ejercicios. Puedes seleccionar un ejercicio de la lista o escribir uno tú mismo."

    return render_template('chat.html', 
                         exercises=exercises, 
                         session_start_time=session_start_time.isoformat(),
                         session_end_time=session_end_time.isoformat(),
                         access_key=access_key,
                         initial_message=initial_message)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.get_json()
        access_key = data['access_key']
        user_message = data['user_message']
        action = data.get('action')

        prompt = Prompt.query.filter_by(access_key=access_key).first()
        if not prompt:
            return jsonify({'ai_response': 'Error: Clave de acceso no válida.'})
        
        time_elapsed = datetime.datetime.now(timezone.utc) - prompt.session_start_time
        if time_elapsed.total_seconds() > SESSION_TIME_LIMIT_MINUTES * 60:
            return jsonify({'ai_response': 'Tu sesión ha expirado. Por favor, contacta a tu tutor para una nueva sesión.'})

        system_prompt = prompt.prompt_content
        if action == "get_solution":
            ai_response = get_ai_response(system_prompt + "\n\nPor favor, proporciona la solución paso a paso para el siguiente ejercicio:", user_message)
        elif action == "initial_message":
            ai_response = get_ai_response(system_prompt, "Hola, por favor, preséntate y saluda al alumno. Adicionalmente, indícale que puede seleccionar uno de los ejercicios de la lista de la izquierda o escribir uno directamente en el chat. Si no hay ejercicios, indícale que puede escribir uno directamente en el chat.")
        else:
            ai_response = get_ai_response(system_prompt, user_message)
        
        # Guardar en historial (lógica simplificada para el ejemplo)
        new_history = ExerciseHistory(
            access_key=access_key,
            exercise_text=user_message, # Guardamos el mensaje del usuario como el ejercicio
            solution_text=ai_response # Guardamos la respuesta completa de la IA
        )
        db.session.add(new_history)
        db.session.commit()
        
        return jsonify({'ai_response': ai_response})
    
    except Exception as e:
        logger.error(f"Error en api_chat: {e}")
        return jsonify({'ai_response': 'Lo siento, ha ocurrido un error al procesar tu solicitud.'})

# Ruta de administración
@app.route('/admin')
def admin():
    if session.get('logged_in'):
        return render_template('admin_dashboard.html')
    else:
        return render_template('admin_login.html')

# Login de administrador
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('Inicio de sesión exitoso.', 'success')
            return redirect(url_for('admin_create_prompt'))
        else:
            flash('Contraseña incorrecta.', 'danger')
    return render_template('admin_login.html')

# Logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('admin_login'))

# Crear prompt desde el admin
@app.route('/admin/create_prompt', methods=['GET', 'POST'])
def admin_create_prompt():
    if not session.get('logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        student_email = request.form['student_email'].strip()
        topic = request.form['topic'].strip()
        prompt_content = request.form['prompt_content'].strip()
        exercises_text = request.form.get('exercises_text', '').strip()
        
        if not all([student_email, topic, prompt_content]):
            flash("Todos los campos marcados con * son obligatorios.", "danger")
        else:
            try:
                access_key = generate_unique_access_key()
                new_prompt = Prompt(
                    student_email=student_email,
                    topic=topic,
                    prompt_content=prompt_content,
                    access_key=access_key,
                    session_start_time=datetime.datetime.now(timezone.utc)
                )
                db.session.add(new_prompt)
                db.session.commit()

                exercise_lines = exercises_text.split('\n') if exercises_text else []
                added_exercises = 0
                for i, line in enumerate(exercise_lines):
                    if line.strip():
                        new_exercise = PredefinedExercise(
                            prompt_id=new_prompt.id,
                            exercise_text=line.strip(),
                            order_in_list=i + 1
                        )
                        db.session.add(new_exercise)
                        added_exercises += 1
                
                if added_exercises > 0:
                    db.session.commit()

                success_message = f"Prompt creado exitosamente. Clave de acceso: {access_key}"
                if added_exercises > 0:
                    success_message += f". Se agregaron {added_exercises} ejercicios predefinidos."
                flash(success_message, "success")
                return redirect(url_for('admin_create_prompt'))

            except Exception as e:
                db.session.rollback()
                logger.error(f"Error al crear el prompt: {e}")
                flash("Error al crear el prompt. Por favor, intenta nuevamente.", "danger")
        
    return render_template('admin_create.html')


# Endpoint para generar ejercicio con IA
@app.route('/generate_exercise', methods=['POST'])
def generate_exercise():
    data = request.get_json()
    access_key = data.get('access_key')
    prompt_id = data.get('prompt_id')

    if not access_key or not prompt_id:
        return jsonify({'error': 'Faltan datos'}), 400

    prompt = Prompt.query.filter_by(access_key=access_key, id=prompt_id).first()
    if not prompt:
        return jsonify({'error': 'Clave de acceso inválida'}), 404

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un tutor de programación experto. Genera un ejercicio práctico breve y claro basado en el tema proporcionado."}, 
                {"role": "user", "content": f"Genera un ejercicio de programación sobre: {prompt.topic}. No expliques, solo da el ejercicio."}
            ],
            temperature=0.7,
            max_tokens=200
        )
        exercise_text = response.choices[0].message.content.strip()

        # Guardar ejercicio en base de datos
        exercise = PredefinedExercise(
            prompt_id=prompt.id,
            exercise_text=exercise_text,
            order_in_list=1
        )
        db.session.add(exercise)
        db.session.commit()

        return jsonify({
            'success': True,
            'exercise': exercise_text,
            'exercise_id': exercise.id
        })

    except Exception as e:
        logger.error(f"Error generando ejercicio: {e}")
        return jsonify({'error': 'Error al generar ejercicio'}), 500

# Endpoint para guardar solución del estudiante
@app.route('/submit_solution', methods=['POST'])
def submit_solution():
    data = request.get_json()
    access_key = data.get('access_key')
    exercise_text = data.get('exercise_text')
    solution_text = data.get('solution_text')

    if not all([access_key, exercise_text, solution_text]):
        return jsonify({'error': 'Datos incompletos'}), 400

    # Guardar historial de solución
    history = ExerciseHistory(
        access_key=access_key,
        exercise_text=exercise_text,
        solution_text=solution_text
    )
    db.session.add(history)
    db.session.commit()

    return jsonify({'success': True})

# Verificar acceso por clave
@app.route('/check_access/<key>')
def check_access(key):
    prompt = Prompt.query.filter_by(access_key=key).first()
    if prompt:
        return jsonify({
            'exists': True,
            'student_email': prompt.student_email,
            'topic': prompt.topic,
            'session_start_time': prompt.session_start_time.isoformat() if prompt.session_start_time else None
        })
    else:
        return jsonify({'exists': False}), 404

# Ruta pública para resolver ejercicio
@app.route('/solve/<key>')
def solve(key):
    prompt = Prompt.query.filter_by(access_key=key).first()
    if not prompt:
        return "Clave inválida", 404

    exercise = PredefinedExercise.query.filter_by(prompt_id=prompt.id).first()
    if not exercise:
        return "No hay ejercicio generado aún.", 404

    return render_template('solve.html', prompt=prompt, exercise=exercise)

# Ruta para ver historial de soluciones
@app.route('/history/<key>')
def history(key):
    exercises = ExerciseHistory.query.filter_by(access_key=key).all()
    return render_template('history.html', key=key, exercises=exercises)

# Si se ejecuta directamente (modo desarrollo)
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crea las tablas si no existen
    app.run(debug=True, port=8000)