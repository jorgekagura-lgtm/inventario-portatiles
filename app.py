from flask import Flask, render_template, request, redirect, url_for, Response
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import csv
import io

app = Flask(__name__)

# CONFIGURACIÓN DE CONEXIÓN
def conectar_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# 1. CONFIGURACIÓN INICIAL DE LAS TABLAS (SEGURA: NO BORRA DATOS)
def init_db():
    conn = conectar_db()
    cur = conn.cursor()
    
    # Creamos la tabla de portatiles
    cur.execute('''CREATE TABLE IF NOT EXISTS portatiles (
                    id TEXT PRIMARY KEY, 
                    descripcion_tecnica TEXT, 
                    num_serie TEXT,
                    ubicacion TEXT, 
                    estado TEXT DEFAULT 'Disponible',
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Creamos la tabla de prestamos
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

# Ejecutar la inicialización al arrancar
init_db()

# 2. RUTA PRINCIPAL (MODIFICADA SOLO PARA TRAER EL NOMBRE DEL USUARIO)
@app.route('/')
def index():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # Esta consulta busca el nombre de la persona en la tabla prestamos
    # y lo asigna a 'persona' para que el HTML lo encuentre.
    query = '''
        SELECT p.*, pr.persona 
        FROM portatiles p
        LEFT JOIN prestamos pr ON p.id = pr.id_portatil AND pr.fecha_devolucion IS NULL
        ORDER BY p.fecha_registro ASC
    '''
    cur.execute(query)
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


# ==========================================
# 10. NUEVA RUTA: EXPORTAR A CSV
# ==========================================
@app.route('/exportar_csv')
def exportar_csv():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = '''
        SELECT p.id, p.descripcion_tecnica, p.num_serie, p.ubicacion, p.estado, pr.persona 
        FROM portatiles p
        LEFT JOIN prestamos pr ON p.id = pr.id_portatil AND pr.fecha_devolucion IS NULL
        ORDER BY p.fecha_registro ASC
    '''
    cur.execute(query)
    portatiles = cur.fetchall()
    cur.close()
    conn.close()

    # Crear el stream de texto para el archivo CSV
    si = io.StringIO()
    cw = csv.writer(si, delimiter=';') # Usamos punto y coma para que Excel en español lo abra perfecto
    
    # Escribir las cabeceras del Excel / CSV
    cw.writerow(['ID Portátil', 'Descripción Técnica', 'Número de Serie', 'Ubicación', 'Estado', 'Asignado a'])
    
    # Rellenar con los datos actuales
    for p in portatiles:
        cw.writerow([
            p['id'], 
            p['descripcion_tecnica'], 
            p['num_serie'], 
            p['ubicacion'], 
            p['estado'], 
            p['persona'] if p['persona'] else 'Nadie'
        ])
    
    output = si.getvalue()
    si.close()
    
    # Retornar respuesta HTTP de descarga de archivo
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=inventario_portatiles.csv"}
    )


# ==========================================
# 11. NUEVA RUTA: VISTA DE IMPRESIÓN LIMPIA
# ==========================================
@app.route('/imprimir_inventario')
def imprimir_inventario():
    conn = conectar_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    query = '''
        SELECT p.*, pr.persona 
        FROM portatiles p
        LEFT JOIN prestamos pr ON p.id = pr.id_portatil AND pr.fecha_devolucion IS NULL
        ORDER BY p.fecha_registro ASC
    '''
    cur.execute(query)
    portatiles = cur.fetchall()
    cur.close()
    conn.close()
    # Esta ruta renderiza una plantilla especial diseñada para imprimirse directamente
    return render_template('imprimir.html', portatiles=portatiles)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
