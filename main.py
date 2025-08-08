from flask import Flask, jsonify, request, render_template
import json
import os
import random

app = Flask(__name__)

# Ruta del archivo JSON
RUTA_JSON = "verbos.json"

# Cargar verbos desde el archivo
def cargar_verbos():
    if os.path.exists(RUTA_JSON):
        with open(RUTA_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Guardar verbos en el archivo
def guardar_verbos(verbos):
    with open(RUTA_JSON, "w", encoding="utf-8") as f:
        json.dump(verbos, f, ensure_ascii=False, indent=4)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/obtener_verbos", methods=["GET"])
def obtener_verbos():
    return jsonify(cargar_verbos())

@app.route("/agregar_verbo", methods=["POST"])
def agregar_verbo():
    data = request.json
    verbos = cargar_verbos()
    verbos.append(data)
    guardar_verbos(verbos)
    return jsonify({"mensaje": "Verbo agregado con éxito"})

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json
    verbos = cargar_verbos()
    for i, verbo in enumerate(verbos):
        if i == data["index"]:
            verbos[i] = data["nuevo"]
            break
    guardar_verbos(verbos)
    return jsonify({"mensaje": "Verbo editado con éxito"})

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json
    verbos = cargar_verbos()
    if 0 <= data["index"] < len(verbos):
        verbos.pop(data["index"])
        guardar_verbos(verbos)
    return jsonify({"mensaje": "Verbo eliminado con éxito"})

@app.route("/pregunta", methods=["POST"])
def pregunta():
    data = request.json
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", None)

    verbos = cargar_verbos()

    # Filtrar según tipo
    if tipo != "todos":
        verbos = [v for v in verbos if v["tipo"] == tipo]

    # Selección de verbos
    if cantidad and cantidad != "ilimitado":
        verbos = random.sample(verbos, min(cantidad, len(verbos)))
    else:
        random.shuffle(verbos)

    preguntas = []
    for v in verbos:
        modo = random.choice(["presente", "pasado", "traduccion"])
        if modo == "presente":
            preguntas.append({
                "pregunta": f"¿Cuál es el pasado de '{v['presente']}'?",
                "respuesta": v["pasado"]
            })
        elif modo == "pasado":
            preguntas.append({
                "pregunta": f"¿Cuál es el presente de '{v['pasado']}'?",
                "respuesta": v["presente"]
            })
        else:
            preguntas.append({
                "pregunta": f"¿Cómo se traduce '{v['presente']}' al español?",
                "respuesta": v["traduccion"]
            })

    return jsonify(preguntas)

if __name__ == "__main__":
    app.run(debug=True)
