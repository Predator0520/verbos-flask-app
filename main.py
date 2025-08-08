from flask import Flask, jsonify, request, render_template
import json
import os
import random
from datetime import datetime

app = Flask(__name__)

# ===== Persistencia (Render usa /var/data) =====
DEFAULT_DATA_DIR = "/var/data"  # disco persistente en Render (ver render.yaml)
DATA_DIR = os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)

def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, ".write_test")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
            f.flush()
            os.fsync(f.fileno())
        os.remove(test)
        return True
    except Exception:
        return False

# Si /var/data no es escribible, usa cwd (local dev)
if not _writable(DATA_DIR):
    DATA_DIR = os.getcwd()

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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        # Garantiza persistencia incluso si el contenedor se suspende
        f.flush()
        os.fsync(f.fileno())

def _migrar_si_falta():
    # Si no existe el archivo en /var/data, intenta seed desde el repo (verbos.json/stats.json)
    if not os.path.exists(VERBOS_FILE):
        seed = _leer_json("verbos.json", [])
        # Normaliza campos faltantes
        for v in seed:
            v.setdefault("traduccion_pasado", v.get("traduccion", ""))
            v.setdefault("continuo", "")
            v.setdefault("traduccion_continuo", v.get("traduccion_pasado", v.get("traduccion","")))
            v.setdefault("categoria", v.get("categoria","regular"))
        _escribir_json(VERBOS_FILE, seed)
    if not os.path.exists(STATS_FILE):
        seed = _leer_json("stats.json", [])
        _escribir_json(STATS_FILE, seed)

_migrar_si_falta()

# ---------- Utilidades de idioma ----------
def _is_vowel(c): return c.lower() in "aeiou"

def _gerund(base: str) -> str:
    """
    Construye el gerundio en inglés (forma -ing) con reglas comunes.
    No pretende cubrir el 100%, pero sirve para autocompletar.
    """
    w = base.strip().lower()
    if not w:
        return ""
    if w == "be":   # irregular común
        return "being"
    if w.endswith("ie"):
        return w[:-2] + "ying"   # die -> dying
    if w.endswith("e") and len(w) > 2 and w[-2] not in "aeiou":
        # make -> making, but see -> seeing (por la vocal antes)
        if w.endswith("ee"):
            return w + "ing"
        return w[:-1] + "ing"
    # Duplicación de consonante final en patrón CVC corto (run -> running)
    if len(w) >= 3 and (not _is_vowel(w[-1])) and _is_vowel(w[-2]) and (not _is_vowel(w[-3])):
        # evita duplicar en 'w', 'x', 'y'
        if w[-1] not in "wxy":
            return w + w[-1] + "ing"
    return w + "ing"

def _autocompletar_continuo(v: dict) -> dict:
    """
    Asegura que exista 'continuo' y 'traduccion_continuo'.
    continuo = "was/were <gerundio(base)>"
    traduccion_continuo = traduccion_pasado (fallback a traduccion)
    """
    v.setdefault("presente","")
    v.setdefault("traduccion","")
    v.setdefault("traduccion_pasado", v.get("traduccion",""))
    v.setdefault("continuo","")
    v.setdefault("traduccion_continuo", v.get("traduccion_pasado", v.get("traduccion","")))
    if not v["continuo"]:
        g = _gerund(v["presente"])
        v["continuo"] = f"was/were {g}" if g else ""
    if not v["traduccion_continuo"]:
        v["traduccion_continuo"] = v.get("traduccion_pasado") or v.get("traduccion") or ""
    return v

# ---------- Acceso a datos ----------
def cargar_verbos():
    verbos = _leer_json(VERBOS_FILE, [])
    # Normaliza y autocompleta para compatibilidad
    out = []
    for v in verbos:
        v.setdefault("categoria", v.get("categoria","regular"))
        out.append(_autocompletar_continuo(v))
    return out

