from flask import Flask, jsonify, request, render_template, Response
import json, os, random
from datetime import datetime, timezone
from io import StringIO

# === Postgres (psycopg 3 + pool) ===
from psycopg import connect
from psycopg_pool import ConnectionPool

app = Flask(__name__)

# =======================
#   CONEXIÓN A POSTGRES
# =======================
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("Falta la variable de entorno DATABASE_URL")

pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=1,
    max_size=5,
    num_workers=2,
    timeout=30
)

def run_query(sql, params=None, fetch="all"):
    """Helper para SELECT/INSERT/UPDATE con pool."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            if fetch == "one":
                r = cur.fetchone()
                return r
            if fetch == "all":
                return cur.fetchall()
            return None

def run_exec(sql, params=None):
    """Helper sin fetch (INSERT/UPDATE/DELETE)."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())

# Auto-create defensivo por si no corriste el SQL (harmless si ya existen)
DDL = """
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_verbos_presente ON verbos (presente);

CREATE TABLE IF NOT EXISTS stats (
  id SERIAL PRIMARY KEY,
  usuario TEXT NOT NULL,
  tipo TEXT NOT NULL,
  limitado BOOLEAN NOT NULL,
  cantidad TEXT NOT NULL,
  correctas INT NOT NULL,
  incorrectas INT NOT NULL,
  porcentaje NUMERIC(5,2) NOT NULL,
  streak_max INT NOT NULL,
  duracion_segundos INT NOT NULL,
  fecha TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stats_usuario ON stats (LOWER(usuario));
CREATE INDEX IF NOT EXISTS idx_stats_fecha   ON stats (fecha DESC);
"""
def ensure_schema():
    # Ejecuta múltiples sentencias
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)

ensure_schema()

# =======================
#   NORMALIZADORES
# =======================
def _is_vowel(c): return c.lower() in "aeiou"

def _gerund(base: str) -> str:
    w = (base or "").strip().lower()
    if not w: return ""
    if w == "be": return "being"
    if w.endswith("ie"): return w[:-2] + "ying"
    if w.endswith("e") and len(w) > 2 and w[-2] not in "aeiou":
        if w.endswith("ee"): return w + "ing"
        return w[:-1] + "ing"
    if len(w) >= 3 and (w[-1] not in "aeiou") and (w[-2] in "aeiou") and (w[-3] not in "aeiou"):
        if w[-1] not in "wxy": return w + w[-1] + "ing"
    return w + "ing"

def _autofill_cont(v: dict) -> dict:
    base = v.get("presente","")
    v.setdefault("traduccion","")
    v.setdefault("traduccion_pasado", v["traduccion"])
    v.setdefault("continuo","")
    v.setdefault("traduccion_continuo","")
    if not v["continuo"]:
        g = _gerund(base)
        v["continuo"] = f"was / were {g}" if g else ""
    if not v["traduccion_continuo"]:
        v["traduccion_continuo"] = v.get("traduccion_pasado") or v.get("traduccion") or ""
    return v

def _normalize_input(v: dict) -> dict:
    presente = (v.get("presente") or v.get("base") or "").strip().lower()
    pasado = (v.get("pasado") or v.get("past") or "").strip().lower()
    traduccion = (v.get("traduccion") or v.get("traducción") or "").strip().lower()
    traduccion_pasado = (v.get("traduccion_pasado") or v.get("traducción_pasado") or "").strip().lower()
    continuo = (v.get("continuo") or v.get("past_continuous") or "").strip().lower()
    traduccion_continuo = (v.get("traduccion_continuo") or v.get("traducción_continuo") or "").strip().lower()
    categoria = (v.get("categoria") or "regular").strip().lower()
    if categoria not in ("regular","irregular"):
        categoria = "regular"

    out = {
        "presente": presente,
        "pasado": pasado,
        "traduccion": traduccion,
        "traduccion_pasado": traduccion_pasado or traduccion,
        "continuo": continuo,
        "traduccion_continuo": traduccion_continuo,
        "categoria": categoria
    }
    return _autofill_cont(out)

# =======================
#        VISTAS
# =======================
@app.route("/")
def index():
    return render_template("index.html")

