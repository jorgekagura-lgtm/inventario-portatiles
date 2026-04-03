from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)

# CONFIGURACIÓN DE CONEXIÓN
def conectar_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# 1. CONFIGURACIÓN INICIAL DE LAS TABLAS (CON REPARACIÓN DE ORDEN)
def init_db():
    conn = conectar_db()
    cur = conn.cursor()
    
    # Crear tabla base si no existe
    cur.execute('''CREATE TABLE IF NOT EXISTS portatiles (
                    id TEXT PRIMARY KEY, 
                    descripcion_tecnica TEXT, 
                    num_serie TEXT,
                    ubicacion TEXT, 
                    estado TEXT DEFAULT 'Disponible')''')
    
    # REPARACIÓN: Añadir columna de fecha para el orden si no existe
    try:
        cur.execute("ALTER TABLE portatiles ADD COLUMN IF NOT EXISTS fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    except Exception:
        pass # Si ya existe o hay error, continuamos

    cur.execute('''CREATE TABLE IF NOT EXISTS prestamos (
                    id_prestamo SERIAL PRIMARY KEY,
                    id_portatil TEXT, 
                    persona TEXT, 
                    correo TEXT, 
                    fecha_prestamo TEXT, 
                    fecha_devolucion TEXT)''')
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# 2. RUTA PRINCIPAL (ORDENADO POR REGISTRO REAL)
@app.route('/')
def index():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Ordenamos por la fecha de registro para que aparezcan en fila según se crean
    cur.execute("SELECT * FROM portatiles ORDER BY fecha_registro ASC")
    
    portatiles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', portatiles=portatiles)

# 3. AÑADIR NUEVO EQUIPO
@app.route('/nuevo_portatil', methods=['GET', 'POST'])
def nuevo_portatil():
    if request.method == 'POST':
        id_p = request.form['id_portatil'].strip().upper()
        desc = request.form['descripcion_tecnica'].strip()
        serial = request.form['num_serie'].strip().upper()
        ubi = request.form['ubicacion'].strip()
        
        conn = conectar_db()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO portatiles (id, descripcion_tecnica, num_serie, ubicacion) VALUES (%s,%s,%s,%s)', 
                        (id_p, desc, serial, ubi))
            conn.commit()
            return redirect(url_for('index'))
        except Exception as e:
            conn.rollback()
            return render_template('nuevo.html', error=f"Error: El ID ya existe o hay un fallo de conexión.")
        finally:
            cur.close()
            conn.close()
    return render_template('nuevo.html')

# 4. EDITAR EQUIPO EXISTENTE
@app.route('/editar_equipo/<id_p>', methods=['GET', 'POST'])
def editar_equipo(id_p):
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nuevo_id = request.form['id_portatil'].strip().upper()
        nueva_desc = request.form['descripcion_tecnica'].strip()
        nuevo_serial = request.form['num_serie'].strip().upper()
        nueva_ubi = request.form['ubicacion'].strip()
        nuevo_estado = request.form['estado']
        
        cur.execute('''UPDATE portatiles 
                        SET id = %s, descripcion_tecnica = %s, num_serie = %s, ubicacion = %s, estado = %s 
                        WHERE id = %s''', 
                    (nuevo_id, nueva_desc, nuevo_serial, nueva_ubi, nuevo_estado, id_p))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    cur.execute('SELECT * FROM portatiles WHERE id = %s', (id_p,))
    equipo = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('editar.html', equipo=equipo)

# 5. PRESTAR EQUIPO
@app.route('/prestar', methods=['GET', 'POST'])
def prestar():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        id_p = request.form['id_portatil']
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip().lower()
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        cur.execute('INSERT INTO prestamos (id_portatil, persona, correo, fecha_prestamo) VALUES (%s,%s,%s,%s)', 
                    (id_p, nombre, correo, fecha))
        cur.execute('UPDATE portatiles SET estado = %s WHERE id = %s', ("Prestado", id_p))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    # Mantener el mismo orden en el desplegable
    cur.execute("SELECT * FROM portatiles WHERE estado = 'Disponible' ORDER BY fecha_registro ASC")
    disponibles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('prestar.html', disponibles=disponibles)

# 6. DEVOLVER EQUIPO
@app.route('/devolver', methods=['GET', 'POST'])
def devolver():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        id_p = request.form['id_portatil']
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        cur.execute('UPDATE prestamos SET fecha_devolucion = %s WHERE id_portatil = %s AND fecha_devolucion IS NULL', 
                    (fecha, id_p))
        cur.execute('UPDATE portatiles SET estado = %s WHERE id = %s', ("Disponible", id_p))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    
    query = '''SELECT p.id, pr.persona 
                FROM portatiles p 
                JOIN prestamos pr ON p.id = pr.id_portatil 
                WHERE p.estado = 'Prestado' AND pr.fecha_devolucion IS NULL
                ORDER BY p.fecha_registro ASC'''
    cur.execute(query)
    prestados = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('devolver.html', prestados=prestados)

# 7. ELIMINAR EQUIPO
@app.route('/eliminar_equipo/<id_p>')
def eliminar_equipo(id_p):
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT estado FROM portatiles WHERE id = %s', (id_p,))
    equipo = cur.fetchone()
    if equipo and equipo['estado'] == 'Prestado':
        cur.close()
        conn.close()
        return "Error: No se puede eliminar un equipo que está prestado."
    
    cur.execute('DELETE FROM portatiles WHERE id = %s', (id_p,))
    cur.execute('DELETE FROM prestamos WHERE id_portatil = %s', (id_p,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

# 8. HISTORIAL DE PRÉSTAMOS
@app.route('/historial')
def historial():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = '''SELECT id_portatil, persona, fecha_prestamo, fecha_devolucion 
                FROM prestamos 
                ORDER BY id_prestamo DESC'''
    cur.execute(query)
    registros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('historial.html', registros=registros)

# 9. VACIAR HISTORIAL
@app.route('/vaciar_historial')
def vaciar_historial():
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM prestamos WHERE fecha_devolucion IS NOT NULL')
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('historial'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)