def guardar_verbos(v):
    # Antes de guardar, autocompletar continuo/esp para evitar nulos
    v = [_autocompletar_continuo(dict(item)) for item in v]
    _escribir_json(VERBOS_FILE, v)

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

    # Campos mínimos obligatorios
    req_min = ["presente","pasado","traduccion","traduccion_pasado","categoria"]
    if not all(k in data and str(data[k]).strip() for k in req_min):
        return jsonify({"ok": False, "msg": "Faltan campos obligatorios"}), 400

    # Campos opcionales (autocompletables)
    continuo = (data.get("continuo") or "").strip()
    traduccion_continuo = (data.get("traduccion_continuo") or "").strip()

    verbos = cargar_verbos()
    if any(v["presente"].lower().strip() == data["presente"].lower().strip() for v in verbos):
        return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400

    nuevo = {
        "presente": data["presente"].strip().lower(),
        "pasado": data["pasado"].strip().lower(),
        "traduccion": data["traduccion"].strip().lower(),
        "traduccion_pasado": data["traduccion_pasado"].strip().lower(),
        "continuo": continuo.lower(),
        "traduccion_continuo": traduccion_continuo.lower(),
        "categoria": data["categoria"].strip().lower()
    }
    nuevo = _autocompletar_continuo(nuevo)

    verbos.append(nuevo)
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✅ Verbo agregado", "verbo": nuevo})

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
    # Permite vacío en 'continuo' y 'traduccion_continuo' (se autocompleta)
    req_min = ["presente","pasado","traduccion","traduccion_pasado","categoria"]
    if not all(k in nuevo and str(nuevo[k]).strip() for k in req_min):
        return jsonify({"ok": False, "msg": "Faltan campos obligatorios"}), 400

    edited = {
        "presente": nuevo["presente"].strip().lower(),
        "pasado": nuevo["pasado"].strip().lower(),
        "traduccion": nuevo["traduccion"].strip().lower(),
        "traduccion_pasado": nuevo["traduccion_pasado"].strip().lower(),
        "continuo": (nuevo.get("continuo") or "").strip().lower(),
        "traduccion_continuo": (nuevo.get("traduccion_continuo") or "").strip().lower(),
        "categoria": nuevo["categoria"].strip().lower()
    }
    edited = _autocompletar_continuo(edited)

    verbos[idx] = edited
    guardar_verbos(verbos)
    return jsonify({"ok": True, "msg": "✏️ Verbo editado", "verbo": edited})

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

# ---------- Preguntas (Simple/Past Continuous) ----------
@app.route("/preguntas", methods=["POST"])
def preguntas():
    data = request.json or {}
    modo = data.get("modo", "simple")
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", "ilimitado")

    verbos = cargar_verbos()
    if modo in ("simple", "continuous") and tipo != "todos":
        verbos = [v for v in verbos if v.get("categoria") == tipo]
    if not verbos:
        return jsonify([])

    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(verbos) * 3, 60) or 30

    preguntas = []
    modos = ["a","b","c","d","e","f"]  # 6 variantes balanceadas

    for i in range(n):
        code = modos[i % 6]
        v = random.choice(verbos)
        v = _autocompletar_continuo(v)  # asegura continuo
        t_es = v.get("traduccion","")
        t_es_past = v.get("traduccion_pasado", t_es)
        cont = v.get("continuo","")
        t_es_cont = v.get("traduccion_continuo", t_es_past or t_es)

        if modo == "simple":
            if code == "a":
                preguntas.append({"pregunta": f"¿Cuál es el pasado de '{v['presente']}'?", "respuesta": v["pasado"]})
            elif code == "b":
                preguntas.append({"pregunta": f"¿Cuál es el presente de '{v['pasado']}'?", "respuesta": v["presente"]})
            elif code == "c":
                preguntas.append({"pregunta": f"¿Cómo se traduce '{v['presente']}' al español?", "respuesta": t_es})
            elif code == "d":
                preguntas.append({"pregunta": f"¿Cómo se traduce el pasado '{v['pasado']}' al español?", "respuesta": t_es_past})
            elif code == "e":
                preguntas.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": v["presente"]})
            else:
                preguntas.append({"pregunta": f"En inglés (pasado), ¿cómo se dice '{t_es_past}'?", "respuesta": v["pasado"]})
        else:  # continuous
            # Si por alguna razón cont está vacío, fuerza preguntas seguras
            if not cont or not t_es_cont:
                code = "c"
            if code == "a":
                preguntas.append({"pregunta": f"¿Cuál es el pasado continuo de '{v['presente']}'?", "respuesta": cont})
            elif code == "b":
                preguntas.append({"pregunta": f"¿Cuál es el presente del continuo '{cont}'?", "respuesta": v["presente"]})
            elif code == "c":
                preguntas.append({"pregunta": f"¿Cómo se traduce '{v['presente']}' al español?", "respuesta": t_es})
            elif code == "d":
                preguntas.append({"pregunta": f"¿Cómo se traduce el pasado continuo '{cont}' al español?", "respuesta": t_es_cont})
            elif code == "e":
                preguntas.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": v["presente"]})
            else:
                preguntas.append({"pregunta": f"En inglés (pasado continuo), ¿cómo se dice '{t_es_cont}'?", "respuesta": cont})

    return jsonify(preguntas)

