import os
import secrets
import string
import re
import datetime
import logging
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from dotenv import load_dotenv
from openai import OpenAI

# ✅ IMPORTA LOS MODELOS PRIMERO (esto carga db = SQLAlchemy())
from models import db, Prompt, ExerciseHistory, PredefinedExercise

load_dotenv()

# ✅ CREA LA APP DESPUÉS DE IMPORTAR MODELOS
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))

# ✅ CONFIGURA LA BASE DE DATOS
database_url = os.getenv('DATABASE_URL')
if not database_url:
    database_url = 'sqlite:///tutor_ia.db'
else:
    if database_url.startswith('postgresql://'):
        database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    elif database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
SESSION_TIME_LIMIT_MINUTES = 30

# ✅ ¡CRUCIAL: INICIALIZA db CON app ANTES DE CUALQUIER USO!
db.init_app(app)

# ✅ AHORA SÍ, CREA LAS TABLAS EN UN CONTEXTOS DE APLICACIÓN
with app.app_context():
    db.create_all()

# ✅ INICIALIZA CLIENTE DE OPENAI
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# === [TU LÓGICA ORIGINAL A PARTIR DE AQUÍ — SIN CAMBIOS] ===

# Función para generar clave de acceso aleatoria
def generate_access_key():
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(16))

# Ruta principal
@app.route('/')
def index():
    return render_template('index.html')

# Ruta de administración
@app.route('/admin')
def admin():
    if session.get('logged_in'):
        return render_template('admin_dashboard.html')
    else:
        return render_template('admin_login.html')

# Login de administrador
@app.route('/admin/login', methods=['POST'])
def admin_login():
    password = request.form.get('password')
    if password == ADMIN_PASSWORD:
        session['logged_in'] = True
        flash('Acceso concedido.', 'success')
        return redirect(url_for('admin'))
    else:
        flash('Contraseña incorrecta.', 'error')
        return redirect(url_for('admin'))

# Logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('logged_in', None)
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('admin'))

# Crear prompt desde el admin
@app.route('/admin/create_prompt', methods=['GET', 'POST'])
def create_prompt():
    if not session.get('logged_in'):
        return redirect(url_for('admin'))

    if request.method == 'POST':
        student_email = request.form.get('student_email').strip()
        topic = request.form.get('topic').strip()
        prompt_content = request.form.get('prompt_content').strip()

        if not all([student_email, topic, prompt_content]):
            flash('Todos los campos son obligatorios.', 'error')
            return render_template('admin_create.html')

        # Validar email simple
        if not re.match(r"[^@]+@[^@]+\.[^@]+", student_email):
            flash('Email inválido.', 'error')
            return render_template('admin_create.html')

        # Generar clave única
        access_key = generate_access_key()
        while Prompt.query.filter_by(access_key=access_key).first():
            access_key = generate_access_key()

        # Crear prompt en DB
        new_prompt = Prompt(
            student_email=student_email,
            topic=topic,
            prompt_content=prompt_content,
            access_key=access_key
        )
        db.session.add(new_prompt)
        db.session.commit()

        flash(f'Prompt creado exitosamente. Clave de acceso: {access_key}', 'success')
        return redirect(url_for('create_prompt'))

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
    app.run(debug=True, port=8000)