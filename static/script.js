// ===== UI =====
const ui = {
  mostrar: (id) => {
    const modal = document.getElementById("resumen");
    if (modal) { modal.classList.add("hidden"); modal.style.display = "none"; }

    document.getElementById("btn-ver-verbos").disabled = (id === "play" || id === "setup");

    ["menu","setup","play","lista","agregar","stats"].forEach(sec => {
      document.getElementById(sec).classList.add("hidden");
    });
    document.getElementById(id).classList.remove("hidden");

    if(id==="setup"){
      ui.irPaso(1);
      document.getElementById("setupTitle").textContent =
        practica.modo==='simple' ? "🧠 Configurar: Simple Past" :
        practica.modo==='continuous' ? "🧠 Configurar: Past Continuous" :
        "🧠 Configurar: WH Questions";
    }
  },
  irPaso: (n) => {
    ["step1","step2","step3"].forEach(s => {
      const el = document.getElementById(s);
      if (el) el.classList.add("hidden");
    });
    const step = document.getElementById(`step${n}`);
    if (step) step.classList.remove("hidden");
  },

  // ==== Usuarios (sidebar) ====
  cargarUsuarios: async () => {
    try{
      const res = await fetch("/usuarios");
      const users = await res.json();
      const ul = document.getElementById("listaUsuarios");
      ul.innerHTML = users.length ? "" : "<li>(Sin usuarios aún)</li>";
      users.forEach(name => {
        const li = document.createElement("li");
        li.textContent = name;
        li.onclick = () => {
          document.querySelectorAll("#listaUsuarios li").forEach(x=>x.classList.remove("active"));
          li.classList.add("active");
          document.getElementById("filtroUsuario").value = name;
          ui.cargarEstadisticas();
        };
        ul.appendChild(li);
      });
    }catch(e){
      console.error(e);
      document.getElementById("listaUsuarios").innerHTML = "<li>Error cargando usuarios</li>";
    }
  },

  // ==== Estadísticas ====
  cargarEstadisticas: async () => {
    try{
      const usuario = document.getElementById("filtroUsuario").value.trim();
      const url = usuario ? `/estadisticas?usuario=${encodeURIComponent(usuario)}` : "/estadisticas";
      const res = await fetch(url);
      const data = await res.json();

      const tabla = document.getElementById("tablaStats");
      if (!data.length) {
        tabla.innerHTML = "<div style='padding:10px'>No hay resultados aún.</div>";
      } else {
        tabla.innerHTML = `
          <table class="tabla">
            <thead>
              <tr><th>Fecha</th><th>Usuario</th><th>Tipo</th><th>Modo</th><th>Correctas</th><th>Incorrectas</th><th>%</th><th>Racha</th><th>Tiempo</th></tr>
            </thead>
            <tbody>
              ${data.map(r => `
                <tr>
                  <td>${new Date(r.fecha).toLocaleString()}</td>
                  <td>${r.usuario}</td>
                  <td>${r.tipo}</td>
                  <td>${r.limitado ? `limitado (${r.cantidad})` : "ilimitado"}</td>
                  <td>${r.correctas}</td>
                  <td>${r.incorrectas}</td>
                  <td>${r.porcentaje}%</td>
                  <td>${r.streak_max}</td>
                  <td>${Math.floor(r.duracion_segundos/60)}m ${r.duracion_segundos%60}s</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }

      const ctx = document.getElementById("chartStats");
      if (window._chart) window._chart.destroy();
      window._chart = new Chart(ctx, {
        type: "bar",
        data: {
          labels: data.map((_, i) => `#${i+1}`),
          datasets: [
            { label: "Correctas", data: data.map(r => r.correctas) },
            { label: "Incorrectas", data: data.map(r => r.incorrectas) }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "top" } },
          scales: { y: { beginAtZero: true, ticks: { precision:0 } } }
        }
      });
    }catch(e){
      console.error(e);
      document.getElementById("tablaStats").innerHTML = "<div style='padding:10px'>Error cargando estadísticas.</div>";
    }
  }
};

