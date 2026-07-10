#MODIFICADO PORQUE NO ME DEJABA DARLE CLICK AL BOTON DE CREAER EVENTO
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'clave_secreta_super_segura_facyt_2026')

def obtener_conexion():
    return pymysql.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=int(os.getenv('DB_PORT', 3306)),
        database=os.getenv('DB_NAME', 'defaultdb'),
        ssl_verify_identity=False,
        cursorclass=pymysql.cursors.DictCursor
    )

def inicializar_base_de_datos():
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS personal_autorizado (cedula VARCHAR(20) PRIMARY KEY, correo_institucional VARCHAR(100) UNIQUE NOT NULL, tipo_personal VARCHAR(20) NOT NULL);")
            cursor.execute("CREATE TABLE IF NOT EXISTS roles (id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(20) UNIQUE NOT NULL);")
            cursor.execute("CREATE TABLE IF NOT EXISTS usuarios (id INT AUTO_INCREMENT PRIMARY KEY, nombre_completo VARCHAR(100) NOT NULL, correo VARCHAR(100) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, cedula VARCHAR(20) UNIQUE NOT NULL, role_id INT NOT NULL, FOREIGN KEY (role_id) REFERENCES roles(id));")
            cursor.execute("CREATE TABLE IF NOT EXISTS espacios (id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(50) UNIQUE NOT NULL, tipo VARCHAR(30) NOT NULL, capacidad INT NOT NULL, ubicacion VARCHAR(100) NOT NULL);")
            cursor.execute("CREATE TABLE IF NOT EXISTS estados (id INT AUTO_INCREMENT PRIMARY KEY, nombre VARCHAR(20) UNIQUE NOT NULL);")
            cursor.execute("CREATE TABLE IF NOT EXISTS eventos (id INT AUTO_INCREMENT PRIMARY KEY, titulo VARCHAR(150) NOT NULL, tipo_actividad VARCHAR(50) NOT NULL, fecha DATE NOT NULL, hora_inicio TIME NOT NULL, hora_fin TIME NOT NULL, estado_id INT NOT NULL, espacio_id INT NULL, creador_id INT NOT NULL, FOREIGN KEY (estado_id) REFERENCES estados(id), FOREIGN KEY (espacio_id) REFERENCES espacios(id), FOREIGN KEY (creador_id) REFERENCES usuarios(id));")

            if cursor.execute("SELECT COUNT(*) AS total FROM roles;") and cursor.fetchone()['total'] == 0:
                cursor.executemany("INSERT INTO roles (nombre) VALUES (%s);", [('Admin',), ('Profesor',), ('Estudiante',)])

            if cursor.execute("SELECT COUNT(*) AS total FROM estados;") and cursor.fetchone()['total'] == 0:
                cursor.executemany("INSERT INTO estados (nombre) VALUES (%s);", [('Propuesto',), ('Solicitado',), ('Aprobado',), ('Cancelado',)])

            usuarios_autorizados = [
                ('12345678', 'admin.facyt@uc.edu.ve', 'Admin'),
                ('22222222', 'profesor.facyt@uc.edu.ve', 'Profesor'),
                ('33333333', 'estudiante.facyt@uc.edu.ve', 'Estudiante')
            ]
            cursor.executemany("INSERT IGNORE INTO personal_autorizado (cedula, correo_institucional, tipo_personal) VALUES (%s, %s, %s);", usuarios_autorizados)
            
# ---------------CORRECCIÓN DE RAÍZ: Insertar solo si NO existe para mantener estable el ID autoincremental
            cursor.execute("SELECT id FROM usuarios WHERE correo = 'admin.facyt@uc.edu.ve';")
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM roles WHERE nombre = 'Admin';")
                role_id = cursor.fetchone()['id']
                pass_hash = generate_password_hash('admin123')
                cursor.execute("INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) VALUES (%s, %s, %s, %s, %s);", ('Administrador de Pruebas', 'admin.facyt@uc.edu.ve', pass_hash, '12345678', role_id))
            
            conexion.commit()
            """
            cursor.execute("DELETE FROM usuarios WHERE correo = 'admin.facyt@uc.edu.ve';")
            cursor.execute("SELECT id FROM roles WHERE nombre = 'Admin';")
            role_id = cursor.fetchone()['id']
            pass_hash = generate_password_hash('admin123')
            cursor.execute("INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) VALUES (%s, %s, %s, %s, %s);", ('Administrador de Pruebas', 'admin.facyt@uc.edu.ve', pass_hash, '12345678', role_id))
            conexion.commit()"""
    finally:
        conexion.close()

