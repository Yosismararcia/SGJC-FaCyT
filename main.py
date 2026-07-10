from flask import Flask, jsonify
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
