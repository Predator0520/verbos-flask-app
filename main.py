from flask import Flask, jsonify, request, render_template
import json
import os
import random
from datetime import datetime

app = Flask(__name__)

# ===== Persistencia en volumen Render =====
DATA_DIR = "/data"
os.makedirs(DATA_DIR, exist_ok=True)

VERBOS_FILE = os.path.join(DATA_DIR, "verbos.json")
STATS_FILE  = os.path.join(DATA_DIR, "stats.json")

def _leer_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def _escribir_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _migrar_si_falta():
    # Si /data está vacío, copia semillas del repo (si existen)
    if not os.path.exists(VERBOS_FILE):
        seed = _leer_json("verbos.json", [])
        _escribir_json(VERBOS_FILE, seed)
    if not os.path.exists(STATS_FILE):
        seed = _leer_json("stats.json", [])
        _escribir_json(STATS_FILE, seed)

_migrar_si_falta()

def cargar_verbos(): return _leer_json(VERBOS_FILE, [])
def guardar_verbos(v): _escribir_json(VERBOS_FILE, v)
def cargar_stats(): return _leer_json(STATS_FILE, [])
def guardar_stats(s): _escribir_json(STATS_FILE, s)

# ---------- Vistas ----------
@app.route("/")
def index():
    return render_template("index.html")

# ---------- Verbos CRUD ----------
@app.route("/obtener_verbos", methods=["GET"])
def obtener_verbos():
    return jsonify(cargar_verbos())

@app.route("/agregar_verbo", methods=["POST"])
def agregar_verbo():
    data = request.json or {}
    req = ["presente","pasado","traduccion","categoria"]
    if not all(k in data and str(data[k]).strip() for k in req):
        return jsonify({"ok": False, "msg": "Faltan campos"}), 400

    verbos = cargar_verbos()
    if any(v["presente"].lower().strip() == data["presente"].lower().strip() for v in verbos):
        return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400

    verbos.append({
        "presente": data["presente"].strip().lower(),
        "pasado": data["pasado"].strip().lower(),
        "traduccion": data["traduccion"].strip().lower(),
        "categoria": data["categoria"].strip().lower()  # regular | irregular
    })
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✅ Verbo agregado"})

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json or {}  # {index, verbo:{...}}
    if "index" not in data or "verbo" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    verbos = cargar_verbos()
    idx = int(data["index"])
    if idx < 0 or idx >= len(verbos):
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400

    nuevo = data["verbo"]
    req = ["presente","pasado","traduccion","categoria"]
    if not all(k in nuevo and str(nuevo[k]).strip() for k in req):
        return jsonify({"ok": False, "msg": "Faltan campos"}), 400

    verbos[idx] = {
        "presente": nuevo["presente"].strip().lower(),
        "pasado": nuevo["pasado"].strip().lower(),
        "traduccion": nuevo["traduccion"].strip().lower(),
        "categoria": nuevo["categoria"].strip().lower()
    }
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✏️ Verbo editado"})

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json or {}  # {index}
    if "index" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400
    verbos = cargar_verbos()
    idx = int(data["index"])
    if idx < 0 or idx >= len(verbos):
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400
    del verbos[idx]
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "🗑️ Verbo eliminado"})

# ---------- Preguntas ----------
@app.route("/preguntas", methods=["POST"])
def preguntas():
    """
    Recibe: { tipo: 'regular'|'irregular'|'todos', cantidad: 10|20|30|40|'ilimitado' }
    Devuelve: [ {pregunta, respuesta}, ... ]
    """
    data = request.json or {}
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", "ilimitado")

    verbos = cargar_verbos()
    if tipo != "todos":
        verbos = [v for v in verbos if v.get("categoria") == tipo]

    if not verbos:
        return jsonify([])

    def pregunta_de(v, modo):
        if modo == "presente":
            return {"pregunta": f"¿Cuál es el presente de '{v['pasado']}'?",
                    "respuesta": v["presente"]}
        if modo == "pasado":
            return {"pregunta": f"¿Cuál es el pasado de '{v['presente']}'?",
                    "respuesta": v["pasado"]}
        return {"pregunta": f"¿Cómo se traduce '{v['presente']}' al español?",
                "respuesta": v["traduccion"]}

    modos = ["presente","pasado","traduccion"]
    preguntas = []

    # Limitado: genera N preguntas exactas (con repetición si hace falta)
    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))  # tope seguridad
        for _ in range(n):
            v = random.choice(verbos)
            m = random.choice(modos)
            preguntas.append(pregunta_de(v, m))
    else:
        # Ilimitado: devuelve un pool para reciclar (máx 50)
        pool = verbos[:]
        random.shuffle(pool)
        pool = pool[:50] if len(pool) > 50 else pool
        for v in pool:
            m = random.choice(modos)
            preguntas.append(pregunta_de(v, m))

    return jsonify(preguntas)

# ---------- Estadísticas ----------
@app.route("/guardar_resultado", methods=["POST"])
def guardar_resultado():
    data = request.json or {}
    req = ["usuario", "tipo", "limitado", "correctas", "incorrectas", "duracion_segundos"]
    if not all(k in data for k in req):
        return jsonify({"ok": False, "msg": "Datos incompletos"}), 400

    total = int(data["correctas"]) + int(data["incorrectas"])
    porcentaje = round((int(data["correctas"]) / total) * 100, 2) if total > 0 else 0.0

    registro = {
        "usuario": (data.get("usuario") or "invitado").strip(),
        "tipo": data.get("tipo", "todos"),
        "limitado": bool(data.get("limitado", False)),
        "cantidad": data.get("cantidad", "ilimitado"),
        "correctas": int(data.get("correctas", 0)),
        "incorrectas": int(data.get("incorrectas", 0)),
        "porcentaje": porcentaje,
        "streak_max": int(data.get("streak_max", 0)),
        "duracion_segundos": int(data.get("duracion_segundos", 0)),
        "fecha": datetime.utcnow().isoformat() + "Z"
    }
    stats = cargar_stats()
    stats.append(registro)
    guardar_stats(stats)
    return jsonify({"ok": True, "msg": "📊 Resultado guardado", "registro": registro})

@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    usuario = (request.args.get("usuario") or "").strip()
    stats = cargar_stats()
    if usuario:
        stats = [s for s in stats if s.get("usuario", "").lower() == usuario.lower()]
    # ordena por fecha (desc)
    stats.sort(key=lambda x: x.get("fecha",""), reverse=True)
    return jsonify(stats)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
