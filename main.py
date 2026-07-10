import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', '27894120')  # Cambia esto por una clave secreta segura en producción
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

            if cursor.execute("SELECT COUNT(*) AS total FROM espacios;") and cursor.fetchone()['total'] == 0:
                espacios_facyt = [
                    ('Auditorio FaCyT', 'Auditorio', 150, 'Planta Baja, Edificio de Aulas'),
                    ('Laboratorio de Computación 1', 'Laboratorio', 30, 'Primer Piso, Ala Norte'),
                    ('Aula Magna 202', 'Aula de Clases', 45, 'Segundo Piso, Edificio de Aulas')
                ]
                cursor.executemany("INSERT INTO espacios (nombre, tipo, capacidad, ubicacion) VALUES (%s, %s, %s, %s);", espacios_facyt)

            usuarios_autorizados = [
                ('12345678', 'admin.facyt@uc.edu.ve', 'Admin'),
                ('22222222', 'profesor.facyt@uc.edu.ve', 'Profesor'),
                ('33333333', 'estudiante.facyt@uc.edu.ve', 'Estudiante')
            ]
            cursor.executemany("INSERT IGNORE INTO personal_autorizado (cedula, correo_institucional, tipo_personal) VALUES (%s, %s, %s);", usuarios_autorizados)

            cursor.execute("SELECT id FROM usuarios WHERE correo = 'admin.facyt@uc.edu.ve';")
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM roles WHERE nombre = 'Admin';")
                role_id = cursor.fetchone()['id']
                pass_hash = generate_password_hash('admin123')
                cursor.execute("INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) VALUES (%s, %s, %s, %s, %s);", ('Administrador de Pruebas', 'admin.facyt@uc.edu.ve', pass_hash, '12345678', role_id))
            
            conexion.commit()
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
    if 'usuario_id' in session:
        if request.method == 'POST':
            titulo = request.form['titulo'].strip()
            tipo_actividad = request.form['tipo_actividad']
            fecha = request.form['fecha']
            hora_inicio = request.form['hora_inicio']
            hora_fin = request.form['hora_fin']
            creador_id = session['usuario_id']

            if hora_inicio >= hora_fin:
                flash('Error: La hora de inicio debe ser anterior a la de culminación.', 'error')
                return render_template('proponer.html')

            conexion = obtener_conexion()
            try:
                with conexion.cursor() as cursor:
                    cursor.execute("SELECT id FROM estados WHERE nombre = 'Propuesto';")
                    estado_id = cursor.fetchone()['id']

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

@app.route('/historial')
def ver_historial():
    if 'usuario_id' in session:
        creador_id = session['usuario_id']
        conexion = obtener_conexion()
        eventos = []
        try:
            with conexion.cursor() as cursor:
                sql = """
                    SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                           est.nombre AS estado_nombre, esp.nombre AS espacio_nombre
                    FROM eventos e
                    JOIN estados est ON e.estado_id = est.id
                    LEFT JOIN espacios esp ON e.espacio_id = esp.id
                    WHERE e.creador_id = %s
                    ORDER BY e.fecha DESC, e.hora_inicio DESC;
                """
                cursor.execute(sql, (creador_id,))
                eventos = cursor.fetchall()
                for ev in eventos:
                    ev['fecha'] = str(ev['fecha'])
                    ev['hora_inicio'] = str(ev['hora_inicio'])
                    ev['hora_fin'] = str(ev['hora_fin'])
        except Exception as e:
            flash(f'Error al cargar el historial: {str(e)}', 'error')
        finally:
            conexion.close()
        return render_template('historial.html', eventos=eventos)
    return redirect(url_for('login'))