# =======================
#        VERBOS
# =======================
@app.route("/obtener_verbos", methods=["GET"])
def obtener_verbos():
    rows = run_query(
        "SELECT id, presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria "
        "FROM verbos ORDER BY id ASC"
    )
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "presente": r[1],
            "pasado": r[2],
            "traduccion": r[3],
            "traduccion_pasado": r[4],
            "continuo": r[5],
            "traduccion_continuo": r[6],
            "categoria": r[7],
        })
    return jsonify(out)

@app.route("/agregar_verbo", methods=["POST"])
def agregar_verbo():
    data = request.json or {}
    try:
        v = _normalize_input(data)
        if not v["presente"] or not v["pasado"] or not v["traduccion"]:
            return jsonify({"ok": False, "msg": "Faltan campos obligatorios"}), 400
        # insert
        run_exec(
            "INSERT INTO verbos (presente,pasado,traduccion,traduccion_pasado,continuo,traduccion_continuo,categoria) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (v["presente"], v["pasado"], v["traduccion"], v["traduccion_pasado"], v["continuo"], v["traduccion_continuo"], v["categoria"])
        )
        return jsonify({"ok": True, "msg": "✅ Verbo agregado", "verbo": v})
    except Exception as e:
        msg = str(e)
        if "idx_verbos_presente" in msg or "duplicate" in msg.lower():
            return jsonify({"ok": False, "msg": "El verbo ya existe"}), 400
        return jsonify({"ok": False, "msg": "Error al agregar"}), 500

def _id_by_index(idx: int) -> int | None:
    r = run_query("SELECT id FROM verbos ORDER BY id ASC", fetch="all")
    if 0 <= idx < len(r):
        return r[idx][0]
    return None

@app.route("/editar_verbo", methods=["POST"])
def editar_verbo():
    data = request.json or {}
    if "index" not in data or "verbo" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400
    v = _normalize_input(data["verbo"])
    vid = _id_by_index(int(data["index"]))
    if vid is None:
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400
    try:
        run_exec(
            "UPDATE verbos SET presente=%s, pasado=%s, traduccion=%s, traduccion_pasado=%s, "
            "continuo=%s, traduccion_continuo=%s, categoria=%s WHERE id=%s",
            (v["presente"], v["pasado"], v["traduccion"], v["traduccion_pasado"],
             v["continuo"], v["traduccion_continuo"], v["categoria"], vid)
        )
        return jsonify({"ok": True, "msg": "✏️ Verbo editado", "verbo": v})
    except Exception:
        return jsonify({"ok": False, "msg": "Error al editar"}), 500

@app.route("/eliminar_verbo", methods=["POST"])
def eliminar_verbo():
    data = request.json or {}
    if "index" not in data:
        return jsonify({"ok": False, "msg": "Datos inválidos"}), 400
    vid = _id_by_index(int(data["index"]))
    if vid is None:
        return jsonify({"ok": False, "msg": "Índice inválido"}), 400
    try:
        run_exec("DELETE FROM verbos WHERE id=%s", (vid,))
        return jsonify({"ok": True, "msg": "🗑️ Verbo eliminado"})
    except Exception:
        return jsonify({"ok": False, "msg": "Error al eliminar"}), 500

# ===== IMPORT/EXPORT =====
@app.route("/exportar_verbos", methods=["GET"])
def exportar_verbos():
    rows = run_query(
        "SELECT presente,pasado,traduccion,traduccion_pasado,continuo,traduccion_continuo,categoria "
        "FROM verbos ORDER BY id ASC"
    )
    data = []
    for r in rows:
        data.append({
            "presente": r[0],
            "pasado": r[1],
            "traduccion": r[2],
            "traduccion_pasado": r[3],
            "continuo": r[4],
            "traduccion_continuo": r[5],
            "categoria": r[6],
        })
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition":"attachment; filename=verbos-export.json"}
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
        return jsonify({"ok": False, "msg": "Se espera una lista JSON"}), 400

    added, updated = 0, 0
    for item in payload:
        v = _normalize_input(item)
        row = run_query("SELECT id FROM verbos WHERE presente=%s", (v["presente"],), fetch="one")
        if row:
            run_exec(
                "UPDATE verbos SET pasado=%s,traduccion=%s,traduccion_pasado=%s,continuo=%s,traduccion_continuo=%s,categoria=%s "
                "WHERE id=%s",
                (v["pasado"], v["traduccion"], v["traduccion_pasado"], v["continuo"], v["traduccion_continuo"], v["categoria"], row[0])
            )
            updated += 1
        else:
            run_exec(
                "INSERT INTO verbos (presente,pasado,traduccion,traduccion_pasado,continuo,traduccion_continuo,categoria) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (v["presente"], v["pasado"], v["traduccion"], v["traduccion_pasado"], v["continuo"], v["traduccion_continuo"], v["categoria"])
            )
            added += 1
    total = run_query("SELECT COUNT(*) FROM verbos", fetch="one")[0]
    return jsonify({"ok": True, "msg": f"✅ Importados: {added} nuevos, {updated} actualizados", "total": total})