# ---------- WH (traducción) ----------
@app.route("/preguntas_wh", methods=["POST"])
def preguntas_wh():
    data = request.json or {}
    cantidad = data.get("cantidad", "ilimitado")
    bank = [
        {"en": "who", "es": "quién"},
        {"en": "what", "es": "qué"},
        {"en": "when", "es": "cuándo"},
        {"en": "where", "es": "dónde"},
        {"en": "why", "es": "por qué"},
        {"en": "how", "es": "cómo"},
        {"en": "which", "es": "cuál"},
        {"en": "whose", "es": "de quién"},
        {"en": "how many", "es": "cuántos"},
        {"en": "how much", "es": "cuánto"}
    ]
    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(bank) * 3, 60)

    qs = []
    for i in range(n):
        it = random.choice(bank)
        if i % 2 == 0:
            qs.append({"pregunta": f"Traduce al español: '{it['en']}'", "respuesta": it["es"]})
        else:
            qs.append({"pregunta": f"Traduce al inglés: '{it['es']}'", "respuesta": it["en"]})
    return jsonify(qs)

# ---------- WH (oraciones opción múltiple) ----------
@app.route("/preguntas_wh_oraciones", methods=["POST"])
def preguntas_wh_oraciones():
    data = request.json or {}
    cantidad = data.get("cantidad", "ilimitado")

    templates = [
        ("___ did you call last night?",           ["Who","What","When","Where"], 0),
        ("___ is your favorite color?",            ["What","Which","Why","How"], 0),
        ("___ did they arrive?",                   ["When","Where","Who","Why"], 0),
        ("___ are you from?",                      ["Where","When","How","Who"], 0),
        ("___ are you late?",                      ["Why","How","When","What"], 0),
        ("___ do you spell your name?",            ["How","What","Why","When"], 0),
        ("___ book do you want, this one or that one?", ["Which","What","Whose","Who"], 0),
        ("___ bag is this?",                       ["Whose","Who","Which","Where"], 0),
        ("___ apples do we need for the pie?",     ["How many","How much","Which","What"], 0),
        ("___ water should I add?",                ["How much","How many","When","Why"], 0),
        ("I don’t know ___ he is calling.",        ["why","which","who","when"], 0),
        ("___ did you go to the store? (reason)",  ["Why","When","Where","Who"], 0),
        ("___ are they meeting? (place)",          ["Where","When","What","Which"], 0),
        ("___ does this word mean?",               ["What","Which","How","Why"], 0),
        ("___ car is newer, the red one or the blue one?", ["Which","What","Whose","How"], 0)
    ]

    bank = [{"pregunta": s, "opciones": opts[:], "correcta": i_ok, "respuesta": opts[i_ok]}
            for (s, opts, i_ok) in templates]

    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(bank), 60)

    random.shuffle(bank)
    return jsonify(bank[:n])

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
        "tipo": data.get("tipo", "simple"),  # simple | continuous | wh/traduccion | wh/oraciones
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
    names = sorted({ s.get("usuario","").strip() for s in stats
                     if s.get("usuario","").strip() and s.get("usuario","").lower() != "invitado" })
    return jsonify(names)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
