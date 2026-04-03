from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

app = Flask(__name__)

def conectar_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS portatiles (
                    id TEXT PRIMARY KEY, 
                    descripcion_tecnica TEXT, 
                    num_serie TEXT,
                    ubicacion TEXT, 
                    estado TEXT DEFAULT 'Disponible',
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
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

@app.route('/')
def index():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = '''
        SELECT p.*, pr.persona as usuario_actual
        FROM portatiles p
        LEFT JOIN prestamos pr ON p.id = pr.id_portatil AND pr.fecha_devolucion IS NULL
        ORDER BY p.fecha_registro ASC
    '''
    cur.execute(query)
    portatiles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', portatiles=portatiles)

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
        except:
            conn.rollback()
            return "Error: El ID ya existe."
        finally:
            cur.close()
            conn.close()
    return render_template('nuevo.html')

@app.route('/editar_equipo/<id_p>', methods=['GET', 'POST'])
def editar_equipo(id_p):
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        nuevo_id = request.form['id_portatil'].strip().upper()
        cur.execute('''UPDATE portatiles SET id=%s, descripcion_tecnica=%s, num_serie=%s, ubicacion=%s, estado=%s WHERE id=%s''', 
                    (nuevo_id, request.form['descripcion_tecnica'], request.form['num_serie'], request.form['ubicacion'], request.form['estado'], id_p))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    cur.execute('SELECT * FROM portatiles WHERE id = %s', (id_p,))
    equipo = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('editar.html', equipo=equipo)

@app.route('/prestar', methods=['GET', 'POST'])
def prestar():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        cur.execute('INSERT INTO prestamos (id_portatil, persona, correo, fecha_prestamo) VALUES (%s,%s,%s,%s)', 
                    (request.form['id_portatil'], request.form['nombre'], request.form['correo'], fecha))
        cur.execute('UPDATE portatiles SET estado = %s WHERE id = %s', ("Prestado", request.form['id_portatil']))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    cur.execute("SELECT * FROM portatiles WHERE estado = 'Disponible' ORDER BY fecha_registro ASC")
    disponibles = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('prestar.html', disponibles=disponibles)

@app.route('/devolver', methods=['GET', 'POST'])
def devolver():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if request.method == 'POST':
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        cur.execute('UPDATE prestamos SET fecha_devolucion = %s WHERE id_portatil = %s AND fecha_devolucion IS NULL', (fecha, request.form['id_portatil']))
        cur.execute('UPDATE portatiles SET estado = %s WHERE id = %s', ("Disponible", request.form['id_portatil']))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    cur.execute("SELECT p.id, pr.persona FROM portatiles p JOIN prestamos pr ON p.id = pr.id_portatil WHERE p.estado = 'Prestado' AND pr.fecha_devolucion IS NULL")
    prestados = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('devolver.html', prestados=prestados)

@app.route('/eliminar_equipo/<id_p>')
def eliminar_equipo(id_p):
    conn = conectar_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM portatiles WHERE id = %s', (id_p,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/historial')
def historial():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute('SELECT * FROM prestamos ORDER BY id_prestamo DESC')
    registros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('historial.html', registros=registros)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)