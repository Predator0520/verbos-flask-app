from flask import Flask, jsonify, request, render_template
import json, os, random, re
from datetime import datetime

app = Flask(__name__)

# ===== Persistencia =====
DEFAULT_DATA_DIR = "/var/data"
DATA_DIR = os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)

def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, ".write_test")
        with open(test, "w") as f: f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False

if not _writable(DATA_DIR):
    DATA_DIR = os.getcwd()

VERBOS_FILE = os.path.join(DATA_DIR, "verbos.json")
STATS_FILE  = os.path.join(DATA_DIR, "stats.json")

def _leer_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default
    return default

def _escribir_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _migrar_si_falta():
    if not os.path.exists(VERBOS_FILE):
        seed = _leer_json("verbos.json", [])
        _escribir_json(VERBOS_FILE, seed)
    if not os.path.exists(STATS_FILE):
        seed = _leer_json("stats.json", [])
        _escribir_json(STATS_FILE, seed)

_migrar_si_falta()

# ---------- Datos ----------
def cargar_verbos():
    verbos = _leer_json(VERBOS_FILE, [])
    for v in verbos:
        # Backwards compatibility
        v.setdefault("traduccion_pasado", v.get("traduccion", ""))
        v.setdefault("gerundio", "")  # v-ing (going, playing)
        v.setdefault("traduccion_continuo", "")  # "estaba jugando"
    return verbos

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
    req = ["presente","pasado","traduccion","traduccion_pasado","categoria"]
    # gerundio y traduccion_continuo son opcionales (pero recomendados)
    if not all(k in data and str(data[k]).strip() for k in req):
        return jsonify({"ok": False, "msg": "Faltan campos obligatorios"}), 400

    verbos = cargar_verbos()
    if any(v["presente"].lower().strip() == data["presente"].lower().strip() for v in verbos):
        return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400

    verbos.append({
        "presente": data["presente"].strip().lower(),
        "pasado": data["pasado"].strip().lower(),
        "traduccion": data["traduccion"].strip().lower(),
        "traduccion_pasado": data["traduccion_pasado"].strip().lower(),
        "gerundio": (data.get("gerundio") or "").strip().lower(),
        "traduccion_continuo": (data.get("traduccion_continuo") or "").strip().lower(),
        "categoria": data["categoria"].strip().lower()
    })
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✅ Verbo agregado"})

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json or {}
    if "index" not in data or "verbo" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    verbos = cargar_verbos()
    idx = int(data["index"])
    if idx < 0 or idx >= len(verbos):
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400

    nuevo = data["verbo"]
    req = ["presente","pasado","traduccion","traduccion_pasado","categoria"]
    if not all(k in nuevo and str(nuevo[k]).strip() for k in req):
        return jsonify({"ok": False, "msg": "Faltan campos"}), 400

    verbos[idx] = {
        "presente": nuevo["presente"].strip().lower(),
        "pasado": nuevo["pasado"].strip().lower(),
        "traduccion": nuevo["traduccion"].strip().lower(),
        "traduccion_pasado": nuevo["traduccion_pasado"].strip().lower(),
        "gerundio": (nuevo.get("gerundio") or "").strip().lower(),
        "traduccion_continuo": (nuevo.get("traduccion_continuo") or "").strip().lower(),
        "categoria": nuevo["categoria"].strip().lower()
    }
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✏️ Verbo editado"})

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json or {}
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
WH_BANK = [
    # (pregunta_con_hueco, pista_es, respuesta)
    ("__ did you arrive?", "¿cuándo?", "when"),
    ("__ did you go yesterday?", "¿adónde / dónde?", "where"),
    ("__ is your favorite sport?", "¿cuál (de varios)?", "which"),
    ("__ is this book?", "¿de quién?", "whose"),
    ("__ did it happen?", "¿por qué?", "why"),
    ("__ are you?", "¿cómo / estado?", "how"),
    ("__ much water do you drink?", "¿cuánto? (incontable)", "how much"),
    ("__ many apples do you have?", "¿cuántos? (contable)", "how many"),
    ("__ long did it take?", "¿cuánto tiempo?", "how long"),
    ("__ is your name?", "¿cuál es tu nombre?", "what"),
    ("__ did you talk to?", "¿con quién?", "who"),
]

