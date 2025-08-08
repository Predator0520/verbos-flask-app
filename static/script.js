// ===== UI =====
const ui = {
  mostrar: (id) => {
    // Oculta modal de resumen por si quedó abierto de una sesión anterior
    const modal = document.getElementById("resumen");
    if (modal) modal.classList.add("hidden");

    // Deshabilitar Ver Verbos durante setup o juego
    document.getElementById("btn-ver-verbos").disabled = (id === "play" || id === "setup");

    // Mostrar sección
    ["menu","setup","play","lista","agregar","stats"].forEach(sec => {
      document.getElementById(sec).classList.add("hidden");
    });
    document.getElementById(id).classList.remove("hidden");

    // Reiniciar wizard al entrar a setup
    if(id==="setup") ui.irPaso(1);
  },
  irPaso: (n) => {
    ["step1","step2","step3"].forEach(s => {
      const el = document.getElementById(s);
      if (el) el.classList.add("hidden");
    });
    const step = document.getElementById(`step${n}`);
    if (step) step.classList.remove("hidden");
  },
  cargarEstadisticas: async () => {
    try{
      const usuario = document.getElementById("filtroUsuario").value.trim();
      const url = usuario ? `/estadisticas?usuario=${encodeURIComponent(usuario)}` : "/estadisticas";
      const res = await fetch(url);
      const data = await res.json();

      const tabla = document.getElementById("tablaStats");
      if (!data.length) {
        tabla.innerHTML = "<p>No hay resultados aún.</p>";
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
        options: { responsive: true, maintainAspectRatio: false }
      });
    }catch(e){
      document.getElementById("tablaStats").innerHTML = "<p>Error cargando estadísticas.</p>";
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
        <span class="verb">${v.presente} – ${v.pasado} – ${v.traduccion}</span>
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
          const nuevo = prompt("Editar: presente,pasado,traducción,categoria", `${v.presente},${v.pasado},${v.traduccion},${v.categoria}`);
          if (!nuevo) return;
          const [presente, pasado, traduccion, categoria] = nuevo.split(",").map(s => (s||"").trim());
          const res = await fetch("/editar_verbo", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({index: idx, verbo: {presente, pasado, traduccion, categoria}})
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
    const categoria = document.getElementById("nuevaCategoria").value;
    if (!presente || !pasado || !traduccion) {
      document.getElementById("mensajeAgregar").textContent = "⚠️ Todos los campos son obligatorios.";
      return;
    }
    const res = await fetch("/agregar_verbo", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({presente, pasado, traduccion, categoria})
    });
    const data = await res.json();
    document.getElementById("mensajeAgregar").textContent = data.msg || (data.ok ? "Guardado" : "Error");
    if (data.ok) {
      document.getElementById("nuevoPresente").value = "";
      document.getElementById("nuevoPasado").value = "";
      document.getElementById("nuevaTraduccion").value = "";
    }
  }
};

// ===== PRÁCTICA =====
const practica = {
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

  usarInvitado(){ this.usuario = "invitado"; },
  setUsuario(){ this.usuario = (document.getElementById("nombreUsuario").value.trim() || "invitado"); },
  setTipo(t){ this.tipo = t; document.getElementById("pillTipo").textContent = `Tipo: ${t}`; },
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
    // Oculta el modal SIEMPRE al iniciar una nueva práctica
    const modal = document.getElementById("resumen");
    if (modal) modal.classList.add("hidden");

    let arr = [];
    try{
      const res = await fetch("/preguntas", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({
          tipo: this.tipo,
          cantidad: this.ilimitado ? "ilimitado" : this.cantidad
        })
      });
      arr = await res.json();
    }catch(e){
      alert("No se pudieron cargar las preguntas. Intenta de nuevo.");
      return;
    }

    if (!Array.isArray(arr) || arr.length === 0){
      alert("No hay preguntas para ese tipo de verbo. Agrega verbos o cambia el filtro.");
      ui.mostrar("setup"); ui.irPaso(2);
      return;
    }

    this.preguntas = arr;
    this.idx = 0; this.correctas = 0; this.incorrectas = 0;
    this.streak = 0; this.streakMax = 0;
    this.startTs = Date.now();
    this._startTimer();

    document.getElementById("pillUsuario").textContent = `👤 ${this.usuario}`;
    document.getElementById("pillTipo").textContent = `Tipo: ${this.tipo}`;
    document.getElementById("pillLimite").textContent = `Límite: ${this.ilimitado ? "Ilimitado" : this.cantidad}`;
    document.getElementById("pillContador").textContent = `0/${this.ilimitado ? "∞" : this.preguntas.length}`;
    document.getElementById("pillStreak").textContent = `🔥 racha: 0`;
    document.getElementById("resultado").textContent = "";

    ui.mostrar("play");
    this._pintarPregunta();
  },

  _pintarPregunta(){
    if (!this.ilimitado && this.idx >= this.preguntas.length) {
      // Ya no mostramos resumen aquí: sólo si termina por completar todas.
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
    const q = this.preguntas[this.idx % this.preguntas.length];
    const resp = (document.getElementById("respuesta").value || "").trim().toLowerCase();
    const ok = resp === q.respuesta.toLowerCase();
    const out = document.getElementById("resultado");

    if(ok){
      this.correctas++; this.streak++; this.streakMax = Math.max(this.streakMax, this.streak);
      out.textContent = "✅ ¡Correcto!";
      if (this.streak && this.streak % 5 === 0) out.textContent += ` 🔥 Racha de ${this.streak}!`;
    }else{
      this.incorrectas++; this.streak = 0;
      out.textContent = `❌ Incorrecto. Era: ${q.respuesta}`;
    }
    this.idx++;
    this._pintarPregunta();
  },

  finalizar(){
    this._stopTimer();
    const secs = Math.floor((Date.now() - this.startTs)/1000);
    const total = this.correctas + this.incorrectas;
    const porcentaje = total ? ((this.correctas/total)*100).toFixed(2) : "0.00";

    // Modo (fácil/medio/difícil)
    let modo = "fácil";
    if (this.ilimitado || (!this.ilimitado && this.cantidad > 45)) modo = "difícil";
    else if (!this.ilimitado && (this.cantidad === 30 || this.cantidad === 40)) modo = "medio";

    // Guardar (async)
    fetch("/guardar_resultado", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        usuario: this.usuario,
        tipo: this.tipo,
        limitado: !this.ilimitado,
        cantidad: this.ilimitado ? "ilimitado" : this.cantidad,
        correctas: this.correctas,
        incorrectas: this.incorrectas,
        streak_max: this.streakMax,
        duracion_segundos: secs
      })
    });

    // Completar resumen
    document.getElementById("rUsuario").textContent = this.usuario;
    document.getElementById("rTipo").textContent = this.tipo;
    document.getElementById("rModo").textContent = modo;
    document.getElementById("rOk").textContent = this.correctas;
    document.getElementById("rBad").textContent = this.incorrectas;
    document.getElementById("rStreak").textContent = this.streakMax;
    document.getElementById("rTiempo").textContent = `${Math.floor(secs/60)}m ${secs%60}s (${porcentaje}%)`;

    // Mostrar modal SÓLO ahora
    document.getElementById("resumen").classList.remove("hidden");

    // Permitir ver verbos otra vez
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

// ===== Modo oscuro persistente =====
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