# =======================
#      PREGUNTAS
# =======================
@app.route("/preguntas", methods=["POST"])
def preguntas():
    data = request.json or {}
    modo = data.get("modo","simple")          # simple | continuous
    tipo = data.get("tipo","todos")           # regular | irregular | todos
    cantidad = data.get("cantidad","ilimitado")

    where = []
    params = []
    if tipo in ("regular","irregular"):
        where.append("categoria=%s")
        params.append(tipo)
    sql = "SELECT presente,pasado,traduccion,traduccion_pasado,continuo,traduccion_continuo FROM verbos"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id ASC"
    rows = run_query(sql, tuple(params))

    if not rows:
        return jsonify([])

    # cuántas preguntas
    if isinstance(cantidad, int):
        n = max(1, min(int(cantidad), 200))
    else:
        n = min(len(rows) * 3, 60) or 30

    preguntas = []
    modos = ["a","b","c","d","e","f"]
    for i in range(n):
        code = modos[i % 6]
        r = random.choice(rows)
        base, past, t_es, t_es_past, cont, t_es_cont = r
        # fallback continuo
        if not cont:
            cont = f"was / were {_gerund(base)}"
        if not t_es_cont:
            t_es_cont = t_es_past or t_es

        if modo == "simple":
            if code == "a":
                preguntas.append({"pregunta": f"¿Cuál es el pasado de '{base}'?", "respuesta": past})
            elif code == "b":
                preguntas.append({"pregunta": f"¿Cuál es el presente de '{past}'?", "respuesta": base})
            elif code == "c":
                preguntas.append({"pregunta": f"¿Cómo se traduce '{base}' al español?", "respuesta": t_es})
            elif code == "d":
                preguntas.append({"pregunta": f"¿Cómo se traduce el pasado '{past}' al español?", "respuesta": t_es_past})
            elif code == "e":
                preguntas.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": base})
            else:
                preguntas.append({"pregunta": f"En inglés (pasado), ¿cómo se dice '{t_es_past}'?", "respuesta": past})
        else:
            if code == "a":
                preguntas.append({"pregunta": f"¿Cuál es el pasado continuo de '{base}'?", "respuesta": cont})
            elif code == "b":
                preguntas.append({"pregunta": f"¿Cuál es el presente del continuo '{cont}'?", "respuesta": base})
            elif code == "c":
                preguntas.append({"pregunta": f"¿Cómo se traduce '{base}' al español?", "respuesta": t_es})
            elif code == "d":
                preguntas.append({"pregunta": f"¿Cómo se traduce el pasado continuo '{cont}' al español?", "respuesta": t_es_cont})
            elif code == "e":
                preguntas.append({"pregunta": f"En inglés (presente), ¿cómo se dice '{t_es}'?", "respuesta": base})
            else:
                preguntas.append({"pregunta": f"En inglés (pasado continuo), ¿cómo se dice '{t_es_cont}'?", "respuesta": cont})

    return jsonify(preguntas)

# ===== WH =====
@app.route("/preguntas_wh", methods=["POST"])
def preguntas_wh():
    data = request.json or {}
    cantidad = data.get("cantidad","ilimitado")
    bank = [
        {"en":"who","es":"quién"},{"en":"what","es":"qué"},{"en":"when","es":"cuándo"},
        {"en":"where","es":"dónde"},{"en":"why","es":"por qué"},{"en":"how","es":"cómo"},
        {"en":"which","es":"cuál"},{"en":"whose","es":"de quién"},{"en":"how many","es":"cuántos"},
        {"en":"how much","es":"cuánto"}
    ]
    n = max(1, min(int(cantidad), 200)) if isinstance(cantidad,int) else min(len(bank)*3,60)
    out = []
    for i in range(n):
        it = random.choice(bank)
        if i % 2 == 0:
            out.append({"pregunta": f"Traduce al español: '{it['en']}'", "respuesta": it["es"]})
        else:
            out.append({"pregunta": f"Traduce al inglés: '{it['es']}'", "respuesta": it["en"]})
    return jsonify(out)