@app.route('/')
def home():
    inicializar_base_de_datos()
    if 'usuario_id' in session:
        return render_template('dashboard.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                sql = "SELECT u.*, r.nombre AS rol_nombre FROM usuarios u JOIN roles r ON u.role_id = r.id WHERE u.correo = %s;"
                cursor.execute(sql, (correo,))
                usuario = cursor.fetchone()
                if usuario and check_password_hash(usuario['password_hash'], password):
                    session['usuario_id'] = usuario['id']
                    session['nombre'] = usuario['nombre_completo']
                    session['rol'] = usuario['rol_nombre']
                    session['cedula'] = usuario['cedula']
                    return redirect(url_for('home'))
                else:
                    flash('Correo o contraseña incorrectos.', 'error')
        finally:
            conexion.close()
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        cedula = request.form['cedula'].strip()
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip()
        password = request.form['password']

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT * FROM personal_autorizado WHERE cedula = %s AND correo_institucional = %s;", (cedula, correo))
                personal = cursor.fetchone()

                if not personal:
                    flash('Error: Tus datos no figuran en el personal autorizado de la FaCyT-UC.', 'error')
                    return redirect(url_for('register'))

                cursor.execute("SELECT id FROM usuarios WHERE cedula = %s OR correo = %s;", (cedula, correo))
                if cursor.fetchone():
                    flash('Esta cuenta ya se encuentra registrada. Intenta iniciar sesión.', 'error')
                    return redirect(url_for('register'))

                cursor.execute("SELECT id FROM roles WHERE nombre = %s;", (personal['tipo_personal'],))
                role_id = cursor.fetchone()['id']

                password_hash = generate_password_hash(password)
                sql_insert = "INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) VALUES (%s, %s, %s, %s, %s);"
                cursor.execute(sql_insert, (nombre, correo, password_hash, cedula, role_id))
                conexion.commit()

                flash('¡Registro exitoso! Ya puedes iniciar sesión.', 'success')
                return redirect(url_for('login'))
        finally:
            conexion.close()
    return render_template('register.html')

@app.route('/proponer', methods=['GET', 'POST'])
def proponer_evento():
    # Protección de ruta: si no está logueado, va al login
    if 'usuario_id' in session:
        if request.method == 'POST':
            titulo = request.form['titulo'].strip()
            tipo_actividad = request.form['tipo_actividad']
            fecha = request.form['fecha']
            hora_inicio = request.form['hora_inicio']
            hora_fin = request.form['hora_fin']
            creador_id = session['usuario_id']

            # Validación básica de tiempos lógicos
            if hora_inicio >= hora_fin:
                flash('Error: La hora de inicio debe ser anterior a la de culminación.', 'error')
                return render_template('proponer.html')

            conexion = obtener_conexion()
            try:
                with conexion.cursor() as cursor:
                    # Buscamos el ID asignado al estado por defecto 'Propuesto'
                    cursor.execute("SELECT id FROM estados WHERE nombre = 'Propuesto';")
                    estado_id = cursor.fetchone()['id']
                    # Insertamos el evento ligando la propuesta al usuario actual
                    sql_evento = """
                        INSERT INTO eventos (titulo, tipo_actividad, fecha, hora_inicio, hora_fin, estado_id, creador_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """
                    cursor.execute(sql_evento, (titulo, tipo_actividad, fecha, hora_inicio, hora_fin, estado_id, creador_id))
                    conexion.commit()
                    
                flash('¡Propuesta enviada con éxito! Está en revisión administrativa.', 'success')
                return redirect(url_for('home'))
            except Exception as e:
                flash(f'Error en el sistema al guardar la actividad: {str(e)}', 'error')
            finally:
                conexion.close()

        return render_template('proponer.html')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))

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