// ===== VERBOS =====
const datos = {
  verbos: [],
  listarVerbos: async () => {
    const ul = document.getElementById("listaVerbos");
    ul.innerHTML = "<li>Cargando...</li>";
    const res = await fetch("/obtener_verbos");
    const arr = await res.json();
    datos.verbos = arr;
    if (!arr.length) {
      ul.innerHTML = "<li>No hay verbos guardados aún.</li>";
      return;
    }
    ul.innerHTML = "";
    arr.forEach((v, idx) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span class="badge ${v.categoria}">${v.categoria}</span>
        <span class="verb">
          ${v.presente} – ${v.pasado} – ${v.continuo} –
          ${v.traduccion} / ${v.traduccion_pasado} / ${v.traduccion_continuo}
        </span>
        <button class="mini" type="button" data-idx="${idx}" data-action="edit">✏️</button>
        <button class="mini danger" type="button" data-idx="${idx}" data-action="del">🗑️</button>
      `;
      ul.appendChild(li);
    });

    ul.querySelectorAll("button[data-action]").forEach(btn=>{
      btn.addEventListener("click", async (e)=>{
        const idx = Number(e.currentTarget.dataset.idx);
        const action = e.currentTarget.dataset.action;
        if (action === "edit") {
          const v = datos.verbos[idx];
          const nuevo = prompt(
            "Editar: presente,pasado,traducción,trad. pasado,continuo,trad. continuo,categoria",
            `${v.presente},${v.pasado},${v.traduccion},${v.traduccion_pasado},${v.continuo},${v.traduccion_continuo},${v.categoria}`
          );
          if (!nuevo) return;
          const [presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria] =
            nuevo.split(",").map(s => (s||"").trim());
          const res = await fetch("/editar_verbo", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({index: idx, verbo: {presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria}})
          });
          const data = await res.json();
          if (data.ok) datos.listarVerbos();
          else alert(data.msg || "Error al editar");
        } else {
          if (!confirm("¿Eliminar verbo?")) return;
          const res = await fetch("/eliminar_verbo", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({index: idx})
          });
          const data = await res.json();
          if (data.ok) datos.listarVerbos();
          else alert(data.msg || "Error al eliminar");
        }
      });
    });
  },
  agregar: async () => {
    const presente = document.getElementById("nuevoPresente").value.trim();
    const pasado = document.getElementById("nuevoPasado").value.trim();
    const traduccion = document.getElementById("nuevaTraduccion").value.trim();
    const traduccion_pasado = document.getElementById("nuevaTraduccionPasado").value.trim();
    const continuo = document.getElementById("nuevoContinuo").value.trim();
    const traduccion_continuo = document.getElementById("nuevaTraduccionContinuo").value.trim();
    const categoria = document.getElementById("nuevaCategoria").value;
    if (!presente || !pasado || !traduccion || !traduccion_pasado || !continuo || !traduccion_continuo) {
      document.getElementById("mensajeAgregar").textContent = "⚠️ Todos los campos son obligatorios.";
      return;
    }
    const res = await fetch("/agregar_verbo", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({presente, pasado, traduccion, traduccion_pasado, continuo, traduccion_continuo, categoria})
    });
    const data = await res.json();
    document.getElementById("mensajeAgregar").textContent = data.msg || (data.ok ? "Guardado" : "Error");
    if (data.ok) {
      ["nuevoPresente","nuevoPasado","nuevaTraduccion","nuevaTraduccionPasado","nuevoContinuo","nuevaTraduccionContinuo"]
        .forEach(id => document.getElementById(id).value = "");
    }
  }
};

// ===== PRÁCTICA =====
const practica = {
  modo: "simple",      // simple | continuous | wh
  usuario: "invitado",
  tipo: "todos",
  cantidad: 10,
  ilimitado: false,

  preguntas: [],
  idx: 0,
  correctas: 0,
  incorrectas: 0,
  streak: 0,
  streakMax: 0,
  startTs: 0,
  timerInt: null,

  setModo(m){ this.modo = m; },
  usarInvitado(){ this.usuario = "invitado"; },
  setUsuario(){ this.usuario = (document.getElementById("nombreUsuario").value.trim() || "invitado"); },
  setTipo(t){ this.tipo = t; },
  setCantidad(n){
    this.cantidad = n; this.ilimitado = false;
    document.getElementById("cantidadActual").textContent = `Selección: ${n}`;
    document.getElementById("pillLimite").textContent = `Límite: ${n}`;
  },
  setIlimitado(){
    this.ilimitado = true;
    document.getElementById("cantidadActual").textContent = "Selección: Ilimitado";
    document.getElementById("pillLimite").textContent = "Límite: Ilimitado";
  },

  async iniciar(){
    const modal = document.getElementById("resumen");
    if (modal) { modal.classList.add("hidden"); modal.style.display = "none"; }

    let arr = [];
    try{
      if (this.modo === "wh") {
        const res = await fetch("/preguntas_wh", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({
            cantidad: this.ilimitado ? "ilimitado" : this.cantidad
          })
        });
        arr = await res.json();
      } else {
        const res = await fetch("/preguntas", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({
            modo: this.modo,
            tipo: this.tipo,
            cantidad: this.ilimitado ? "ilimitado" : this.cantidad
          })
        });
        arr = await res.json();
      }
    }catch(e){
      alert("No se pudieron cargar las preguntas. Intenta de nuevo.");
      return;
    }

    if (!Array.isArray(arr) || arr.length === 0){
      alert("No hay preguntas para ese modo/filtro. Agrega verbos o cambia el filtro.");
      ui.mostrar("setup"); ui.irPaso(this.modo==='wh'?1:2);
      return;
    }

    this.preguntas = arr;
    this.idx = 0; this.correctas = 0; this.incorrectas = 0;
    this.streak = 0; this.streakMax = 0;
    this.startTs = Date.now();
    this._startTimer();

    document.getElementById("pillUsuario").textContent = `👤 ${this.usuario}`;
    document.getElementById("pillModo").textContent = `Modo: ${this.modo}`;
    document.getElementById("pillTipo").textContent = this.modo==='wh' ? "Tipo: —" : `Tipo: ${this.tipo}`;
    document.getElementById("pillLimite").textContent = `Límite: ${this.ilimitado ? "Ilimitado" : this.cantidad}`;
    document.getElementById("pillContador").textContent = `0/${this.ilimitado ? "∞" : this.preguntas.length}`;
    document.getElementById("pillStreak").textContent = `🔥 racha: 0`;
    document.getElementById("resultado").textContent = "";

    ui.mostrar("play");
    this._pintarPregunta();
  },

  _pintarPregunta(){
    if (!this.ilimitado && this.idx >= this.preguntas.length) {
      this.finalizar();
      return;
    }
    const q = this.preguntas[this.idx % this.preguntas.length];
    document.getElementById("pregunta").textContent = q.pregunta;
    const r = document.getElementById("respuesta");
    r.value=""; r.focus();
    document.getElementById("pillContador").textContent =
      `${Math.min(this.idx, this.preguntas.length)}/${this.ilimitado ? "∞" : this.preguntas.length}`;
  },

  verificar(){
    const norm = (s) => (s ?? "").toString().trim().toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "");

    const q = this.preguntas[this.idx % this.preguntas.length];
    const resp = norm(document.getElementById("respuesta").value || "");
    const expected = q.respuesta;

    let ok = false;
    if (Array.isArray(expected)) ok = expected.some(ans => norm(ans) === resp);
    else ok = norm(expected) === resp;

    const out = document.getElementById("resultado");
    if(ok){
      this.correctas++; this.streak++; this.streakMax = Math.max(this.streakMax, this.streak);
      out.textContent = "✅ ¡Correcto!";
      if (this.streak && this.streak % 5 === 0) out.textContent += ` 🔥 Racha de ${this.streak}!`;
    }else{
      this.incorrectas++; this.streak = 0;
      out.textContent = `❌ Incorrecto. Era: ${Array.isArray(expected) ? expected[0] : expected}`;
    }
    this.idx++;
    this._pintarPregunta();
  },

  finalizar(){
    this._stopTimer();
    const secs = Math.floor((Date.now() - this.startTs)/1000);
    const total = this.correctas + this.incorrectas;
    const porcentaje = total ? ((this.correctas/total)*100).toFixed(2) : "0.00";

    let modoText = this.modo;
    let limiteText = this.ilimitado ? "ilimitado" : this.cantidad;

    fetch("/guardar_resultado", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        usuario: this.usuario,
        tipo: this.modo,                  // guardamos modo aquí
        limitado: !this.ilimitado,
        cantidad: limiteText,
        correctas: this.correctas,
        incorrectas: this.incorrectas,
        streak_max: this.streakMax,
        duracion_segundos: secs
      })
    });

    document.getElementById("rUsuario").textContent = this.usuario;
    document.getElementById("rModo").textContent = modoText;
    document.getElementById("rTipo").textContent = (this.modo==='wh' ? "—" : this.tipo);
    document.getElementById("rOk").textContent = this.correctas;
    document.getElementById("rBad").textContent = this.incorrectas;
    document.getElementById("rStreak").textContent = this.streakMax;
    document.getElementById("rTiempo").textContent = `${Math.floor(secs/60)}m ${secs%60}s (${porcentaje}%)`;

    const modal = document.getElementById("resumen");
    modal.classList.remove("hidden");
    modal.style.display = "flex";

    document.getElementById("btn-ver-verbos").disabled = false;
  },

  _startTimer(){
    const pill = document.getElementById("pillTimer");
    if (this.timerInt) clearInterval(this.timerInt);
    this.timerInt = setInterval(()=>{
      const secs = Math.floor((Date.now() - this.startTs)/1000);
      const mm = String(Math.floor(secs/60)).padStart(2,"0");
      const ss = String(secs%60).padStart(2,"0");
      pill.textContent = `⏱ ${mm}:${ss}`;
    }, 1000);
  },
  _stopTimer(){ if (this.timerInt) clearInterval(this.timerInt); this.timerInt = null; }
};

// ===== Dark mode =====
(function initDarkMode(){
  const btn = document.getElementById("btn-dark");
  const apply = (dark) => {
    if (dark) document.body.classList.add("dark");
    else document.body.classList.remove("dark");
    localStorage.setItem("dark", dark ? "1" : "0");
  };
  const saved = localStorage.getItem("dark") === "1";
  apply(saved);
  btn.addEventListener("click", () => apply(!document.body.classList.contains("dark")));
})();

// Inicio
ui.mostrar("menu");