@app.route("/preguntas_wh_oraciones", methods=["POST"])
def preguntas_wh_oraciones():
    cantidad = request.json.get("cantidad","ilimitado") if request.json else "ilimitado"
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
    n = max(1, min(int(cantidad), 200)) if isinstance(cantidad,int) else min(len(bank),60)
    for item in bank:
        correct = item["opciones"][item["correcta"]]
        random.shuffle(item["opciones"])
        item["correcta"] = item["opciones"].index(correct)
    return jsonify(bank[:n])

# =======================
#      ESTADÍSTICAS
# =======================
@app.route("/guardar_resultado", methods=["POST"])
def guardar_resultado():
    d = request.json or {}
    req = ["usuario","tipo","limitado","correctas","incorrectas","duracion_segundos"]
    if not all(k in d for k in req):
        return jsonify({"ok": False, "msg": "Datos incompletos"}), 400
    total = int(d["correctas"]) + int(d["incorrectas"])
    porcentaje = round((int(d["correctas"])/total)*100, 2) if total>0 else 0.0
    run_exec(
        "INSERT INTO stats (usuario,tipo,limitado,cantidad,correctas,incorrectas,porcentaje,streak_max,duracion_segundos,fecha) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            (d.get("usuario") or "invitado").strip(),
            d.get("tipo","simple"),
            bool(d.get("limitado", False)),
            str(d.get("cantidad","ilimitado")),
            int(d.get("correctas",0)),
            int(d.get("incorrectas",0)),
            porcentaje,
            int(d.get("streak_max",0)),
            int(d.get("duracion_segundos",0)),
            datetime.now(timezone.utc)
        )
    )
    return jsonify({"ok": True, "msg": "📊 Resultado guardado"})

@app.route("/estadisticas", methods=["GET"])
def estadisticas():
    usuario = (request.args.get("usuario") or "").strip()
    if usuario:
        rows = run_query(
            "SELECT fecha,usuario,tipo,limitado,cantidad,correctas,incorrectas,porcentaje,streak_max,duracion_segundos "
            "FROM stats WHERE LOWER(usuario)=LOWER(%s) ORDER BY fecha DESC",
            (usuario,)
        )
    else:
        rows = run_query(
            "SELECT fecha,usuario,tipo,limitado,cantidad,correctas,incorrectas,porcentaje,streak_max,duracion_segundos "
            "FROM stats ORDER BY fecha DESC"
        )
    out = []
    for r in rows:
        out.append({
            "fecha": r[0].isoformat(),
            "usuario": r[1],
            "tipo": r[2],
            "limitado": r[3],
            "cantidad": r[4],
            "correctas": r[5],
            "incorrectas": r[6],
            "porcentaje": float(r[7]),
            "streak_max": r[8],
            "duracion_segundos": r[9]
        })
    return jsonify(out)

@app.route("/estadisticas_csv", methods=["GET"])
def estadisticas_csv():
    rows = run_query(
        "SELECT fecha,usuario,tipo,limitado,cantidad,correctas,incorrectas,porcentaje,streak_max,duracion_segundos "
        "FROM stats ORDER BY fecha DESC"
    )
    out = StringIO()
    headers = ["fecha","usuario","tipo","limitado","cantidad","correctas","incorrectas","porcentaje","streak_max","duracion_segundos"]
    out.write(",".join(headers) + "\n")
    for r in rows:
        row = [
            r[0].isoformat(), r[1], r[2],
            "1" if r[3] else "0",
            str(r[4]), str(r[5]), str(r[6]),
            str(float(r[7])), str(r[8]), str(r[9])
        ]
        out.write(",".join(row) + "\n")
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=estadisticas.csv"})

@app.route("/usuarios", methods=["GET"])
def usuarios():
    rows = run_query("SELECT DISTINCT usuario FROM stats WHERE usuario <> '' AND LOWER(usuario) <> 'invitado' ORDER BY 1")
    return jsonify([r[0] for r in rows])

@app.route("/health", methods=["GET"])
def health():
    # prueba simple a DB
    try:
        _ = run_query("SELECT 1", fetch="one")
        ok = True
    except Exception:
        ok = False
    return jsonify({"ok": ok})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