@app.route('/evento/editar/<int:evento_id>', methods=['GET', 'POST'])
def editar_evento(evento_id):
    if 'usuario_id' in session:
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                # Verificar pertenencia y estado (Solo se editan si están 'Propuestos')
                cursor.execute("""
                    SELECT e.*, est.nombre AS estado_nombre 
                    FROM eventos e 
                    JOIN estados est ON e.estado_id = est.id 
                    WHERE e.id = %s AND e.creador_id = %s;
                """, (evento_id, session['usuario_id']))
                evento = cursor.fetchone()

                if not evento or evento['estado_nombre'] != 'Propuesto':
                    flash('No puedes modificar un evento que ya fue procesado o no te pertenece.', 'error')
                    return redirect(url_for('ver_historial'))

                if request.method == 'POST':
                    titulo = request.form['titulo'].strip()
                    tipo_actividad = request.form['tipo_actividad']
                    fecha = request.form['fecha']
                    hora_inicio = request.form['hora_inicio']
                    hora_fin = request.form['hora_fin']

                    if hora_inicio >= hora_fin:
                        flash('Error: La hora de inicio debe ser anterior.', 'error')
                        return redirect(url_for('editar_evento', evento_id=evento_id))

                    cursor.execute("""
                        UPDATE eventos 
                        SET titulo = %s, tipo_actividad = %s, fecha = %s, hora_inicio = %s, hora_fin = %s 
                        WHERE id = %s;
                    """, (titulo, tipo_actividad, fecha, hora_inicio, hora_fin, evento_id))
                    conexion.commit()
                    flash('Propuesta actualizada correctamente.', 'success')
                    return redirect(url_for('ver_historial'))

                # Formatear datos para el HTML
                evento['fecha'] = str(evento['fecha'])
                evento['hora_inicio'] = str(evento['hora_inicio'])[:5]
                evento['hora_fin'] = str(evento['hora_fin'])[:5]
                return render_template('editar_evento.html', evento=evento)
        finally:
            conexion.close()
    return redirect(url_for('login'))

@app.route('/evento/eliminar/<int:evento_id>')
def eliminar_evento(evento_id):
    if 'usuario_id' in session:
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                # Comprobar seguridad antes de borrar
                cursor.execute("""
                    SELECT e.*, est.nombre AS estado_nombre 
                    FROM eventos e 
                    JOIN estados est ON e.estado_id = est.id 
                    WHERE e.id = %s AND e.creador_id = %s;
                """, (evento_id, session['usuario_id']))
                evento = cursor.fetchone()

                if evento and evento['estado_nombre'] == 'Propuesto':
                    cursor.execute("DELETE FROM eventos WHERE id = %s;", (evento_id,))
                    conexion.commit()
                    flash('La propuesta ha sido eliminada permanentemente.', 'success')
                else:
                    flash('No puedes eliminar este evento.', 'error')
        finally:
            conexion.close()
        return redirect(url_for('ver_historial'))
    return redirect(url_for('login'))

@app.route('/admin/pendientes')
def admin_pendientes():
    if 'usuario_id' in session and session.get('rol') == 'Admin':
        conexion = obtener_conexion()
        solicitudes = []
        espacios = []
        try:
            with conexion.cursor() as cursor:
                sql_solicitudes = """
                    SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                           u.nombre_completo AS solicitante, u.cedula
                    FROM eventos e
                    JOIN usuarios u ON e.creador_id = u.id
                    JOIN estados est ON e.estado_id = est.id
                    WHERE est.nombre = 'Propuesto'
                    ORDER BY e.fecha ASC;
                """
                cursor.execute(sql_solicitudes)
                solicitudes = cursor.fetchall()
                for s in solicitudes:
                    s['fecha'] = str(s['fecha'])
                    s['hora_inicio'] = str(s['hora_inicio'])
                    s['hora_fin'] = str(s['hora_fin'])

                cursor.execute("SELECT id, nombre, capacidad FROM espacios ORDER BY nombre ASC;")
                espacios = cursor.fetchall()
        finally:
            conexion.close()
        return render_template('admin_pendientes.html', solicitudes=solicitudes, espacios=espacios)
    return redirect(url_for('login'))

@app.route('/admin/procesar/<int:evento_id>', methods=['POST'])
def procesar_solicitud(evento_id):
    if 'usuario_id' in session and session.get('rol') == 'Admin':
        accion = request.form.get('accion')
        espacio_id = request.form.get('espacio_id')
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                if accion == 'aprobar':
                    cursor.execute("SELECT id FROM estados WHERE nombre = 'Aprobado';")
                    estado_id = cursor.fetchone()['id']
                    cursor.execute("UPDATE eventos SET estado_id = %s, espacio_id = %s WHERE id = %s;", (estado_id, espacio_id, evento_id))
                    flash('Evento aprobado correctamente con espacio asignado.', 'success')
                elif accion == 'cancelar':
                    cursor.execute("SELECT id FROM estados WHERE nombre = 'Cancelado';")
                    estado_id = cursor.fetchone()['id']
                    cursor.execute("UPDATE eventos SET estado_id = %s WHERE id = %s;", (estado_id, evento_id))
                    flash('Propuesta rechazada y cancelada con éxito.', 'success')
                conexion.commit()
        finally:
            conexion.close()
        return redirect(url_for('admin_pendientes'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
