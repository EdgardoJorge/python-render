import pusher
import pymssql
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

# Configuracion de Pusher
pusher_client = pusher.Pusher(
    app_id='2062321',
    key='ffe42ba29cf735fcd0ac',
    secret='eedcd5fb65b012c67ad1',
    cluster='mt1',
    ssl=True
)

app = Flask(__name__)
CORS(app)

# Configuracion de la conexion a SQL Server (SomeeHost) - SIN ODBC DRIVER
def get_db_connection():
    try:
        conn = pymssql.connect(
            server='python-server.mssql.somee.com',
            user='Edgardodev_SQLLogin_1',
            password='ebnhdelgtq',
            database='python-server'
        )
        return conn
    except Exception as e:
        print(f"Error de conexion: {e}")
        raise

# Ruta principal
@app.route('/')
def inicio():
    return jsonify({
        'mensaje': 'API de Mensajeria con SQL Server',
        'estado': 'Funcionando',
        'version': '1.0',
        'servidor': 'SomeeHost',
        'driver': 'pymssql (sin ODBC)'
    }), 200

# Ruta para probar conexion
@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM MensajeDirecto")
        total_mensajes = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'mensaje': 'Conexion exitosa',
            'version_sql': version[:100],
            'total_mensajes': total_mensajes
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Ruta para enviar mensaje
@app.route('/enviar-mensaje', methods=['POST'])
def enviar_mensaje():
    try:
        data = request.json
        id_emisor = data.get('id_emisor')
        id_receptor = data.get('id_receptor')
        texto_mensaje = data.get('texto_mensaje')
        
        if not all([id_emisor, id_receptor, texto_mensaje]):
            return jsonify({'error': 'Faltan datos requeridos'}), 400
        
        if not texto_mensaje.strip():
            return jsonify({'error': 'El mensaje no puede estar vacio'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        fecha_envio = datetime.now()
        
        cursor.execute(
            """
            INSERT INTO MensajeDirecto (IdEmisor, IdReceptor, TextoMensaje, FechaEnvio)
            VALUES (%s, %s, %s, %s);
            SELECT SCOPE_IDENTITY() AS id;
            """,
            (id_emisor, id_receptor, texto_mensaje, fecha_envio)
        )
        
        id_mensaje = cursor.fetchone()[0]
        conn.commit()
        
        cursor.close()
        conn.close()
        
        payload = {
            'id_mensaje': int(id_mensaje),
            'id_emisor': id_emisor,
            'id_receptor': id_receptor,
            'texto_mensaje': texto_mensaje,
            'fecha_envio': fecha_envio.strftime('%Y-%m-%d %H:%M:%S')
        }
        
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
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Ruta para obtener historial
@app.route('/historial-mensajes', methods=['GET'])
def obtener_historial():
    try:
        id_usuario1 = request.args.get('id_usuario1', type=int)
        id_usuario2 = request.args.get('id_usuario2', type=int)
        limite = request.args.get('limite', default=50, type=int)
        
        if not all([id_usuario1, id_usuario2]):
            return jsonify({'error': 'Faltan parametros requeridos'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT TOP (%s) IdMensaje, IdEmisor, IdReceptor, TextoMensaje, FechaEnvio
            FROM MensajeDirecto
            WHERE (IdEmisor = %s AND IdReceptor = %s)
               OR (IdEmisor = %s AND IdReceptor = %s)
            ORDER BY FechaEnvio DESC
            """,
            (limite, id_usuario1, id_usuario2, id_usuario2, id_usuario1)
        )
        
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

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'mensaje': 'API funcionando'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
