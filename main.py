from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# Configuración de variables de entorno
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "defaultdb")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca=/etc/ssl/certs/ca-certificates.crt"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== MODELOS DE BASE DE DATOS ====================
# tabla de personal autorizado para el sistema profesores, administrativos y estudiantes
class PersonalAutorizado(db.Model):
    tablename = 'personal_autorizado'
    cedula = db.Column(db.String(20), primary_key=True)
    correo_institucional = db.Column(db.String(100), unique=True, nullable=False)
    tipo_personal = db.Column(db.String(20), nullable=False) # 'Admin', 'Profesor', 'Estudiante'

# tabla de roles para el sistema
class Role(db.Model):
    tablename = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False) # 'Admin', 'Profesor', 'Estudiante'
    usuarios = db.relationship('Usuario', backref='role', lazy=True)

# tabla de usuarios del sistema
class Usuario(db.Model):
    tablename = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre_completo = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    eventos = db.relationship('Evento', backref='creador', lazy=True)

# tabla de espacios disponibles para eventos
class Espacio(db.Model):
    tablename = 'espacios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False) # Ej: 'Auditorio Benito Juarez'
    tipo = db.Column(db.String(30), nullable=False) # 'Laboratorio', 'Salon', 'Auditorio'
    capacidad = db.Column(db.Integer, nullable=False)
    ubicacion = db.Column(db.String(100), nullable=False)

# tabla de estados de los eventos
class Estado(db.Model):
    tablename = 'estados'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(20), unique=True, nullable=False) # 'Propuesto', 'Solicitado', 'Aprobado', 'En Revision', 'Cancelado'
    eventos = db.relationship('Evento', backref='estado', lazy=True)

# tabla de eventos
class Evento(db.Model):
    tablename = 'eventos'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    tipo_actividad = db.Column(db.String(50), nullable=False) # ´'congreso', 'jornada de investigacion','Conferencia', 'Taller', 'Ponencia'
    fecha = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    estado_id = db.Column(db.Integer, db.ForeignKey('estados.id'), nullable=False)
    espacio_id = db.Column(db.Integer, db.ForeignKey('espacios.id'), nullable=True) # Puede ser nulo si es 'Propuesto'
    creador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    descripcion = db.Column(db.String(500), nullable=False)

# ==================== INICIALIZACIÓN DE DATOS SEMILLA ====================

def inicializar_datos():
    # Crear tablas si no existen
    db.create_all()
    
    # Insertar Roles por defecto si la tabla está vacía
    if not Role.query.first():
        roles = [Role(nombre='Admin'), Role(nombre='Profesor'), Role(nombre='Estudiante')]
        db.session.bulk_save_objects(roles)
        
    # Insertar Estados por defecto si la tabla está vacía
    if not Estado.query.first():
        estados = [Estado(nombre='Propuesto'), Estado(nombre='Solicitado'), Estado(nombre='Aprobado'),Estado(nombre='En Revision'), Estado(nombre='Cancelado')]
        db.session.bulk_save_objects(estados)
        
    db.session.commit()

# ==================== RUTA DE PRUEBA DE CONEXIÓN Y CREACIÓN ====================
@app.route('/')
def home():
    try:
        inicializar_datos()
        db_status = "Tablas validadas/creadas con éxito e inicializadas en Aiven MySQL"
    except Exception as e:
        db_status = f"Error al interactuar con la DB: {str(e)}"

    return jsonify({
        "status": "ok",
        "message": "Backend del Sistema de Gestión de Eventos FaCyT",
        "database_status": db_status
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)




































"""from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# 1. Recuperamos las variables que configuraste en Render (u tu .env local)
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "defaultdb")

# 2. Armamos la URL de conexión adaptada para Aiven MySQL utilizando SSL nativo
# Usamos ssl_verify_cert=True y el llavero de certificados por defecto de Linux (/etc/ssl/certs/ca-certificates.crt)
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?ssl_ca=/etc/ssl/certs/ca-certificates.crt"

app.config['SQLALCHEMY_DATABASE_URL'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.route('/')
def home():
    try:
        # Hacemos una consulta rápida de prueba a la base de datos para verificar conexión
        db.session.execute('SELECT 1')
        db_status = "Conexión exitosa a Aiven MySQL"
    except Exception as e:
        db_status = f"Error de conexión: {str(e)}"

    return jsonify({
        "status": "ok",
        "message": "Backend corriendo en Render con Flask",
        "database_status": db_status
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)


"""

























































"""from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Backend corriendo en Render con Flask con éxito"
    })

if __name__ == '__main__':
    # Esto es solo para correrlo local en WSL2
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
"""
