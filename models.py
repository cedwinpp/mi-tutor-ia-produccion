from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Prompt, PredefinedExercise  # Solo para tipo, no se ejecuta en runtime

db = SQLAlchemy()

class Prompt(db.Model):
    __tablename__ = 'prompts'
    id = db.Column(db.Integer, primary_key=True)
    student_email = db.Column(db.String(120), nullable=False)
    topic = db.Column(db.String(120), nullable=False)
    prompt_content = db.Column(db.Text, nullable=False)
    access_key = db.Column(db.String(16), unique=True, nullable=False)
    session_start_time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # ✅ USO CORRECTO: referencia a clase sin importación circular
    predefined_exercises = relationship(
        "PredefinedExercise",
        back_populates="prompt",
        lazy="select"
    )

class ExerciseHistory(db.Model):
    __tablename__ = 'exercise_history'
    id = db.Column(db.Integer, primary_key=True)
    access_key = db.Column(db.String(16), ForeignKey('prompts.access_key'), nullable=False)
    exercise_text = db.Column(db.Text, nullable=False)
    solution_text = db.Column(db.Text, nullable=False)
    exercise_type = db.Column(db.String(120), nullable=True)
    difficulty = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class PredefinedExercise(db.Model):
    __tablename__ = 'predefined_exercises'
    id = db.Column(db.Integer, primary_key=True)
    prompt_id = db.Column(db.Integer, ForeignKey('prompts.id'), nullable=False)
    exercise_text = db.Column(db.Text, nullable=False)
    order_in_list = db.Column(db.Integer, nullable=False)
    
    # ✅ USO CORRECTO: referencia a clase sin importación circular
    prompt = relationship(
        "Prompt",
        back_populates="predefined_exercises",
        lazy="select"
    )