from flask import Flask, jsonify, request, render_template, Response
import os, json, random
from datetime import datetime
from io import StringIO
from typing import List, Dict

# --- DB ---
from sqlalchemy import create_engine, text

app = Flask(__name__)

# ==========
#  DATABASE
# ==========
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("Falta la variable de entorno DATABASE_URL (postgresql://...)")

# Neon/PG
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

def init_db():
    """Crea tablas si no existen (idempotente)."""
    ddl = """
    CREATE TABLE IF NOT EXISTS verbos (
        id SERIAL PRIMARY KEY,
        presente TEXT NOT NULL,
        pasado TEXT NOT NULL,
        traduccion TEXT NOT NULL,
        traduccion_pasado TEXT NOT NULL,
        continuo TEXT NOT NULL,
        traduccion_continuo TEXT NOT NULL,
        categoria TEXT NOT NULL CHECK (categoria IN ('regular','irregular'))
    );

    CREATE TABLE IF NOT EXISTS stats (
        id SERIAL PRIMARY KEY,
        usuario TEXT NOT NULL,
        tipo TEXT NOT NULL,
        limitado BOOLEAN NOT NULL,
        cantidad TEXT NOT NULL,
        correctas INT NOT NULL,
        incorrectas INT NOT NULL,
        porcentaje NUMERIC(6,2) NOT NULL,
        streak_max INT NOT NULL,
        duracion_segundos INT NOT NULL,
        fecha TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS portada (
        id INTEGER PRIMARY KEY,
        data_url TEXT,
        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        for stmt in ddl.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))

init_db()

# =======================
#   LENGUAJE & NORMALIZ.
# =======================
def _is_vowel(c): return c.lower() in "aeiou"

def _gerund(base: str) -> str:
    w = (base or "").strip().lower()
    if not w:
        return ""
    if w == "be":
        return "being"
    if w.endswith("ie"):
        return w[:-2] + "ying"
    if w.endswith("e") and len(w) > 2 and w[-2] not in "aeiou":
        if w.endswith("ee"):
            return w + "ing"
        return w[:-1] + "ing"
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
    req_min = ["presente", "pasado", "traduccion", "categoria"]
    if not all(k in data and str(data[k]).strip() for k in req_min):
        raise ValueError("Faltan campos obligatorios (presente, pasado, traducción y categoría).")
    if not data.get("traduccion_pasado"):
        data["traduccion_pasado"] = data.get("traduccion", "")
    return _normalize_verb_input(data)

# ==========
#   VISTAS
# ==========
@app.route("/")
def index():
    return render_template("index.html")

# ================
#   PORTADA API
# ================
@app.route("/portada", methods=["GET"])
def portada_get():
    with engine.connect() as conn:
        r = conn.execute(text("SELECT data_url FROM portada WHERE id=1")).fetchone()
        return jsonify({"ok": True, "data_url": r[0] if r else ""})

@app.route("/portada", methods=["POST"])
def portada_set():
    data = request.json or {}
    data_url = (data.get("data_url") or "").strip()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO portada (id, data_url, updated_at)
            VALUES (1, :d, NOW())
            ON CONFLICT (id) DO UPDATE SET data_url = EXCLUDED.data_url, updated_at = NOW()
        """), {"d": data_url})
    return jsonify({"ok": True})

@app.route("/portada/delete", methods=["POST"])
def portada_del():
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM portada WHERE id=1"))
    return jsonify({"ok": True})

# =================
#   VERBOS (CRUD)
# =================
def _load_verbs() -> List[Dict]:
    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT id, presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria
            FROM verbos ORDER BY presente ASC
        """))
        rows = [dict(r) for r in cur.mappings()]
    # normalizamos para asegurar campos continuo/traduccion_continuo
    return [_autofill_continuous(dict(v)) for v in rows]

def _get_id_by_index(idx: int) -> int:
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT id FROM verbos ORDER BY presente ASC LIMIT 1 OFFSET :off
        """), {"off": idx}).fetchone()
        if not r:
            return -1
        return int(r[0])

@app.route("/obtener_verbos", methods=["GET"])
def obtener_verbos():
    return jsonify(_load_verbs())

@app.route("/agregar_verbo", methods=["POST"])
def agregar_verbo():
    data = request.json or {}
    try:
        nuevo = _normalize_verb_strict_for_add(data)
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400

    # duplicado por 'presente'
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 FROM verbos WHERE LOWER(TRIM(presente)) = :p LIMIT 1"),
                         {"p": nuevo["presente"]}).fetchone()
    if r:
        return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO verbos (presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria)
            VALUES (:presente, :pasado, :traduccion, :traduccion_pasado, :continuo, :traduccion_continuo, :categoria)
        """), nuevo)
    return jsonify({"ok": True, "msg": "✅ Verbo agregado", "verbo": nuevo})

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json or {}
    if "index" not in data or "verbo" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400

    idx = int(data["index"])
    try:
        edited = _normalize_verb_strict_for_add(data["verbo"])
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400

    vid = _get_id_by_index(idx)
    if vid < 0:
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE verbos SET
                presente=:presente, pasado=:pasado, traduccion=:traduccion,
                traduccion_pasado=:traduccion_pasado, continuo=:continuo,
                traduccion_continuo=:traduccion_continuo, categoria=:categoria
            WHERE id=:id
        """), {**edited, "id": vid})
    return jsonify({"ok": True, "msg": "✏️ Verbo editado", "verbo": edited})

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json or {}
    if "index" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400
    idx = int(data["index"])
    vid = _get_id_by_index(idx)
    if vid < 0:
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM verbos WHERE id=:id"), {"id": vid})
    return jsonify({"ok": True, "msg": "🗑️ Verbo eliminado"})

