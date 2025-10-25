import pusher
import pyodbc
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# Configuración de Pusher
pusher_client = pusher.Pusher(
    app_id='2062321',
    key='ffe42ba29cf735fcd0ac',
    secret='eedcd5fb65b012c67ad1',
    cluster='mt1',
    ssl=True
)

# Crear aplicación Flask
app = Flask(__name__)
CORS(app)  # Permitir peticiones desde el frontend

# Configuración de la conexión a SQL Server
def get_db_connection():
    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 13 for SQL Server};'
            'SERVER=IHR80PBE13;'  # Cambia por tu servidor
            'DATABASE=message;'  # Cambia por tu base de datos
            'UID=sa;'  # Cambia por tu usuario
            'PWD=continental;'  # Cambia por tu contraseña
            'TrustServerCertificate=yes;'
        )
        return conn
    except Exception as e:
        print(f"Error de conexión: {e}")
        raise

# Ruta para enviar mensaje
@app.route('/enviar-mensaje', methods=['POST'])
def enviar_mensaje():
    try:
        data = request.json
        id_emisor = data.get('id_emisor')
        id_receptor = data.get('id_receptor')
        texto_mensaje = data.get('texto_mensaje')
        
        # Validar datos
        if not all([id_emisor, id_receptor, texto_mensaje]):
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        if not texto_mensaje.strip():
            return jsonify({'error': 'El mensaje no puede estar vacío'}), 400
        
        # Guardar mensaje en la base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        INSERT INTO MensajeDirecto (IdEmisor, IdReceptor, TextoMensaje, FechaEnvio)
        OUTPUT INSERTED.IdMensaje
        VALUES (?, ?, ?, ?)
        """
        fecha_envio = datetime.now()
        cursor.execute(query, (id_emisor, id_receptor, texto_mensaje, fecha_envio))
        
        # Obtener el ID del mensaje insertado
        id_mensaje = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Preparar payload para Pusher
        payload = {
            'id_mensaje': int(id_mensaje),
            'id_emisor': id_emisor,
            'id_receptor': id_receptor,
            'texto_mensaje': texto_mensaje,
            'fecha_envio': fecha_envio.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Enviar a ambos usuarios (emisor y receptor)
        pusher_client.trigger(
            [f'chat-{id_receptor}', f'chat-{id_emisor}'],
            'nuevo-mensaje',
            payload
        )
        
        return jsonify({
            'success': True,
            'mensaje': 'Mensaje enviado correctamente',
            'data': payload
        }), 200
        
    except pyodbc.Error as e:
        return jsonify({'error': f'Error de base de datos: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener historial de mensajes entre dos usuarios
@app.route('/historial-mensajes', methods=['GET'])
def obtener_historial():
    try:
        id_usuario1 = request.args.get('id_usuario1', type=int)
        id_usuario2 = request.args.get('id_usuario2', type=int)
        limite = request.args.get('limite', default=50, type=int)
        
        if not all([id_usuario1, id_usuario2]):
            return jsonify({'error': 'Faltan parámetros requeridos'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT TOP (?) IdMensaje, IdEmisor, IdReceptor, TextoMensaje, FechaEnvio
        FROM MensajeDirecto
        WHERE (IdEmisor = ? AND IdReceptor = ?)
           OR (IdEmisor = ? AND IdReceptor = ?)
        ORDER BY FechaEnvio DESC
        """
        
        cursor.execute(query, (limite, id_usuario1, id_usuario2, id_usuario2, id_usuario1))
        mensajes = cursor.fetchall()
        
        resultado = []
        for mensaje in mensajes:
            resultado.append({
                'id_mensaje': mensaje[0],
                'id_emisor': mensaje[1],
                'id_receptor': mensaje[2],
                'texto_mensaje': mensaje[3],
                'fecha_envio': mensaje[4].strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Invertir para mostrar del más antiguo al más reciente
        resultado.reverse()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'cantidad': len(resultado),
            'mensajes': resultado
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener mensajes no leídos (opcional)
@app.route('/mensajes-nuevos/<int:id_usuario>', methods=['GET'])
def mensajes_nuevos(id_usuario):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
        SELECT IdMensaje, IdEmisor, IdReceptor, TextoMensaje, FechaEnvio
        FROM MensajeDirecto
        WHERE IdReceptor = ?
        ORDER BY FechaEnvio DESC
        """
        
        cursor.execute(query, (id_usuario,))
        mensajes = cursor.fetchall()
        
        resultado = []
        for mensaje in mensajes:
            resultado.append({
                'id_mensaje': mensaje[0],
                'id_emisor': mensaje[1],
                'id_receptor': mensaje[2],
                'texto_mensaje': mensaje[3],
                'fecha_envio': mensaje[4].strftime('%Y-%m-%d %H:%M:%S')
            })
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'cantidad': len(resultado),
            'mensajes': resultado
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para eliminar un mensaje
@app.route('/eliminar-mensaje/<int:id_mensaje>', methods=['DELETE'])
def eliminar_mensaje(id_mensaje):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = "DELETE FROM MensajeDirecto WHERE IdMensaje = ?"
        cursor.execute(query, (id_mensaje,))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # Notificar eliminación por Pusher (opcional)
        pusher_client.trigger('mensajes', 'mensaje-eliminado', {
            'id_mensaje': id_mensaje
        })
        
        return jsonify({
            'success': True,
            'mensaje': 'Mensaje eliminado correctamente'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta de prueba
@app.route('/test', methods=['GET'])
def test():
    return jsonify({'mensaje': 'API de mensajería funcionando correctamente'}), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
