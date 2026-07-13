#--------------------------- NUEVA MODIFICACION INTEGRADA 2026
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pymysql
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# CONFIGURACIÓN PARA LA DIVULGACIÓN POR EMAIL
# ==========================================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_EMISOR = "arciayosi@gmail.com"  
EMAIL_PASSWORD = "DrakoM0810."       # Asegúrate de que esta sea tu Contraseña de Aplicación de Google

#--- CARGA DE VARIABLES DE ENTORNO DESDE .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', '27894120')

# EXPRESIÓN REGULAR: Previene inyecciones y símbolos raros
CARACTERES_PERMITIDOS = re.compile(r"^[a-zA-Z0-9@._-]+$")

#---- RUTA DE CONTROL DE SESIÓN Y TIEMPO DE INACTIVIDAD ----
@app.before_request
def controlar_sesion_y_tiempo():
    session.permanent = True # 
    app.permanent_session_lifetime = timedelta(minutes=5)
    session.modified = True

#----- FUNCIONES AUXILIARES -------------------
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
            """# 1. DESACTIVACIÓN DE RESTRICCIONES PARA LIMPIEZA TOTAL
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            
            # 2. DROP TABLES: Reseteo controlado para reestructurar IDs
            tablas = ["inscripciones", "eventos", "usuarios", "espacios", "estados", "roles", "personal_autorizado"]
            for tabla in tablas:
                cursor.execute(f"DROP TABLE IF EXISTS {tabla};")
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
            print("¡Base de datos limpia desde cero!")"""

            # 3. CREACIÓN DE TABLAS MAESTRAS (Sin Auto-Incremento en estados)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personal_autorizado (
                    cedula VARCHAR(20) PRIMARY KEY, 
                    correo_institucional VARCHAR(100) UNIQUE NOT NULL, 
                    tipo_personal VARCHAR(20) NOT NULL
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roles (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    nombre VARCHAR(20) UNIQUE NOT NULL
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    nombre_completo VARCHAR(100) NOT NULL, 
                    correo VARCHAR(100) UNIQUE NOT NULL, 
                    password_hash VARCHAR(255) NOT NULL, 
                    cedula VARCHAR(20) UNIQUE NOT NULL, 
                    role_id INT NOT NULL, 
                    FOREIGN KEY (role_id) REFERENCES roles(id)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS espacios (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    nombre VARCHAR(50) UNIQUE NOT NULL, 
                    tipo VARCHAR(30) NOT NULL, 
                    capacidad INT NOT NULL, 
                    ubicacion VARCHAR(100) NOT NULL
                );
            """)
            
            # --- CORRECCIÓN CRÍTICA: ID ESTÁTICO MANUAL ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS estados (
                    id INT PRIMARY KEY, 
                    nombre VARCHAR(20) UNIQUE NOT NULL
                );
            """)
           
            # 4. INYECCIÓN REGLAMENTARIA DE ESTADOS (IDs del 1 al 6)
            valores_estados = [
                (1, 'Solicitado'),
                (2, 'En Revisión'),
                (3, 'Aprobado'),
                (4, 'Realizado'),
                (5, 'Cancelado'),
                (6, 'Rechazado')
            ]
            cursor.executemany("INSERT INTO estados (id, nombre) VALUES (%s, %s);", valores_estados)
            print("Estados estáticos (1-6) inyectados con éxito.")

            # 5. CREACIÓN DE TABLAS TRANSACCIONALES
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eventos (
                    id INT AUTO_INCREMENT PRIMARY KEY, 
                    titulo VARCHAR(150) NOT NULL, 
                    tipo_actividad VARCHAR(50) NOT NULL, 
                    fecha DATE NOT NULL, 
                    hora_inicio TIME NOT NULL, 
                    hora_fin TIME NOT NULL, 
                    estado_id INT DEFAULT 1, 
                    espacio_id INT NULL, 
                    usuario_id INT NOT NULL,
                    cupos_disponibles INT NULL,
                    fecha_elim VARCHAR(10) NULL,
                    FOREIGN KEY (estado_id) REFERENCES estados(id), 
                    FOREIGN KEY (espacio_id) REFERENCES espacios(id), 
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
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
            
            # 6. INICIALIZACION DE DATOS DE CONTROL
            cursor.executemany("INSERT IGNORE INTO roles (nombre) VALUES (%s);", [('Admin',), ('Profesor',), ('Estudiante',)])

            espacios_facyt = [
                ('Auditorio FaCyT', 'Auditorio', 150, 'Planta Baja, Edificio de Aulas'),
                ('Laboratorio de Computación 1', 'Laboratorio', 30, 'Primer Piso, Ala Norte'),
                ('Aula Magna 202', 'Aula de Clases', 45, 'Segundo Piso, Edificio de Aulas')
            ]
            cursor.executemany("INSERT IGNORE INTO espacios (nombre, tipo, capacidad, ubicacion) VALUES (%s, %s, %s, %s);", espacios_facyt)

            usuarios_autorizados = [
                ('27894120', 'arciayosi@gmail.com', 'Admin'),
                ('22222222', 'yosi12141@gmail.com', 'Profesor'),
                ('33333333', 'yarcia@uc.edu.ve', 'Estudiante')
            ]
            cursor.executemany("INSERT IGNORE INTO personal_autorizado (cedula, correo_institucional, tipo_personal) VALUES (%s, %s, %s);", usuarios_autorizados)

            # 7. CREACIÓN DEL ADMINISTRADOR POR DEFECTO
            cursor.execute("SELECT id FROM roles WHERE nombre = 'Admin';")
            role_id = cursor.fetchone()['id']
            pass_hash = generate_password_hash('admin123')
            cursor.execute("""
                INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) 
                VALUES (%s, %s, %s, %s, %s);
            """, ('Administrador de Pruebas', 'arciayosi@gmail.com', pass_hash, '27894120', role_id))
            
            conexion.commit()
            print("¡Inicialización de base de datos completada exitosamente!")
    except Exception as e:
        print(f"Error al inicializar base de datos: {str(e)}")
    finally:
        conexion.close()

def enviar_correo_divulgacion(destinatarios, titulo_evento, fecha, horario, aula):
    """
    Se conecta al servidor SMTP institucional para notificar masivamente a los 
    estudiantes sobre la aprobación y apertura de cupos de una nueva actividad académica.
    """
    # 1. Validación de control: Si la lista viene vacía, no procesamos el envío
    if not destinatarios:
        print("Divulgación cancelada: No se encontraron alumnos registrados en el sistema.")
        return False

    try:
        # 2. Configuración del contenedor del mensaje (MIME)
        msg = MIMEMultipart()
        msg['From'] = EMAIL_EMISOR
        # El campo 'To' visual mostrará el remitente institucional por estética, los correos van ocultos
        msg['To'] = EMAIL_EMISOR 
        msg['Subject'] = f"📢 NUEVA ACTIVIDAD ACADÉMICA: {titulo_evento} (FaCyT-UC)"

        # 3. Diseño del Cuerpo del Mensaje en Formato HTML Limpio
        cuerpo_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px; background-color: #fdfdfd;">
                    <h2 style="color: #003366; text-align: center; border-bottom: 2px solid #003366; padding-bottom: 10px;">
                        Cartelera Digital FaCyT
                    </h2>
                    <p>Estimado(a) estudiante de la comunidad FaCyT-UC,</p>
                    <p>Te informamos que las autoridades de la facultad han evaluado y aprobado una nueva actividad académica de alto interés:</p>
                    
                    <div style="background-color: #f2f5f9; padding: 15px; border-left: 5px solid #003366; margin: 20px 0; border-radius: 4px;">
                        <strong style="font-size: 1.1em; color: #111;">🎯 {titulo_evento}</strong><br><br>
                        📅 <strong>Fecha:</strong> {fecha}<br>
                        ⏰ <strong>Horario:</strong> {horario}<br>
                        📍 <strong>Lugar asignado:</strong> {aula}
                    </div>

                    <p style="text-align: center; margin: 25px 0;">
                        <a href="http://localhost:5000/login" 
                           style="background-color: #003366; color: white; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 5px; display: inline-block;">
                           Ingresar y Reservar Cupo
                        </a>
                    </p>
                    
                    <p style="font-size: 0.9em; color: #777;">
                        ⚠️ <strong>Nota:</strong> Los cupos son limitados según la capacidad física del aula asignada. Asegura tu asistencia ingresando lo antes posible al sistema.
                    </p>
                    <hr style="border: 0; border-top: 1px solid #eee; margin-top: 30px;">
                    <p style="font-size: 0.8em; color: #999; text-align: center;">
                        Sistema Automatizado de Gestión de Eventos - Dirección de Asuntos Estudiantiles FaCyT
                    </p>
                </div>
            </body>
        </html>
        """
        msg.attach(MIMEText(cuerpo_html, 'html'))

        # 4. Conexión e inicio de sesión seguro con el servidor SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Cifra la comunicación (Transport Layer Security)
        server.login(EMAIL_EMISOR, EMAIL_PASSWORD)

        # 5. Envío con el método 'Bcc' (Copia Oculta) 
        # Esto envía el correo a todos los alumnos protegiendo la privacidad de sus direcciones electrónicas.
        server.sendmail(EMAIL_EMISOR, destinatarios, msg.as_string())
        server.quit()
        
        print(f"Divulgación exitosa: Correo masivo enviado a {len(destinatarios)} estudiantes.")
        return True

    except Exception as e:
        print(f"Error crítico en el protocolo SMTP: {str(e)}")
        # Lanzamos la excepción hacia arriba para que la ruta 'procesar_solicitud' entienda que hubo un percance
        raise e
    
#---------------------- RUTAS PRINCIPALES DE LA APLICACIÓN ---------------------------
@app.route('/')
def home():
    inicializar_base_de_datos()
    if 'usuario_id' in session:
        conexion = obtener_conexion()
        estadisticas = {}
        try:
            with conexion.cursor() as cursor:
                # 1. Conteo total de eventos en el sistema
                cursor.execute("SELECT COUNT(*) AS total FROM eventos;")
                estadisticas['total_eventos'] = cursor.fetchone()['total']
                
                # 2. Agrupación por estados reales (IDs del 1 al 6)
                cursor.execute("""
                    SELECT est.nombre, COUNT(e.id) AS conteo 
                    FROM estados est 
                    LEFT JOIN eventos e ON e.estado_id = est.id 
                    GROUP BY est.id, est.nombre;
                """)
                por_estado = cursor.fetchall()
                
                # CORRECCIÓN DE LÓGICA: Pendientes son tanto las 'Solicitado' (ID 1) como 'En Revisión' (ID 2)
                estadisticas['pendientes'] = sum(x['conteo'] for x in por_estado if x['nombre'] in ['Solicitado', 'En Revisión'])
                estadisticas['aprobados'] = next((x['conteo'] for x in por_estado if x['nombre'] == 'Aprobado'), 0)
                estadisticas['cancelados'] = next((x['conteo'] for x in por_estado if x['nombre'] == 'Cancelado'), 0)
                
                # 3. Métrica de uso del Espacio Físico Top (Solo toma en cuenta eventos Aprobados)
                cursor.execute("""
                    SELECT esp.nombre, COUNT(e.id) AS usos 
                    FROM espacios esp 
                    JOIN eventos e ON e.espacio_id = esp.id 
                    WHERE e.estado_id = 3
                    GROUP BY esp.id, esp.nombre 
                    ORDER BY usos DESC 
                    LIMIT 1;
                """)
                mas_utilizado = cursor.fetchone()
                estadisticas['espacio_top'] = mas_utilizado['nombre'] if mas_utilizado else "Ninguno aún"
                estadisticas['espacio_top_usos'] = mas_utilizado['usos'] if mas_utilizado else 0

                # 4. Total de alumnos registrados en actividades
                cursor.execute("SELECT COUNT(*) AS total FROM inscripciones;")
                estadisticas['total_inscritos'] = cursor.fetchone()['total']
                
        except Exception as e:
            print(f"Error al calcular estadísticas del Dashboard: {str(e)}")
            # Valores seguros de respaldo por si la base de datos está temporalmente caída
            estadisticas = {
                'total_eventos': 0, 'pendientes': 0, 'aprobados': 0, 
                'cancelados': 0, 'espacio_top': 'Error de carga', 
                'espacio_top_usos': 0, 'total_inscritos': 0
            }
        finally:
            conexion.close()
            
        return render_template('dashboard.html', stats=estadisticas)
    
    # Si no hay sesión activa, obligamos a ir al Login institucional
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo'].strip()
        password = request.form['password']

        # FILTRO DE SEGURIDAD BACKEND: Evita SQLi o caracteres maliciosos
        if not CARACTERES_PERMITIDOS.match(correo):
            flash("Error: El usuario contiene caracteres especiales no permitidos.", "error")
            return redirect(url_for('login'))

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                # Modificado para traer el nombre del rol usando la relación correcta con la tabla 'roles'
                sql = """
                    SELECT u.*, r.nombre AS rol_nombre 
                    FROM usuarios u 
                    JOIN roles r ON u.role_id = r.id 
                    WHERE u.correo = %s;
                """
                cursor.execute(sql, (correo,))
                usuario = cursor.fetchone()
                
                # Verificación segura del hash de la contraseña
                if usuario and check_password_hash(usuario['password_hash'], password):
                    session['usuario_id'] = usuario['id']
                    session['nombre'] = usuario['nombre_completo']
                    session['rol'] = usuario['rol_nombre']  # 'Admin', 'Profesor' o 'Estudiante'
                    session['cedula'] = usuario['cedula']
                    flash(f"¡Bienvenido de vuelta, {usuario['nombre_completo']}!", "success")
                    return redirect(url_for('home'))
                else:
                    flash('Correo o contraseña incorrectos.', 'error')
        except Exception as e:
            print(f"Error en el proceso de Login: {str(e)}")
            flash("Ocurrió un error interno en el servidor al iniciar sesión.", "error")
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

        # Validación técnica de entradas en el formulario de registro
        if not CARACTERES_PERMITIDOS.match(correo) or not cedula.isdigit():
            flash('Error: Los campos contienen datos o símbolos inválidos.', 'error')
            return redirect(url_for('register'))

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                # 1. Verificar si la persona pertenece al personal autorizado por la FaCyT
                cursor.execute("SELECT * FROM personal_autorizado WHERE cedula = %s AND correo_institucional = %s;", (cedula, correo))
                personal = cursor.fetchone()

                if not personal:
                    flash('Error: Tus datos no figuran en el personal autorizado de la FaCyT-UC.', 'error')
                    return redirect(url_for('register'))

                # 2. Verificar si ya se registró previamente en el sistema
                cursor.execute("SELECT id FROM usuarios WHERE cedula = %s OR correo = %s;", (cedula, correo))
                if cursor.fetchone():
                    flash('Esta cuenta ya se encuentra registrada. Intenta iniciar sesión.', 'error')
                    return redirect(url_for('register'))

                # 3. Buscar el ID del rol que le corresponde (Admin, Profesor, Estudiante) según el personal autorizado
                cursor.execute("SELECT id FROM roles WHERE nombre = %s;", (personal['tipo_personal'],))
                role_res = cursor.fetchone()
                if not role_res:
                    flash('Error interno: El rol asignado en el personal autorizado no es válido.', 'error')
                    return redirect(url_for('register'))
                role_id = role_res['id']

                # 4. Encriptar contraseña y guardar al nuevo usuario
                password_hash = generate_password_hash(password)
                sql_insert = """
                    INSERT INTO usuarios (nombre_completo, correo, password_hash, cedula, role_id) 
                    VALUES (%s, %s, %s, %s, %s);
                """
                cursor.execute(sql_insert, (nombre, correo, password_hash, cedula, role_id))
                conexion.commit()

                flash('¡Registro exitoso! Ya puedes iniciar sesión en la plataforma.', 'success')
                return redirect(url_for('login'))
        except Exception as e:
            print(f"Error en el proceso de Registro: {str(e)}")
            flash("Error al procesar el registro en la base de datos.", "error")
        finally:
            conexion.close()
            
    return render_template('register.html')

@app.route('/recuperar-password', methods=['GET', 'POST'])
def recuperar_password():
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip()
        
        if not CARACTERES_PERMITIDOS.match(correo):
            flash("Error: El formato contiene símbolos inválidos.", "error")
            return redirect(url_for('recuperar_password'))
        
        # Flujo institucional simulado para la recuperación
        flash(f"Si el correo {correo} existe en el sistema FaCyT, recibirás un enlace de restauración de credenciales.", "success")
        return redirect(url_for('login'))
        
    return render_template('recuperar_password.html')

@app.route('/proponer', methods=['GET', 'POST'])
def proponer_evento():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        titulo = request.form['titulo'].strip()
        tipo_actividad = request.form['tipo_actividad']
        fecha = request.form['fecha']
        hora_inicio = request.form['hora_inicio']
        hora_fin = request.form['hora_fin']
        usuario_id = session['usuario_id']

        # Validación lógica de tiempo
        if hora_inicio >= hora_fin:
            flash('Error: La hora de inicio debe ser anterior a la de culminación.', 'error')
            return render_template('proponer.html')

        conexion = obtener_conexion()
        try:
            with conexion.cursor() as cursor:
                # GUSTAZO TÉCNICO: Como el estado inicial 'Solicitado' tiene asignado el ID fijos 1,
                # lo insertamos directamente de forma estática evitando consultas lentas.
                estado_inicial_id = 1 

                sql_evento = """
                    INSERT INTO eventos (titulo, tipo_actividad, fecha, hora_inicio, hora_fin, estado_id, usuario_id, cupos_disponibles)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NULL);
                """
                cursor.execute(sql_evento, (titulo, tipo_actividad, fecha, hora_inicio, hora_fin, estado_inicial_id, usuario_id))
                conexion.commit()
                
            flash('¡Propuesta enviada con éxito! Ha quedado en estado "Solicitado" para revisión administrativa.', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Error al proponer evento: {str(e)}")
            flash(f'Error en el sistema al guardar la actividad en la base de datos.', 'error')
        finally:
            conexion.close()

    return render_template('proponer.html')

@app.route('/historial')
def ver_historial():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']
    conexion = obtener_conexion()
    eventos = []
    try:
        with conexion.cursor() as cursor:
            # Seleccionamos y formateamos los campos utilizando la relación id-estado correcta
            sql = """
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                       est.nombre AS estado_nombre, esp.nombre AS espacio_nombre, e.cupos_disponibles
                FROM eventos e
                JOIN estados est ON e.estado_id = est.id
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.usuario_id = %s
                ORDER BY e.fecha DESC, e.hora_inicio DESC;
            """
            cursor.execute(sql, (usuario_id,))
            eventos = cursor.fetchall()
            
            # Formateo de tipos nativos (Date/Time) a String para que Jinja2 no tenga problemas al renderizar
            for ev in eventos:
                ev['fecha'] = str(ev['fecha'])
                ev['hora_inicio'] = str(ev['hora_inicio'])[:5]
                ev['hora_fin'] = str(ev['hora_fin'])[:5]
                if ev['cupos_disponibles'] is None:
                    ev['cupos_disponibles'] = "No asignado"
    except Exception as e:
        print(f"Error al cargar historial: {str(e)}")
        flash('Error al cargar el historial de eventos desde el servidor.', 'error')
    finally:
        conexion.close()
        
    return render_template('historial.html', eventos=eventos)

@app.route('/evento/editar/<int:evento_id>', methods=['GET', 'POST'])
def editar_evento(evento_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # Buscamos el evento y verificamos si sigue en espera (Estado 'Solicitado' = ID 1)
            cursor.execute("""
                SELECT e.*, est.nombre AS estado_nombre 
                FROM eventos e 
                JOIN estados est ON e.estado_id = est.id 
                WHERE e.id = %s AND e.usuario_id = %s;
            """, (evento_id, session['usuario_id']))
            evento = cursor.fetchone()

            # BLINDAJE: Solo se edita si está 'Solicitado' (ID 1) o 'En Revisión' (ID 2). 
            # Si ya se Aprobó o Rechazó, el profesor pierde el derecho a modificarlo sin permiso.
            if not evento or evento['estado_id'] not in [1, 2]:
                flash('No puedes modificar una actividad que ya fue procesada o aprobada administrativamente.', 'error')
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
                flash('Propuesta actualizada correctamente en la lista de espera.', 'success')
                return redirect(url_for('ver_historial'))

            # Convertir formatos de tiempo para desplegar en los inputs tipo 'date' y 'time' del HTML
            evento['fecha'] = str(evento['fecha'])
            evento['hora_inicio'] = str(evento['hora_inicio'])[:5]
            evento['hora_fin'] = str(evento['hora_fin'])[:5]
            return render_template('editar_evento.html', evento=evento)
    finally:
        conexion.close()

@app.route('/evento/eliminar/<int:evento_id>')
def eliminar_evento(evento_id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT estado_id FROM eventos WHERE id = %s AND usuario_id = %s;", (evento_id, session['usuario_id']))
            evento = cursor.fetchone()

            # Control estricto: Solo permitimos borrar si el estado es 'Solicitado' (ID 1)
            if evento and evento['estado_id'] == 1:
                cursor.execute("DELETE FROM eventos WHERE id = %s;", (evento_id,))
                conexion.commit()
                flash('La propuesta ha sido retirada y eliminada permanentemente.', 'success')
            else:
                flash('No puedes eliminar este evento porque ya se encuentra bajo evaluación o aprobado.', 'error')
    except Exception as e:
        print(f"Error al eliminar: {str(e)}")
        flash('Error al procesar la eliminación del registro.', 'error')
    finally:
        conexion.close()
        
    return redirect(url_for('ver_historial'))

@app.route('/admin/pendientes')
def admin_pendientes():
    # Validación estricta de Roles basada en nuestra tabla limpia
    if 'usuario_id' not in session or session.get('rol') not in ['Admin', 'ADMIN', 'Administrador']:
        flash("Acceso denegado. Se requieren privilegios de Administrador.", "error")
        return redirect(url_for('home'))
        
    conexion = obtener_conexion()
    solicitudes = []
    espacios = []
    try:
        with conexion.cursor() as cursor:
            # Selecciona únicamente los eventos que están en espera de revisión (ID 1: Solicitado o ID 2: En Revisión)
            sql_solicitudes = """
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                       u.nombre_completo AS solicitante, u.cedula, est.nombre AS estado
                FROM eventos e
                JOIN usuarios u ON e.usuario_id = u.id
                JOIN estados est ON e.estado_id = est.id
                WHERE e.estado_id IN (1, 2)
                ORDER BY e.fecha ASC;
            """
            cursor.execute(sql_solicitudes)
            solicitudes = cursor.fetchall()
            
            # Formateo de tiempos para la interfaz gráfica del Administrador
            for s in solicitudes:
                s['fecha'] = str(s['fecha'])
                s['hora_inicio'] = str(s['hora_inicio'])[:5]
                s['hora_fin'] = str(s['hora_fin'])[:5]

            # Cargamos los espacios físicos disponibles (con nombres actualizados de la tabla 'espacios')
            cursor.execute("SELECT id, nombre, capacidad FROM espacios ORDER BY nombre ASC;")
            espacios = cursor.fetchall()
    except Exception as e:
        print(f"Error al cargar panel administrativo: {str(e)}")
        flash('Error al cargar la lista de solicitudes desde el servidor.', 'error')
    finally:
        conexion.close()
        
    return render_template('admin_pendientes.html', solicitudes=solicitudes, espacios=espacios)
    
@app.route('/admin/procesar/<int:evento_id>', methods=['POST'])
def procesar_solicitud(evento_id):
    if 'usuario_id' not in session or session.get('rol') not in ['Admin', 'ADMIN', 'Administrador']:
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    accion = request.form.get('accion') 
    espacio_id = request.form.get('espacio_id')

    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            
            if accion == 'rechazar':
                # ACCIÓN 1: Rechazar la propuesta (ID estático 6)
                sql = "UPDATE eventos SET estado_id = 6 WHERE id = %s;"
                cursor.execute(sql, (evento_id,))
                conexion.commit()
                flash("La solicitud ha sido rechazada con éxito.", "success")
                
            else:
                # ACCIÓN 2: Aprobar la propuesta (Requiere un espacio físico asignado)
                if not espacio_id or espacio_id == "":
                    flash("Error: Debe asignar un espacio físico para poder aprobar el evento.", "error")
                    return redirect(url_for('admin_pendientes'))
                
                # Modificamos el evento a estado Aprobado (ID 3) y le asignamos el aula
                sql = "UPDATE eventos SET estado_id = 3, espacio_id = %s WHERE id = %s;"
                cursor.execute(sql, (espacio_id, evento_id))
                conexion.commit()
                
                # ====================================================================
                # AUTOMATIZACIÓN: MOTOR DE DIVULGACIÓN E INSCRIPCIÓN INSTITUCIONAL
                # ====================================================================
                try:
                    # 1. Buscamos los datos del evento aprobado y su espacio físico real
                    sql_info = """
                        SELECT e.titulo, e.fecha, e.hora_inicio, e.hora_fin, esp.nombre, esp.capacidad 
                        FROM eventos e
                        JOIN espacios esp ON e.espacio_id = esp.id
                        WHERE e.id = %s;
                    """
                    cursor.execute(sql_info, (evento_id,))
                    info_evento = cursor.fetchone()
                    
                    if info_evento:
                        # Extraemos los datos según el formato del diccionario
                        titulo = info_evento['titulo']
                        fecha = str(info_evento['fecha'])
                        horario = f"{str(info_evento['hora_inicio'])[:5]} - {str(info_evento['hora_fin'])[:5]}"
                        aula = info_evento['nombre']
                        capacidad_max = info_evento['capacidad']
                        
                        # 2. Sincronizamos los cupos iniciales del evento basándonos en el aforo del espacio físico asignado
                        cursor.execute("UPDATE eventos SET cupos_disponibles = %s WHERE id = %s;", (capacidad_max, evento_id))
                        conexion.commit()
                        
                        # 3. Extraemos los correos electrónicos de todos los Alumnos registrados para la divulgación masiva
                        cursor.execute("""
                            SELECT u.correo FROM usuarios u 
                            JOIN roles r ON u.role_id = r.id 
                            WHERE r.nombre = 'Estudiante';
                        """)
                        lista_usuarios = cursor.fetchall()
                        
                        correos_destinatarios = [u['correo'] for u in lista_usuarios if u.get('correo')]
                        
                        # Si aún no hay alumnos en el sistema, enviamos una prueba al emisor
                        if not correos_destinatarios:
                            correos_destinatarios = [EMAIL_EMISOR]
                            
                        # 4. Despachamos el correo electrónico institucional
                        enviar_correo_divulgacion(correos_destinatarios, titulo, fecha, horario, aula)
                        flash("La solicitud fue aprobada, los cupos inicializados y divulgada por email.", "success")
                        
                except Exception as ex_mail:
                    print(f"Error no crítico en el envío de correos: {str(ex_mail)}")
                    flash("El evento fue aprobado con éxito, pero la difusión por correo experimentó un retraso físico.", "warning")
                
    except Exception as e:
        print(f"Error al procesar la solicitud: {str(e)}")
        flash(f"Error interno al procesar la solicitud administrativa.", "error")
    finally:
        conexion.close()
        
    return redirect(url_for('admin_pendientes'))

# NOTA DE DEPURACIÓN: Hemos ELIMINADO por completo la ruta '/admin/reparar_tabla_estados_secreta'.
# Como configuramos correctamente los IDs estáticos fijos en la inicialización (1 al 6),
# mantener una ruta secreta que borre y altere los IDs dinámicamente es una vulnerabilidad técnica.

@app.route('/cartelera')
def cartelera():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conexion = obtener_conexion()
    eventos = []
    try:
        with conexion.cursor() as cursor:
            # Trae solo los eventos 'Aprobados' (ID 3) que ocurrirán hoy o en el futuro
            sql = """
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, e.hora_inicio, e.hora_fin, 
                       esp.nombre AS espacio_nombre, e.cupos_disponibles,
                       (SELECT COUNT(*) FROM inscripciones WHERE evento_id = e.id AND usuario_id = %s) AS ya_inscrito
                FROM eventos e
                JOIN espacios esp ON e.espacio_id = esp.id
                WHERE e.estado_id = 3 AND e.fecha >= CURDATE()
                ORDER BY e.fecha ASC, e.hora_inicio ASC;
            """
            cursor.execute(sql, (session['usuario_id'],))
            eventos = cursor.fetchall()
            
            # Formateo visual estricto para Jinja2
            for ev in eventos:
                ev['fecha'] = str(ev['fecha'])
                ev['hora_inicio'] = str(ev['hora_inicio'])[:5]
                ev['hora_fin'] = str(ev['hora_fin'])[:5]
    except Exception as e:
        print(f"Error al cargar cartelera: {str(e)}")
        flash('Error al sincronizar la cartelera de actividades.', 'error')
    finally:
        conexion.close()
        
    return render_template('cartelera.html', eventos=eventos)

@app.route('/inscribir/<int:evento_id>', methods=['POST'])
def inscribir_evento(evento_id):
    if 'usuario_id' not in session or session.get('rol') != 'Estudiante':
        flash("Acceso restringido. Solo los estudiantes pueden inscribirse a las actividades.", "error")
        return redirect(url_for('cartelera'))
        
    usuario_id = session['usuario_id']
    conexion = obtener_conexion()
    try:
        with conexion.cursor() as cursor:
            # 1. Bloqueo de concurrencia: Validar estado actual y cupos disponibles en un solo paso
            cursor.execute("SELECT cupos_disponibles, estado_id, titulo FROM eventos WHERE id = %s FOR UPDATE;", (evento_id,))
            evento = cursor.fetchone()
            
            if not evento or evento['estado_id'] != 3:
                flash("El evento seleccionado no está disponible o ha sido cancelado.", "error")
                return redirect(url_for('cartelera'))
                
            if evento['cupos_disponibles'] is not None and evento['cupos_disponibles'] <= 0:
                flash("Lo sentimos, los cupos para esta actividad académica se han agotado.", "error")
                return redirect(url_for('cartelera'))
                
            # 2. Verificar si ya se encuentra inscrito (Doble capa de seguridad junto al UNIQUE KEY de la BD)
            cursor.execute("SELECT id FROM inscripciones WHERE usuario_id = %s AND evento_id = %s;", (usuario_id, evento_id))
            if cursor.fetchone():
                flash("Ya te encuentras registrado en este evento.", "warning")
                return redirect(url_for('cartelera'))
                
            # 3. Insertar la inscripción y restar un cupo en la misma transacción (Atómico)
            cursor.execute("INSERT INTO inscripciones (usuario_id, evento_id) VALUES (%s, %s);", (usuario_id, evento_id))
            if evento['cupos_disponibles'] is not None:
                cursor.execute("UPDATE eventos SET cupos_disponibles = cupos_disponibles - 1 WHERE id = %s;", (evento_id,))
                
            conexion.commit()
            flash(f"¡Inscripción exitosa al evento: {evento['titulo']}!", "success")
            
    except Exception as e:
        conexion.rollback()
        print(f"Error crítico en el proceso de inscripción: {str(e)}")
        flash("Error interno al procesar tu inscripción. Inténtalo de nuevo.", "error")
    finally:
        conexion.close()
        
    return redirect(url_for('cartelera'))

@app.route('/admin/cartelera')
def admin_cartelera():
    if 'usuario_id' not in session or session.get('rol') not in ['Admin', 'ADMIN', 'Administrador']:
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))
        
    conexion = obtener_conexion()
    eventos_historicos = []
    try:
        with conexion.cursor() as cursor:
            # Muestra el listado global de control de actividades aprobadas, realizadas o rechazadas
            sql = """
                SELECT e.id, e.titulo, e.tipo_actividad, e.fecha, est.nombre AS estado, esp.nombre AS espacio_nombre,
                       (SELECT COUNT(*) FROM inscripciones WHERE evento_id = e.id) AS total_participantes
                FROM eventos e
                JOIN estados est ON e.estado_id = est.id
                LEFT JOIN espacios esp ON e.espacio_id = esp.id
                ORDER BY e.fecha DESC;
            """
            cursor.execute(sql)
            eventos_historicos = cursor.fetchall()
            
            for ev in eventos_historicos:
                ev['fecha'] = str(ev['fecha'])
    except Exception as e:
        print(f"Error en monitor administrativo: {str(e)}")
        flash('Error al recopilar el historial administrativo.', 'error')
    finally:
        conexion.close()
        
    return render_template('admin_cartelera.html', eventos=eventos_historicos)

@app.route('/logout')
def logout():
    session.clear()
    flash("Sesión cerrada correctamente. ¡Hasta luego!", "success")
    return redirect(url_for('login'))

if __name__ == '__main__':
    # El puerto se mapea de forma dinámica para evitar colisiones en Render u otros servidores web
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto, debug=True)





