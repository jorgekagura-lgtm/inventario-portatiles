from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

def conectar_db():
    conn = sqlite3.connect('inventario.db')
    conn.row_factory = sqlite3.Row
    return conn

# 1. CONFIGURACIÓN INICIAL DE LA BASE DE DATOS
with conectar_db() as con:
    con.execute('''CREATE TABLE IF NOT EXISTS portatiles (
                    id TEXT PRIMARY KEY, 
                    descripcion_tecnica TEXT, 
                    num_serie TEXT,
                    ubicacion TEXT, 
                    estado TEXT DEFAULT "Disponible")''')
    
    con.execute('''CREATE TABLE IF NOT EXISTS prestamos (
                    id_prestamo INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_portatil TEXT, 
                    persona TEXT, 
                    correo TEXT, 
                    fecha_prestamo TEXT, 
                    fecha_devolucion TEXT)''')

# 2. RUTA PRINCIPAL
@app.route('/')
def index():
    con = conectar_db()
    query = '''SELECT p.id, p.descripcion_tecnica, p.num_serie, p.estado, p.ubicacion, pr.persona
               FROM portatiles p
               LEFT JOIN prestamos pr ON p.id = pr.id_portatil AND pr.fecha_devolucion IS NULL
               ORDER BY p.rowid ASC'''
    portatiles = con.execute(query).fetchall()
    con.close()
    return render_template('index.html', portatiles=portatiles)

# 3. AÑADIR NUEVO EQUIPO
@app.route('/nuevo_portatil', methods=['GET', 'POST'])
def nuevo_portatil():
    if request.method == 'POST':
        id_p = request.form['id_portatil'].strip().upper()
        desc = request.form['descripcion_tecnica'].strip()
        serial = request.form['num_serie'].strip().upper()
        ubi = request.form['ubicacion'].strip()
        
        con = conectar_db()
        try:
            con.execute('INSERT INTO portatiles (id, descripcion_tecnica, num_serie, ubicacion) VALUES (?,?,?,?)', 
                        (id_p, desc, serial, ubi))
            con.commit()
            return redirect(url_for('index'))
        except:
            return render_template('nuevo.html', error="El ID del equipo ya existe.")
        finally:
            con.close()
    return render_template('nuevo.html')

# 4. EDITAR EQUIPO EXISTENTE
@app.route('/editar_equipo/<id_p>', methods=['GET', 'POST'])
def editar_equipo(id_p):
    con = conectar_db()
    if request.method == 'POST':
        nuevo_id = request.form['id_portatil'].strip().upper()
        nueva_desc = request.form['descripcion_tecnica'].strip()
        nuevo_serial = request.form['num_serie'].strip().upper()
        nueva_ubi = request.form['ubicacion'].strip()
        nuevo_estado = request.form['estado']
        
        con.execute('''UPDATE portatiles 
                        SET id = ?, descripcion_tecnica = ?, num_serie = ?, ubicacion = ?, estado = ? 
                        WHERE id = ?''', 
                    (nuevo_id, nueva_desc, nuevo_serial, nueva_ubi, nuevo_estado, id_p))
        con.commit()
        con.close()
        return redirect(url_for('index'))
    
    equipo = con.execute('SELECT * FROM portatiles WHERE id = ?', (id_p,)).fetchone()
    con.close()
    return render_template('editar.html', equipo=equipo)

# 5. PRESTAR EQUIPO
@app.route('/prestar', methods=['GET', 'POST'])
def prestar():
    con = conectar_db()
    if request.method == 'POST':
        id_p = request.form['id_portatil']
        nombre = request.form['nombre'].strip()
        correo = request.form['correo'].strip().lower()
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        con.execute('INSERT INTO prestamos (id_portatil, persona, correo, fecha_prestamo) VALUES (?,?,?,?)', 
                    (id_p, nombre, correo, fecha))
        con.execute('UPDATE portatiles SET estado = "Prestado" WHERE id = ?', (id_p,))
        con.commit()
        con.close()
        return redirect(url_for('index'))
    
    disponibles = con.execute('SELECT * FROM portatiles WHERE estado = "Disponible"').fetchall()
    con.close()
    return render_template('prestar.html', disponibles=disponibles)

# 6. DEVOLVER EQUIPO
@app.route('/devolver', methods=['GET', 'POST'])
def devolver():
    con = conectar_db()
    if request.method == 'POST':
        id_p = request.form['id_portatil']
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        con.execute('UPDATE prestamos SET fecha_devolucion = ? WHERE id_portatil = ? AND fecha_devolucion IS NULL', 
                    (fecha, id_p))
        con.execute('UPDATE portatiles SET estado = "Disponible" WHERE id = ?', (id_p,))
        con.commit()
        con.close()
        return redirect(url_for('index'))
    
    query = '''SELECT p.id, pr.persona 
                FROM portatiles p 
                JOIN prestamos pr ON p.id = pr.id_portatil 
                WHERE p.estado = "Prestado" AND pr.fecha_devolucion IS NULL'''
    prestados = con.execute(query).fetchall()
    con.close()
    return render_template('devolver.html', prestados=prestados)

# 7. ELIMINAR EQUIPO
@app.route('/eliminar_equipo/<id_p>')
def eliminar_equipo(id_p):
    con = conectar_db()
    equipo = con.execute('SELECT estado FROM portatiles WHERE id = ?', (id_p,)).fetchone()
    if equipo and equipo['estado'] == 'Prestado':
        con.close()
        return "Error: No se puede eliminar un equipo que está prestado."
    
    con.execute('DELETE FROM portatiles WHERE id = ?', (id_p,))
    con.execute('DELETE FROM prestamos WHERE id_portatil = ?', (id_p,))
    con.commit()
    con.close()
    return redirect(url_for('index'))

# 8. HISTORIAL DE PRÉSTAMOS
@app.route('/historial')
def historial():
    con = conectar_db()
    query = '''SELECT id_portatil, persona, fecha_prestamo, fecha_devolucion 
                FROM prestamos 
                ORDER BY id_prestamo DESC'''
    registros = con.execute(query).fetchall()
    con.close()
    return render_template('historial.html', registros=registros)

# 9. VACIAR HISTORIAL
@app.route('/vaciar_historial')
def vaciar_historial():
    con = conectar_db()
    con.execute('DELETE FROM prestamos WHERE fecha_devolucion IS NOT NULL')
    con.commit()
    con.close()
    return redirect(url_for('historial'))

if __name__ == '__main__':
    # Render asigna un puerto automáticamente, esto lo detecta
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)