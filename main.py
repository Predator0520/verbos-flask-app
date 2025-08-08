from flask import Flask, jsonify, request, render_template, Response
import json
import os
import random
from datetime import datetime
from io import StringIO
from typing import List, Dict

app = Flask(__name__)

# =======================
#   PERSISTENCIA & PATHS
# =======================
DEFAULT_DATA_DIR = "/var/data"  # Render mount
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

if not _writable(DATA_DIR):
    DATA_DIR = os.getcwd()

VERBOS_FILE = os.path.join(DATA_DIR, "verbos.json")
STATS_FILE  = os.path.join(DATA_DIR, "stats.json")

# =======================
#     JSON HELPERS
# =======================
def _read_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default
    return default

def _write_json_atomic(path: str, data):
    """Escritura atómica + fsync: escribe a .tmp y reemplaza el real"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atómico en la mayoría de FS

def _backup_rotate(path: str, max_keep: int = 7):
    """Crea una copia fechada y rota (solo para verbos)"""
    if not os.path.exists(path):
        return
    base_dir = os.path.dirname(path)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    backup_name = os.path.join(base_dir, f"backup-verbos-{ts}.json")
    try:
        with open(path, "r", encoding="utf-8") as src, open(backup_name, "w", encoding="utf-8") as dst:
            dst.write(src.read())
            dst.flush()
            os.fsync(dst.fileno())
    except Exception:
        return
    # rotar
    files = sorted([f for f in os.listdir(base_dir) if f.startswith("backup-verbos-") and f.endswith(".json")])
    excess = len(files) - max_keep
    for i in range(excess):
        try:
            os.remove(os.path.join(base_dir, files[i]))
        except Exception:
            pass

def _write_json_safe(path: str, data, do_backup=False):
    if do_backup:
        _backup_rotate(path)
    _write_json_atomic(path, data)

def _migrate_if_missing():
    # Si no existe en /var/data, intentar "seed" desde repo
    if not os.path.exists(VERBOS_FILE):
        seed = _read_json("verbos.json", [])
        seed_norm = []
        for v in seed:
            seed_norm.append(_normalize_verb_input(v))
        _write_json_safe(VERBOS_FILE, seed_norm, do_backup=False)
    if not os.path.exists(STATS_FILE):
        seed = _read_json("stats.json", [])
        _write_json_safe(STATS_FILE, seed, do_backup=False)

_migrate_if_missing()

# =======================
#   LENGUAJE & NORMALIZ.
# =======================
def _is_vowel(c): return c.lower() in "aeiou"

def _gerund(base: str) -> str:
    """Gerundio simple para autocompletar (-ing)."""
    w = (base or "").strip().lower()
    if not w:
        return ""
    if w == "be":
        return "being"
    if w.endswith("ie"):
        return w[:-2] + "ying"   # die -> dying
    if w.endswith("e") and len(w) > 2 and w[-2] not in "aeiou":
        if w.endswith("ee"):
            return w + "ing"     # see -> seeing
        return w[:-1] + "ing"    # make -> making
    # duplicación CVC corta: run -> running
    if len(w) >= 3 and (not _is_vowel(w[-1])) and _is_vowel(w[-2]) and (not _is_vowel(w[-3])):
        if w[-1] not in "wxy":
            return w + w[-1] + "ing"
    return w + "ing"

def _autofill_continuous(v: Dict) -> Dict:
    base = v.get("presente") or v.get("base") or ""
    v.setdefault("traduccion", "")
    v.setdefault("traduccion_pasado", v.get("traduccion", ""))
    v.setdefault("continuo", v.get("past_continuous", ""))
    v.setdefault("traduccion_continuo", v.get("traduccion_continuo", ""))

    if not v["continuo"]:
        g = _gerund(base)
        v["continuo"] = f"was / were {g}" if g else ""

    if not v["traduccion_continuo"]:
        v["traduccion_continuo"] = v.get("traduccion_pasado") or v.get("traduccion") or ""
    return v

def _normalize_verb_input(v: Dict) -> Dict:
    presente = (v.get("presente") or v.get("base") or "").strip().lower()
    pasado = (v.get("pasado") or v.get("past") or "").strip().lower()
    traduccion = (v.get("traduccion") or v.get("traducción") or "").strip().lower()
    traduccion_pasado = (v.get("traduccion_pasado") or v.get("traducción_pasado") or v.get("traduccion_past") or v.get("traducción_past") or "").strip().lower()
    continuo = (v.get("continuo") or v.get("past_continuous") or "").strip().lower()
    traduccion_continuo = (v.get("traduccion_continuo") or v.get("traducción_continuo") or "").strip().lower()
    categoria = (v.get("categoria") or v.get("category") or "regular").strip().lower()

    out = {
        "presente": presente,
        "pasado": pasado,
        "traduccion": traduccion,
        "traduccion_pasado": traduccion_pasado or traduccion,
        "continuo": continuo,
        "traduccion_continuo": traduccion_continuo,
        "categoria": categoria if categoria in ("regular", "irregular") else "regular",
    }
    out = _autofill_continuous(out)
    return out

def _normalize_verb_strict_for_add(data: Dict) -> Dict:
    req_min = ["presente", "pasado", "traduccion", "traduccion_pasado", "categoria"]
    if not all(k in data and str(data[k]).strip() for k in req_min):
        raise ValueError("Faltan campos obligatorios.")
    return _normalize_verb_input(data)

# ================
#  ACCESS LAYERS
# ================
def load_verbs() -> List[Dict]:
    arr = _read_json(VERBOS_FILE, [])
    return [_normalize_verb_input(v) for v in arr]

def save_verbs(verbs: List[Dict]):
    norm = [_normalize_verb_input(v) for v in verbs]
    _write_json_safe(VERBOS_FILE, norm, do_backup=True)

def load_stats() -> List[Dict]:
    return _read_json(STATS_FILE, [])

def save_stats(stats: List[Dict]):
    _write_json_safe(STATS_FILE, stats, do_backup=False)

# ============
#   VISTAS
# ============
@app.route("/")
def index():
    return render_template("index.html")

# ============
#  VERBOS API
# ============
@app.route("/obtener_verbos", methods=["GET"])
def obtener_verbos():
    return jsonify(load_verbs())

@app.route("/agregar_verbo", methods=["POST"])
def agregar_verbo():
    data = request.json or {}
    try:
        nuevo = _normalize_verb_strict_for_add(data)
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400

    verbos = load_verbs()
    if any((v.get("presente","").lower().strip() == nuevo["presente"]) for v in verbos):
        return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400

    verbos.append(nuevo)
    save_verbs(verbos)
    return jsonify({"ok": True, "msg": "✅ Verbo agregado", "verbo": nuevo})

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json or {}
    if "index" not in data or "verbo" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    idx = int(data["index"])
    verbos = load_verbs()
    if idx < 0 or idx >= len(verbos):
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400

    try:
        edited = _normalize_verb_strict_for_add(data["verbo"])
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400

    verbos[idx] = edited
    save_verbs(verbos)
    return jsonify({"ok": True, "msg": "✏️ Verbo editado", "verbo": edited})

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json or {}
    if "index" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    idx = int(data["index"])
    verbos = load_verbs()
    if idx < 0 or idx >= len(verbos):
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400

    del verbos[idx]
    save_verbs(verbos)
    return jsonify({"ok": True, "msg": "🗑️ Verbo eliminado"})

# ==========================
#   IMPORTAR / EXPORTAR
# ==========================
@app.route("/exportar_verbos", methods=["GET"])
def exportar_verbos():
    data = load_verbs()
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=verbos-export.json"}
    )

@app.route("/importar_verbos", methods=["POST"])
def importar_verbos():
    payload = None
    if request.files.get("file"):
        try:
            payload = json.load(request.files["file"])
        except Exception:
            return jsonify({"ok": False, "msg": "Archivo inválido"}), 400
    else:
        payload = request.json

    if not isinstance(payload, list):
        return jsonify({"ok": False, "msg": "Se espera una lista JSON de verbos"}), 400

    actuales = load_verbs()
    by_base = { v["presente"]: v for v in actuales }

    added, updated = 0, 0
    for item in payload:
        norm = _normalize_verb_input(item)
        key = norm["presente"]
        if key in by_base:
            by_base[key] = norm
            updated += 1
        else:
            by_base[key] = norm
            added += 1

    merged = list(by_base.values())
    save_verbs(merged)
    return jsonify({"ok": True, "msg": f"✅ Importados: {added} nuevos, {updated} actualizados", "total": len(merged)})

# ===================
#   PREGUNTAS VERBOS
# ===================
@app.route("/preguntas", methods=["POST"])
def preguntas():
    data = request.json or {}
    modo = data.get("modo", "simple")
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", "ilimitado")

    verbos = load_verbs()
    if modo in ("simple", "continuous") and tipo != "todos":
        verbos = [v for v in verbos if v.get("categoria") == tipo]
    if not verbos:
        return jsonify([])

    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(verbos) * 3, 60) or 30

    preguntas = []
    modos = ["a","b","c","d","e","f"]

    for i in range(n):
        code = modos[i % 6]
        v = random.choice(verbos)
        v = _autofill_continuous(dict(v))
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
        else:
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

# =========================
#   WH: TRADUCCIÓN & MCQ
# =========================
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

    random.shuffle(templates)
    bank = [{"pregunta": s, "opciones": opts[:], "correcta": i_ok, "respuesta": opts[i_ok]} for (s, opts, i_ok) in templates]

    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(bank), 60)

    for item in bank:
        correct_word = item["opciones"][item["correcta"]]
        random.shuffle(item["opciones"])
        item["correcta"] = item["opciones"].index(correct_word)

    return jsonify(bank[:n])

# ======================
#     ESTADÍSTICAS
# ======================
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
        "tipo": data.get("tipo", "simple"),
        "limitado": bool(data.get("limitado", False)),
        "cantidad": data.get("cantidad", "ilimitado"),
        "correctas": int(data.get("correctas", 0)),
        "incorrectas": int(data.get("incorrectas", 0)),
        "porcentaje": porcentaje,
        "streak_max": int(data.get("streak_max", 0)),
        "duracion_segundos": int(data.get("duracion_segundos", 0)),
        "fecha": datetime.utcnow().isoformat() + "Z"
    }
    stats = load_stats()
    stats.append(registro)
    save_stats(stats)
    return jsonify({"ok": True, "msg": "📊 Resultado guardado", "registro": registro})

@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    usuario = (request.args.get("usuario") or "").strip()
    stats = load_stats()
    if usuario:
        stats = [s for s in stats if s.get("usuario","").lower() == usuario.lower()]
    stats.sort(key=lambda x: x.get("fecha",""), reverse=True)
    return jsonify(stats)

@app.route("/estadisticas_csv", methods=["GET"])
def estadisticas_csv():
    stats = load_stats()
    out = StringIO()
    headers = ["fecha","usuario","tipo","limitado","cantidad","correctas","incorrectas","porcentaje","streak_max","duracion_segundos"]
    out.write(",".join(headers) + "\n")
    for s in stats:
        row = [
            s.get("fecha",""),
            s.get("usuario",""),
            s.get("tipo",""),
            "1" if s.get("limitado") else "0",
            str(s.get("cantidad","")),
            str(s.get("correctas",0)),
            str(s.get("incorrectas",0)),
            str(s.get("porcentaje",0)),
            str(s.get("streak_max",0)),
            str(s.get("duracion_segundos",0)),
        ]
        out.write(",".join(row) + "\n")
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=estadisticas.csv"})

@app.route("/usuarios", methods=["GET"])
def usuarios():
    stats = load_stats()
    names = sorted({
        s.get("usuario","").strip() for s in stats
        if s.get("usuario","").strip() and s.get("usuario","").lower() != "invitado"
    })
    return jsonify(names)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "data_dir": DATA_DIR})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