@app.route("/preguntas", methods=["POST"])
def preguntas():
    """
    Recibe:
      {
        modo_practica: 'simple_past' | 'past_continuous' | 'wh',
        tipo: 'regular'|'irregular'|'todos',
        cantidad: 10|20|30|40|'ilimitado'
      }
    Devuelve arreglo de {pregunta, respuesta}
    """
    data = request.json or {}
    modo = data.get("modo_practica", "simple_past")
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", "ilimitado")

    # Número de preguntas
    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = 30

    if modo == "wh":
        bank = WH_BANK.copy()
        out = []
        for i in range(n):
            q = random.choice(bank)
            out.append({
                "pregunta": f"{q[0]}  (Pista: {q[1]})",
                "respuesta": q[2]
            })
        return jsonify(out)

    # Modo basado en verbos
    verbos = cargar_verbos()
    if tipo != "todos":
        verbos = [v for v in verbos if v.get("categoria") == tipo]
    if not verbos:
        return jsonify([])

    # Tipos equilibrados (6)
    modos = ["p->past", "past->p", "p->es", "past->es", "es->p", "es->past"]
    out = []
    for i in range(n):
        m = modos[i % len(modos)]
        v = random.choice(verbos)
        if modo == "simple_past":
            t_es = v.get("traduccion","")
            t_es_past = v.get("traduccion_pasado", t_es or "")
            if m == "p->past":
                out.append({"pregunta": f"¿Cuál es el pasado de '{v['presente']}'?", "respuesta": v["pasado"]})
            elif m == "past->p":
                out.append({"pregunta": f"¿Cuál es el presente de '{v['pasado']}'?", "respuesta": v["presente"]})
            elif m == "p->es":
                out.append({"pregunta": f"¿Cómo se traduce '{v['presente']}' al español?", "respuesta": t_es})
            elif m == "past->es":
                out.append({"pregunta": f"¿Cómo se traduce el pasado '{v['pasado']}' al español?", "respuesta": t_es_past})
            elif m == "es->p":
                out.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": v["presente"]})
            else:
                out.append({"pregunta": f"En inglés (pasado), ¿cómo se dice '{t_es_past}'?", "respuesta": v["pasado"]})
        else:  # past_continuous
            # Requiere gerundio y traducción del continuo
            ger = v.get("gerundio") or ""
            t_cont = v.get("traduccion_continuo") or ""
            t_es = v.get("traduccion","")
            # Si no tiene datos, degradamos a simple present/past equivalentes
            if not ger or not t_cont:
                # fallback a simple past templates
                t_es_past = v.get("traduccion_pasado", t_es or "")
                if m == "p->past":
                    out.append({"pregunta": f"¿Cuál es el pasado de '{v['presente']}'?", "respuesta": v["pasado"]})
                elif m == "past->p":
                    out.append({"pregunta": f"¿Cuál es el presente de '{v['pasado']}'?", "respuesta": v["presente"]})
                elif m == "p->es":
                    out.append({"pregunta": f"¿Cómo se traduce '{v['presente']}' al español?", "respuesta": t_es})
                elif m == "past->es":
                    out.append({"pregunta": f"¿Cómo se traduce el pasado '{v['pasado']}' al español?", "respuesta": t_es_past})
                elif m == "es->p":
                    out.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": v["presente"]})
                else:
                    out.append({"pregunta": f"En inglés (pasado), ¿cómo se dice '{t_es_past}'?", "respuesta": v["pasado"]})
            else:
                # Construimos ejemplos de pasado continuo con sujeto neutral "I" (was) o plural "they" (were)
                subj = random.choice([("I","was"), ("they","were")])
                eng_pc = f"{subj[1]} {ger}"  # "was/were playing"
                if m == "p->past":
                    out.append({"pregunta": f"En inglés (pasado continuo), completa para '{v['presente']}' con sujeto '{subj[0]}':", "respuesta": eng_pc})
                elif m == "past->p":
                    out.append({"pregunta": f"¿Cuál es el presente base del pasado continuo '{eng_pc}'?", "respuesta": v["presente"]})
                elif m == "p->es":
                    out.append({"pregunta": f"¿Cómo se traduce al español '{eng_pc}'?", "respuesta": t_cont})
                elif m == "past->es":
                    out.append({"pregunta": f"Traduce al español (pasado continuo): '{eng_pc}'", "respuesta": t_cont})
                elif m == "es->p":
                    out.append({"pregunta": f"En inglés (pasado continuo), ¿cómo se dice '{t_cont}'?", "respuesta": eng_pc})
                else:
                    out.append({"pregunta": f"Base form (presente) del español '{t_cont}':", "respuesta": v["presente"]})
    return jsonify(out)

# ---------- Estadísticas ----------
@app.route("/guardar_resultado", methods=["POST"])
def guardar_resultado():
    data = request.json or {}
    req = ["usuario","tipo","limitado","correctas","incorrectas","duracion_segundos"]
    if not all(k in data for k in req):
        return jsonify({"ok": False, "msg": "Datos incompletos"}), 400

    total = int(data["correctas"]) + int(data["incorrectas"])
    porcentaje = round((int(data["correctas"]) / total) * 100, 2) if total > 0 else 0.0

    registro = {
        "usuario": (data.get("usuario") or "invitado").strip(),
        "tipo": data.get("tipo", "todos"),
        "modo_practica": data.get("modo_practica", "simple_past"),
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
        stats = [s for s in stats if s.get("usuario","").lower() == usuario.lower()]
    stats.sort(key=lambda x: x.get("fecha",""), reverse=True)
    return jsonify(stats)

@app.route("/usuarios", methods=["GET"])
def usuarios():
    stats = cargar_stats()
    names = sorted({
        s.get("usuario","").strip()
        for s in stats
        if s.get("usuario","").strip() and s.get("usuario","").lower() != "invitado"
    })
    return jsonify(names)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
