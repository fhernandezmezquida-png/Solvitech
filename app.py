# ============================================================
#  SOLVITECH COLOMBIA — Servidor Backend
#  Flask + PostgreSQL (Neon / Supabase / Railway)
#  Ejecutar local:  python app.py
#  Deploy:          Render.com
# ============================================================

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()   # Carga el archivo .env si existe (solo en local)

app = Flask(__name__, static_folder='.')
CORS(app)

# ── CONFIGURACIÓN DE BASE DE DATOS ──────────────────────────
# En producción (Render) se lee la variable de entorno DATABASE_URL
# En local puedes crear un archivo .env con esa variable
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    """Abre una conexión a PostgreSQL (local o en la nube)."""
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode='require')
    else:
        # Fallback a configuración local para desarrollo
        return psycopg2.connect(
            host="localhost",
            port=5432,
            dbname="solvitech_db",
            user="postgres",
            password="1009"
        )


# ── SERVIR ARCHIVOS HTML ─────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)


# ════════════════════════════════════════════════════════════
#  ENDPOINT: LOGIN
# ════════════════════════════════════════════════════════════
@app.route('/api/login', methods=['POST'])
def login():
    data     = request.get_json()
    usuario  = data.get('usuario', '').strip()
    password = data.get('password', '')
    ip       = request.remote_addr
    agente   = request.headers.get('User-Agent', '')

    if not usuario or not password:
        return jsonify({"ok": False, "mensaje": "Completa todos los campos."}), 400

    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute(
            "SELECT registrar_login(%s, %s, %s::inet, %s) AS exitoso",
            (usuario, password, ip, agente)
        )
        resultado = cur.fetchone()
        exitoso   = resultado['exitoso']

        if exitoso:
            cur.execute(
                "SELECT id, nombre, email, rol FROM usuarios WHERE (email=%s OR username=%s) AND activo=TRUE",
                (usuario, usuario)
            )
            user = cur.fetchone()
            conn.commit()
            cur.close(); conn.close()
            return jsonify({
                "ok":     True,
                "nombre": user['nombre'],
                "rol":    user['rol'],
                "email":  user['email']
            })
        else:
            conn.commit()
            cur.close(); conn.close()
            return jsonify({"ok": False, "mensaje": "Usuario o contraseña incorrectos."}), 401

    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error del servidor: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════
#  ENDPOINT: REGISTRO
# ════════════════════════════════════════════════════════════
@app.route('/api/registro', methods=['POST'])
def registro():
    data     = request.get_json()
    nombre   = data.get('nombre', '').strip()
    email    = data.get('email', '').strip().lower()
    telefono = data.get('telefono', '').strip() or None
    ciudad   = data.get('ciudad', 'Cartagena').strip()
    password = data.get('password', '')

    if not nombre:
        return jsonify({"ok": False, "mensaje": "El nombre es obligatorio."}), 400
    if not email:
        return jsonify({"ok": False, "mensaje": "El correo es obligatorio."}), 400
    if not password or len(password) < 6:
        return jsonify({"ok": False, "mensaje": "La contraseña debe tener al menos 6 caracteres."}), 400

    try:
        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT id FROM usuarios WHERE email = %s", (email,))
        if cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"ok": False, "mensaje": "Este correo ya tiene una cuenta registrada."}), 409

        cur.execute("""
            INSERT INTO usuarios (nombre, email, username, password_hash, rol)
            VALUES (%s, %s, %s, crypt(%s, gen_salt('bf')), 'cliente')
        """, (nombre, email, email, password))

        cur.execute("""
            INSERT INTO clientes (nombre, email, telefono, ciudad)
            VALUES (%s, %s, %s, %s)
        """, (nombre, email, telefono, ciudad))

        conn.commit()
        cur.close(); conn.close()
        return jsonify({"ok": True, "mensaje": f"Cuenta creada exitosamente. Bienvenido {nombre}."})

    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error del servidor: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════
#  ENDPOINT: NUEVA COTIZACIÓN
# ════════════════════════════════════════════════════════════
@app.route('/api/cotizacion', methods=['POST'])
def nueva_cotizacion():
    data = request.get_json()

    nombre      = data.get('nombre', '').strip()
    email       = data.get('email', '').strip() or None
    telefono    = data.get('telefono', '').strip() or None
    ciudad      = data.get('ciudad', 'Cartagena').strip()
    empresa     = data.get('empresa', '').strip() or None
    servicio    = data.get('servicio', 'energia_solar')
    descripcion = data.get('descripcion', '').strip() or None
    consumo     = data.get('consumo_kwh') or None
    precio_kwh  = data.get('precio_kwh') or None
    canal       = data.get('canal', 'web')

    if not nombre:
        return jsonify({"ok": False, "mensaje": "El nombre es obligatorio."}), 400

    servicios_validos = ['energia_solar', 'ingenieria_electrica', 'capacitacion', 'otro']
    if servicio not in servicios_validos:
        servicio = 'otro'

    try:
        conn = get_db()
        cur  = conn.cursor()

        cur.execute(
            "SELECT nueva_cotizacion(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (nombre, email, telefono, ciudad, empresa,
             servicio, descripcion, consumo, precio_kwh, canal)
        )
        cotizacion_id = cur.fetchone()[0]
        conn.commit()

        cur.execute("SELECT numero FROM cotizaciones WHERE id = %s", (cotizacion_id,))
        numero = cur.fetchone()[0]
        cur.close(); conn.close()

        return jsonify({
            "ok":      True,
            "mensaje": f"¡Cotización {numero} creada con éxito! Te contactaremos pronto.",
            "numero":  numero,
            "id":      cotizacion_id
        })

    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error del servidor: {str(e)}"}), 500


# ════════════════════════════════════════════════════════════
#  ENDPOINTS ADMIN
# ════════════════════════════════════════════════════════════
@app.route('/api/admin/cotizaciones', methods=['GET'])
def ver_cotizaciones():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT numero, fecha_solicitud, cliente_nombre, cliente_email,
                   cliente_telefono, ciudad, servicio, estado,
                   monto_ofertado, canal_origen, vendedor,
                   ahorro_mensual_est, ahorro_anual_est
            FROM v_resumen_cotizaciones
            ORDER BY fecha_solicitud DESC LIMIT 100
        """)
        cotizaciones = cur.fetchall()
        cur.close(); conn.close()
        resultado = []
        for c in cotizaciones:
            row = dict(c)
            if row.get('fecha_solicitud'):
                row['fecha_solicitud'] = str(row['fecha_solicitud'])
            resultado.append(row)
        return jsonify({"ok": True, "data": resultado})
    except Exception as e:
        return jsonify({"ok": False, "mensaje": str(e)}), 500


@app.route('/api/admin/logins', methods=['GET'])
def ver_logins():
    try:
        conn = get_db()
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT nombre, email, rol,
                   total_intentos, logins_exitosos, logins_fallidos,
                   ultimo_login_exitoso
            FROM v_actividad_logins
            ORDER BY ultimo_login_exitoso DESC NULLS LAST
        """)
        logins = cur.fetchall()
        cur.close(); conn.close()
        resultado = []
        for l in logins:
            row = dict(l)
            if row.get('ultimo_login_exitoso'):
                row['ultimo_login_exitoso'] = str(row['ultimo_login_exitoso'])
            resultado.append(row)
        return jsonify({"ok": True, "data": resultado})
    except Exception as e:
        return jsonify({"ok": False, "mensaje": str(e)}), 500


# ── INICIAR SERVIDOR ─────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  SOLVITECH COLOMBIA — Servidor iniciado")
    print(f"  http://localhost:{port}")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=port)