# ==========================
#   IMPORTAR / EXPORTAR
# ==========================
@app.route("/exportar_verbos", methods=["GET"])
def exportar_verbos():
    data = _load_verbs()
    # quitamos 'id'
    for v in data:
        v.pop("id", None)
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=verbos-export.json"}
    )

@app.route("/importar_verbos", methods=["POST"])
def importar_verbos():
    if request.files.get("file"):
        try:
            payload = json.load(request.files["file"])
        except Exception:
            return jsonify({"ok": False, "msg": "Archivo inválido"}), 400
    else:
        payload = request.json

    if not isinstance(payload, list):
        return jsonify({"ok": False, "msg": "Se espera una lista JSON de verbos"}), 400

    added, updated = 0, 0
    with engine.begin() as conn:
        # Cargamos llaves existentes
        cur = conn.execute(text("SELECT id, presente FROM verbos"))
        existing = {r.presente: r.id for r in cur.mappings()}

        for item in payload:
            norm = _normalize_verb_input(item)
            key = norm["presente"]
            if key in existing:
                conn.execute(text("""
                    UPDATE verbos SET
                      pasado=:pasado, traduccion=:traduccion, traduccion_pasado=:traduccion_pasado,
                      continuo=:continuo, traduccion_continuo=:traduccion_continuo, categoria=:categoria
                    WHERE id=:id
                """), {**norm, "id": existing[key]})
                updated += 1
            else:
                conn.execute(text("""
                    INSERT INTO verbos (presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria)
                    VALUES (:presente, :pasado, :traduccion, :traduccion_pasado, :continuo, :traduccion_continuo, :categoria)
                """), norm)
                added += 1

    # total
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM verbos")).scalar_one()

    return jsonify({"ok": True, "msg": f"✅ Importados: {added} nuevos, {updated} actualizados", "total": int(total)})

# ===================
#   PREGUNTAS VERBOS
# ===================
@app.route("/preguntas", methods=["POST"])
def preguntas():
    data = request.json or {}
    modo = data.get("modo", "simple")
    tipo = data.get("tipo", "todos")
    cantidad = data.get("cantidad", "ilimitado")

    verbos = _load_verbs()
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
        "cantidad": str(data.get("cantidad", "ilimitado")),
        "correctas": int(data.get("correctas", 0)),
        "incorrectas": int(data.get("incorrectas", 0)),
        "porcentaje": porcentaje,
        "streak_max": int(data.get("streak_max", 0)),
        "duracion_segundos": int(data.get("duracion_segundos", 0)),
    }
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO stats (usuario, tipo, limitado, cantidad, correctas, incorrectas, porcentaje, streak_max, duracion_segundos, fecha)
            VALUES (:usuario, :tipo, :limitado, :cantidad, :correctas, :incorrectas, :porcentaje, :streak_max, :duracion_segundos, NOW())
        """), registro)
    return jsonify({"ok": True, "msg": "📊 Resultado guardado", "registro": registro})

@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    usuario = (request.args.get("usuario") or "").strip()
    with engine.connect() as conn:
        if usuario:
            cur = conn.execute(text("""
                SELECT * FROM stats WHERE LOWER(usuario)=LOWER(:u) ORDER BY fecha DESC
            """), {"u": usuario})
        else:
            cur = conn.execute(text("SELECT * FROM stats ORDER BY fecha DESC"))
        rows = [dict(r) for r in cur.mappings()]
    # convertir fecha a ISO (string) para el front
    for r in rows:
        if isinstance(r.get("fecha"), datetime):
            r["fecha"] = r["fecha"].isoformat() + "Z"
    return jsonify(rows)

@app.route("/estadisticas_csv", methods=["GET"])
def estadisticas_csv():
    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT fecha, usuario, tipo, limitado, cantidad, correctas, incorrectas, porcentaje, streak_max, duracion_segundos
            FROM stats ORDER BY fecha DESC
        """))
        rows = list(cur)

    out = StringIO()
    headers = ["fecha","usuario","tipo","limitado","cantidad","correctas","incorrectas","porcentaje","streak_max","duracion_segundos"]
    out.write(",".join(headers) + "\n")
    for s in rows:
        row = [
            (s[0].isoformat() + "Z") if isinstance(s[0], datetime) else str(s[0]),
            str(s[1]), str(s[2]), "1" if s[3] else "0", str(s[4]),
            str(s[5]), str(s[6]), str(s[7]), str(s[8]), str(s[9]),
        ]
        out.write(",".join(row) + "\n")

    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=estadisticas.csv"})

@app.route("/usuarios", methods=["GET"])
def usuarios():
    with engine.connect() as conn:
        cur = conn.execute(text("""
            SELECT DISTINCT usuario FROM stats
            WHERE TRIM(usuario) <> '' AND LOWER(usuario) <> 'invitado'
            ORDER BY usuario
        """))
        names = [r[0] for r in cur]
    return jsonify(names)

@app.route("/health", methods=["GET"])
def health():
    # prueba simple contra la DB
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
