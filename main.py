from flask import Flask, render_template, jsonify, request
import random
import json
import os

app = Flask(__name__)
VERBOS_FILE = 'verbos.json'

def cargar_verbos():
    if os.path.exists(VERBOS_FILE):
        with open(VERBOS_FILE, 'r') as f:
            return json.load(f)
    return []

def guardar_verbos(verbos):
    with open(VERBOS_FILE, 'w') as f:
        json.dump(verbos, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pregunta')
def pregunta():
    verbos = cargar_verbos()
    if not verbos:
        return jsonify({"pregunta": "No hay verbos cargados.", "respuesta": ""})

    verbo = random.choice(verbos)
    tipo = random.choice(['pasado', 'presente', 'traduccion'])

    if tipo == 'pasado':
        pregunta = f"¿Cuál es el pasado de '{verbo['presente']}'?"
        respuesta = verbo['pasado']
    elif tipo == 'presente':
        pregunta = f"¿Cuál es el presente de '{verbo['pasado']}'?"
        respuesta = verbo['presente']
    else:
        pregunta = f"¿Cómo se traduce '{verbo['presente']}' al español?"
        respuesta = verbo['traduccion']

    return jsonify({"pregunta": pregunta, "respuesta": respuesta})

@app.route('/agregar_verbo', methods=['POST'])
def agregar_verbo():
    data = request.get_json()
    presente = data.get('presente', '').strip().lower()
    pasado = data.get('pasado', '').strip().lower()
    traduccion = data.get('traduccion', '').strip().lower()

    if not presente or not pasado or not traduccion:
        return jsonify({"estado": "error", "mensaje": "Faltan campos."})

    verbos = cargar_verbos()
    for verbo in verbos:
        if verbo['presente'] == presente:
            return jsonify({"estado": "error", "mensaje": "El verbo ya existe."})

    verbos.append({
        "presente": presente,
        "pasado": pasado,
        "traduccion": traduccion
    })
    guardar_verbos(verbos)
    return jsonify({"estado": "ok", "mensaje": "✅ Verbo agregado correctamente."})

@app.route('/verbos')
def lista_verbos():
    return jsonify(cargar_verbos())

@app.route('/eliminar_verbo', methods=['POST'])
def eliminar_verbo():
    data = request.get_json()
    presente = data.get('presente', '')
    verbos = cargar_verbos()
    nuevos = [v for v in verbos if v['presente'] != presente]
    guardar_verbos(nuevos)
    return jsonify({"estado": "ok", "mensaje": "🗑️ Verbo eliminado"})

@app.route('/editar_verbo', methods=['POST'])
def editar_verbo():
    data = request.get_json()
    original = data.get('original')
    nuevo = data.get('nuevo')

    verbos = cargar_verbos()
    for v in verbos:
        if v['presente'] == original:
            v['presente'] = nuevo['presente']
            v['pasado'] = nuevo['pasado']
            v['traduccion'] = nuevo['traduccion']
            break

    guardar_verbos(verbos)
    return jsonify({"estado": "ok", "mensaje": "✏️ Verbo editado"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
