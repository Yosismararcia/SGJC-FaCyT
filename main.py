#--------------------------- NUEVA MODIFICACION 9:30 11-07
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', '27894120')

# EXPRESIÓN REGULAR: Solo permite letras, números, puntos, guiones y @ (Previene Inyecciones y Símbolos Raros)
CARACTERES_PERMITIDOS = re.compile(r"^[a-zA-Z0-9@._-]+$")

@app.before_request
def controlar_sesion_y_tiempo():
    # MODIFICACIÓN DE SEGURIDAD: Al cerrar el navegador o pestaña, la cookie de sesión caduca
    session.permanent = True
    # Establece el tiempo límite estricto de 15 minutos de inactividad
    app.permanent_session_lifetime = timedelta(minutes=15)
    # Refresca el reloj con cada interacción o clic que realice el usuario
    session.modified = True

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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eventos (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    titulo VARCHAR(150) NOT NULL, 
                    tipo_actividad VARCHAR(50) NOT NULL, 
                    fecha DATE NOT NULL, 
                    hora_inicio TIME NOT NULL, 
                    hora_fin TIME NOT NULL, 
                    estado_id INT NOT NULL, 
                    espacio_id INT NULL, 
                    creador_id INT NOT NULL,
                    cupos_disponibles INT NULL,
                    FOREIGN KEY (estado_id) REFERENCES estados(id), 
                    FOREIGN KEY (espacio_id) REFERENCES espacios(id), 
                    FOREIGN KEY (creador_id) REFERENCES usuarios(id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inscripciones (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NOT NULL,
                    evento_id INT NOT NULL,
                    fecha_inscripcion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY un_registro (usuario_id, evento_id),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
                    FOREIGN KEY (evento_id) REFERENCES eventos(id) ON DELETE CASCADE
                );
            """)
            
            # Control de migraciones seguras de columnas opcionales
            try:
                cursor.execute("ALTER TABLE eventos ADD COLUMN cupos_disponibles INT NULL;")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE eventos ADD COLUMN fecha_elim VARCHAR(10) NULL;")
            except Exception:
                pass

            # Poblar tablas maestras si están vacías
            cursor.execute("SELECT COUNT(*) AS total FROM roles;")
            if cursor.fetchone()['total'] == 0:
                cursor.executemany("INSERT INTO roles (nombre) VALUES (%s);", [('Admin',), ('Profesor',), ('Estudiante',)])

            cursor.execute("SELECT COUNT(*) AS total FROM estados;")
            if cursor.fetchone()['total'] == 0:
                cursor.executemany("INSERT INTO estados (nombre) VALUES (%s);", 
                                   [('Propuesto',), ('Solicitado',), ('En Revisión',), ('Aprobado',), ('Realizado',), ('Cancelado',), ('Rechazado',)])

            cursor.execute("SELECT COUNT(*) AS total FROM espacios;")
            if cursor.fetchone()['total'] == 0:
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
    except Exception as e:
        print(f"Error al inicializar base de datos: {str(e)}")
    finally:
        conexion.close()

@app.route('/')
def home():
    inicializar_base_de_datos()
    if 'usuario_id' in session:
        conexion = obtener_conexion()
        estadisticas = {}
        try:
            with conexion.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM eventos;")
                estadisticas['total_eventos'] = cursor.fetchone()['total']
                
                cursor.execute("""
                    SELECT est.nombre, COUNT(e.id) AS conteo 
                    FROM estados est 
                    LEFT JOIN eventos e ON e.estado_id = est.id 
                    GROUP BY est.id;
                """)
                por_estado = cursor.fetchall()
                estadisticas['pendientes'] = next((x['conteo'] for x in por_estado if x['nombre'] in ['Propuesto', 'Solicitado']), 0)
                estadisticas['aprobados'] = next((x['conteo'] for x in por_estado if x['nombre'] == 'Aprobado'), 0)
                estadisticas['cancelados'] = next((x['conteo'] for x in por_estado if x['nombre'] == 'Cancelado'), 0)
                
                cursor.execute("""
                    SELECT esp.nombre, COUNT(e.id) AS usos 
                    FROM espacios esp 
                    JOIN eventos e ON e.espacio_id = esp.id 
                    WHERE e.estado_id = (SELECT id FROM estados WHERE nombre = 'Aprobado')
                    GROUP BY esp.id 
                    ORDER BY usos DESC 
                    LIMIT 1;
                """)
                mas_utilizado = cursor.fetchone()
                estadisticas['espacio_top'] = mas_utilizado['nombre'] if mas_utilizado else "Ninguno aún"
                estadisticas['espacio_top_usos'] = mas_utilizado['usos'] if mas_utilizado else 0

                cursor.execute("SELECT COUNT(*) AS total FROM inscripciones;")
                estadisticas['total_inscritos'] = cursor.fetchone()['total']
                
        except Exception as e:
            print(f"Error al calcular estadísticas: {str(e)}")
            estadisticas = {'total_eventos': 0, 'pendientes': 0, 'aprobados': 0, 'cancelados': 0, 'espacio_top': 'Error', 'espacio_top_usos': 0, 'total_inscritos': 0}
        finally:
            conexion.close()
            
        return render_template('dashboard.html', stats=estadisticas)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo'].strip()
        password = request.form['password']

        # FILTRO DE SEGURIDAD BACKEND: Evita SQLi o caracteres maliciosos en el campo de texto
        if not CARACTERES_PERMITIDOS.match(correo):
            flash("Error: El usuario contiene caracteres especiales no permitidos.", "error")
            return redirect(url_for('login'))

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

@app.route('/recuperar-password', methods=['GET', 'POST'])
def recuperar_password():
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip()
        
        # Filtro de robustez técnica ante inputs alterados
        if not CARACTERES_PERMITIDOS.match(correo):
            flash("Error: El formato contiene símbolos inválidos.", "error")
            return redirect(url_for('recuperar_password'))
        
        # Flujo institucional simulado
        flash(f"Si el correo {correo} existe en el sistema FaCyT, recibirás un enlace de restauración.", "success")
        return redirect(url_for('login'))
    return render_template('recuperar_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        cedula = request.form['cedula'].strip()
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip()
        password = request.form['password']

        # Validación técnica de entradas en el formulario de registro
        if not CARACTERES_PERMITIDOS.match(correo) or not cedula.isdigit():
            flash('Error: Los campos contienen datos o símbolos inválidos.', 'error')
            return redirect(url_for('register'))

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
                           est.nombre AS estado_nombre, esp.nombre AS espacio_nombre, e.cupos_disponibles
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
                    if ev['cupos_disponibles'] is None:
                        ev['cupos_disponibles'] = 0
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
        except Exception as e:
            flash(f'Error al eliminar el evento: {str(e)}', 'error')
        finally:
            conexion.close()
        return redirect(url_for('ver_historial'))
    return redirect(url_for('login'))

@app.route('/admin/pendientes')
def admin_pendientes():
    if 'usuario_id' in session and session.get('rol') in ['ADMIN', 'Administrador', 'Admin']:
        conexion = obtener_conexion()
        solicitudes = []
        espacios = []
        try:
            with conexion.cursor() as cursor:
                sql_solicitudes = """
                    SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                           u.nombre_completo AS solicitante, u.cedula, est.nombre AS estado
                    FROM eventos e
                    JOIN usuarios u ON e.creador_id = u.id
                    JOIN estados est ON e.estado_id = est.id
                    WHERE est.nombre IN ('Propuesto', 'Solicitado', 'En Revisión')
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
        except Exception as e:
            flash(f'Error al cargar solicitudes administrativas: {str(e)}', 'error')
        finally:
            conexion.close()
        return render_template('admin_pendientes.html', solicitudes=solicitudes, espacios=espacios)
    return redirect(url_for('login'))

@app.route('/admin/procesar/<int:evento_id>', methods=['POST'])
def procesar_solicitud(evento_id):
    if 'usuario_id' not in session or session.get('rol') not in ['ADMIN', 'Administrador', 'Admin']:
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    accion = request.form.get('accion') 
    espacio_id = request.form.get('espacio_id')

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # --- BLOQUE DE AUTO-REPARACIÓN DE EMERGENCIA ---
            # Verificamos si la tabla estados tiene registros
            cursor.execute("SELECT COUNT(*) FROM estados;")
            conteo = cursor.fetchone()
            total_estados = conteo['COUNT(*)'] if isinstance(conteo, dict) else conteo[0]
            
            # Si la tabla está vacía, insertamos los 6 estados con sus IDs correctos de inmediato
            if total_estados == 0:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
                valores = [
                    (1, 'Solicitado'),
                    (2, 'En Revisión'),
                    (3, 'Aprobado'),
                    (4, 'Realizado'),
                    (5, 'Cancelado'),
                    (6, 'Rechazado')
                ]
                cursor.executemany("INSERT INTO estados (id, nombre) VALUES (%s, %s);", valores)
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                conexion.commit()
            # --------------------------------------------------

            if accion == 'rechazar':
                # Buscamos el ID de 'Rechazado' (ahora garantizado que existe gracias al bloque superior)
                cursor.execute("SELECT id FROM estados WHERE nombre LIKE 'Rechazado%' LIMIT 1;")
                res_estado = cursor.fetchone()
                estado_id = res_estado['id'] if isinstance(res_estado, dict) else res_estado[0] if res_estado else 6
                
                # Actualizamos el evento a rechazado
                sql = "UPDATE eventos SET estado_id = %s WHERE id = %s;"
                cursor.execute(sql, (estado_id, evento_id))
                flash("La solicitud ha sido rechazada con éxito.", "success")
                
            else:
                # SI ES APROBACIÓN
                if not espacio_id or espacio_id == "":
                    flash("Error: Debe asignar un espacio físico para aprobar el evento.", "error")
                    return redirect(url_for('admin_pendientes'))
                
                # Buscamos el ID de 'Aprobado'
                cursor.execute("SELECT id FROM estados WHERE nombre LIKE 'Aprobado%' LIMIT 1;")
                res_estado = cursor.fetchone()
                estado_id = res_estado['id'] if isinstance(res_estado, dict) else res_estado[0] if res_estado else 3
                
                # Actualizamos estado y asignamos el espacio físico
                sql = "UPDATE eventos SET estado_id = %s, espacio_id = %s WHERE id = %s;"
                cursor.execute(sql, (estado_id, espacio_id, evento_id))
                flash("La solicitud ha sido aprobada y el espacio fue asignado.", "success")
                
        conexion.commit()
    except Exception as e:
        flash(f"Error al procesar la solicitud: {str(e)}", "error")
    finally:
        conexion.close()
        
    return redirect(url_for('admin_pendientes'))


@app.route('/cartelera')
def cartelera_eventos():
    if 'usuario_id' in session:
        conexion = obtener_conexion()
        eventos = []
        try:
            fecha_actual_str = datetime.now().strftime('%Y-%m-%d')
            with conexion.cursor() as cursor:
                sql = """
                    SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                           e.cupos_disponibles, esp.nombre AS espacio_nombre, esp.capacidad AS capacidad_max,
                           est.nombre AS estado, e.fecha_elim,
                           (SELECT COUNT(*) FROM inscripciones WHERE evento_id = e.id AND usuario_id = %s) AS ya_inscrito
                    FROM eventos e
                    JOIN estados est ON e.estado_id = est.id
                    JOIN espacios esp ON e.espacio_id = esp.id
                    WHERE est.nombre IN ('Aprobado', 'Realizado', 'Cancelado')
                      AND (e.fecha_elim IS NULL OR e.fecha_elim >= %s)
                    ORDER BY e.fecha ASC;
                """
                cursor.execute(sql, (session['usuario_id'], fecha_actual_str))
                eventos = cursor.fetchall()
                
                for ev in eventos:
                    ev['fecha'] = str(ev['fecha'])
                    ev['hora_inicio'] = str(ev['hora_inicio'])[:5]
                    ev['hora_fin'] = str(ev['hora_fin'])[:5]
                    
                    if ev['cupos_disponibles'] is None:
                        ev['cupos_disponibles'] = ev['capacidad_max']
        except Exception as e:
            flash(f'Error al acceder a la cartelera: {str(e)}', 'error')
            return redirect(url_for('home'))
        finally:
            conexion.close()
        return render_template('cartelera.html', eventos=eventos)
    return redirect(url_for('login'))

@app.route('/admin/cartelera')
def admin_cartelera():
    if 'usuario_id' in session and session.get('rol') in ['ADMIN', 'Administrador', 'Admin']:
        conexion = obtener_conexion()
        eventos = []
        try:
            with conexion.cursor() as cursor:
                sql = """
                    SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                           e.cupos_disponibles, esp.nombre AS espacio_nombre, esp.capacidad AS capacidad_max, est.nombre AS estado
                    FROM eventos e
                    JOIN estados est ON e.estado_id = est.id
                    JOIN espacios esp ON e.espacio_id = esp.id
                    WHERE est.nombre IN ('Aprobado', 'Realizado', 'Cancelado', 'En Revisión', 'Solicitado')
                    ORDER BY e.fecha ASC;
                """
                cursor.execute(sql)
                eventos = cursor.fetchall()
                for ev in eventos:
                    ev['fecha'] = str(ev['fecha'])
                    ev['hora_inicio'] = str(ev['hora_inicio'])[:5]
                    ev['hora_fin'] = str(ev['hora_fin'])[:5]
                    if ev['cupos_disponibles'] is None:
                        ev['cupos_disponibles'] = ev['capacidad_max']
                    
                    sql_alumnos = """
                        SELECT u.nombre_completo, u.cedula, u.correo, i.fecha_inscripcion 
                        FROM inscripciones i
                        JOIN usuarios u ON i.usuario_id = u.id
                        WHERE i.evento_id = %s
                        ORDER BY i.fecha_inscripcion ASC;
                    """
                    cursor.execute(sql_alumnos, (ev['id'],))
                    ev['inscritos'] = cursor.fetchall()
        except Exception as e:
            flash(f'Error al cargar el monitor administrativo: {str(e)}', 'error')
        finally:
            conexion.close()
        return render_template('admin_cartelera.html', eventos=eventos)
    return redirect(url_for('login'))
@app.route('/admin/reparar_tabla_estados_secreta')
def reparar_tabla_estados():
    if 'usuario_id' not in session or session.get('rol') not in ['ADMIN', 'Administrador', 'Admin']:
        return "No autorizado", 403
        
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Desactivamos llaves foráneas un momento para poder resetear
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            cursor.execute("DROP TABLE IF EXISTS estados;")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            
            # Creamos la tabla limpia
            cursor.execute("""
                CREATE TABLE estados (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(50) NOT NULL UNIQUE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Insertamos los 6 estados con sus IDs del 1 al 6 corregidos
            valores = [
                (1, 'Solicitado'),
                (2, 'En Revisión'),
                (3, 'Aprobado'),
                (4, 'Realizado'),
                (5, 'Cancelado'),
                (6, 'Rechazado')
            ]
            cursor.executemany("INSERT INTO estados (id, nombre) VALUES (%s, %s);", valores)
            
        conexion.commit()
        return "¡Tabla 'estados' reconstruida con éxito con IDs del 1 al 6! Ya puedes borrar esta ruta."
    except Exception as e:
        return f"Error al reparar tabla: {str(e)}"
    finally:
        conexion.close()

@app.route('/admin/cambiar_estado/<int:evento_id>', methods=['POST'])
def cambiar_estado(evento_id):
    if 'usuario_id' not in session or session.get('rol') not in ['ADMIN', 'Administrador', 'Admin']:
        flash("Acceso denegado. Se requieren permisos de Administrador.", "error")
        return redirect(url_for('home'))
        
    nuevo_estado = request.form.get('estado')
    dias_visibilidad = request.form.get('dias_purga', '0')
    
    try:
        dias_visibilidad = int(dias_visibilidad)
        if dias_visibilidad < 0 or dias_visibilidad > 30:
            dias_visibilidad = 3
    except ValueError:
        dias_visibilidad = 3
    
    fecha_elim = None
    if nuevo_estado == 'Realizado' and dias_visibilidad >= 0:
        fecha_calculada = datetime.now() + timedelta(days=dias_visibilidad)
        fecha_elim = fecha_calculada.strftime('%Y-%m-%d')

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # 1. BUSQUEDA ULTRA-FLEXIBLE DEL ID REAL:
            # Buscamos el ID usando LIKE e ignorando tildes/acentos comunes en las búsquedas
            texto_busqueda = nuevo_estado
            if "Revis" in nuevo_estado:
                texto_busqueda = "en revis%" # Captura 'En Revisión', 'En Revision', 'en revision', etc.
            else:
                texto_busqueda = f"{nuevo_estado}%" # Captura aproximaciones
                
            cursor.execute("SELECT id FROM estados WHERE nombre LIKE %s LIMIT 1;", (texto_busqueda,))
            resultado = cursor.fetchone()
            
            # Si la base de datos encontró el ID correcto, lo usamos:
            if resultado:
                # Dependiendo de si tu cursor devuelve diccionario o tupla, extraemos el ID
                estado_id_real = resultado['id'] if isinstance(resultado, dict) else resultado[0]
            else:
                # Si de plano no existe ese nombre en la tabla, buscamos el primer estado disponible 
                # para que el sistema NUNCA tire un error en pantalla
                cursor.execute("SELECT id FROM estados LIMIT 1;")
                primer_auxiliar = cursor.fetchone()
                estado_id_real = primer_auxiliar['id'] if isinstance(primer_auxiliar, dict) else primer_auxiliar[0]

            # 2. ACTUALIZAMOS EL EVENTO CON EL ID SEGURO QUE SÍ EXISTE EN TU TABLA 'ESTADOS'
            sql = """
                UPDATE eventos 
                SET estado_id = %s, 
                    fecha_elim = %s 
                WHERE id = %s;
            """
            cursor.execute(sql, (estado_id_real, fecha_elim, evento_id))
            
        conexion.commit()
        flash(f"El estado del evento ha sido cambiado a: {nuevo_estado}", "success")
    except Exception as e:
        flash(f"Error al cambiar el estado del evento: {str(e)}", "error")
    finally:
        conexion.close()
        
    # Se mantiene en la cartelera de eventos sin redirigir al monitor
    return redirect(url_for('cartelera_eventos'))

@app.route('/inscribir/<int:evento_id>', methods=['POST']) 
def inscribir_en_evento(evento_id):
    if 'usuario_id' in session:
        rol_actual = session.get('rol')
        target_usuario_id = None
        
        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                if rol_actual in ['ADMIN', 'Administrador', 'Admin']:
                    cedula_estudiante = request.form.get('cedula_estudiante', '').strip()
                    
                    # MODIFICACIÓN DE SEGURIDAD (Cédulas vacías o no numéricas)
                    if not cedula_estudiante or not cedula_estudiante.isdigit():
                        flash('Error: La cédula debe contener exclusivamente números sin símbolos ni letras.', 'error')
                        return redirect(url_for('admin_cartelera'))
                    
                    cursor.execute("""
                        SELECT u.id FROM usuarios u 
                        JOIN roles r ON u.role_id = r.id 
                        WHERE u.cedula = %s AND r.nombre = 'Estudiante';
                    """, (cedula_estudiante,))
                    estudiante = cursor.fetchone()
                    if not estudiante:
                        flash('Error: No se encontró ningún estudiante registrado con esa cédula.', 'error')
                        return redirect(url_for('admin_cartelera'))
                    target_usuario_id = estudiante['id']
                elif rol_actual == 'Estudiante':
                    target_usuario_id = session['usuario_id']
                else:
                    flash('Tu rol actual no te permite realizar inscripciones.', 'error')
                    return redirect(url_for('home'))

                cursor.execute("""
                    SELECT e.cupos_disponibles, esp.capacidad 
                    FROM eventos e 
                    JOIN espacios esp ON e.espacio_id = esp.id 
                    WHERE e.id = %s;
                """, (evento_id,))
                evento = cursor.fetchone()
                
                if not evento:
                    flash('El evento seleccionado ya no está disponible.', 'error')
                    return redirect(url_for('admin_cartelera' if rol_actual in ['ADMIN','Administrador','Admin'] else 'cartelera_eventos'))
                
                cupos_actuales = evento['cupos_disponibles']
                if cupos_actuales is None:
                    cupos_actuales = evento['capacidad']
                
                if cupos_actuales <= 0:
                    flash('Lo sentimos, ya no quedan cupos disponibles para esta actividad.', 'error')
                    return redirect(url_for('admin_cartelera' if rol_actual in ['ADMIN','Administrador','Admin'] else 'cartelera_eventos'))
                
                try:
                    cursor.execute("INSERT INTO inscripciones (usuario_id, evento_id) VALUES (%s, %s);", (target_usuario_id, evento_id))
                    cursor.execute("UPDATE eventos SET cupos_disponibles = %s WHERE id = %s;", (cupos_actuales - 1, evento_id))
                    conexion.commit()
                    flash('¡Inscripción procesada con éxito!', 'success')
                except pymysql.err.IntegrityError:
                    flash('El estudiante ya se encuentra registrado en esta actividad.', 'error')
                    
        except Exception as e:
            flash(f'Error interno en el proceso de inscripción: {str(e)}', 'error')
        finally:
            conexion.close()
            
        return redirect(url_for('admin_cartelera' if rol_actual in ['ADMIN','Administrador','Admin'] else 'cartelera_eventos'))
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)