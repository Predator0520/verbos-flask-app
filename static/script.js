// ===== Estado global =====
const ui = {
  mostrar: (id) => {
    // Si entras a práctica, oculta/inhabilita Ver Verbos
    document.getElementById("btn-ver-verbos").disabled = (id === "play" || id === "setup");
    ["menu","setup","play","lista","agregar","stats"].forEach(sec => {
      document.getElementById(sec).classList.add("hidden");
    });
    document.getElementById(id).classList.remove("hidden");
  },
  cargarEstadisticas: async () => {
    const usuario = document.getElementById("filtroUsuario").value.trim();
    const url = usuario ? `/estadisticas?usuario=${encodeURIComponent(usuario)}` : "/estadisticas";
    const res = await fetch(url);
    const data = await res.json();

    // tabla simple
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

    // gráfico: correctas vs incorrectas por sesión
    const ctx = document.getElementById("chartStats");
    if (window._chart) window._chart.destroy();
    window._chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((r, i) => `#${i+1}`),
        datasets: [
          { label: "Correctas", data: data.map(r => r.correctas) },
          { label: "Incorrectas", data: data.map(r => r.incorrectas) }
        ]
      },
      options: { responsive: true, maintainAspectRatio: false }
    });
  }
};

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
        <button class="mini" onclick="datos.editar(${idx})">✏️</button>
        <button class="mini danger" onclick="datos.eliminar(${idx})">🗑️</button>
      `;
      ul.appendChild(li);
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
      datos.listarVerbos();
    }
  },
  editar: async (index) => {
    const v = datos.verbos[index];
    const nuevo = prompt("Editar: presente,pasado,traducción,categoria", `${v.presente},${v.pasado},${v.traduccion},${v.categoria}`);
    if (!nuevo) return;
    const [presente, pasado, traduccion, categoria] = nuevo.split(",").map(s => s.trim());
    const res = await fetch("/editar_verbo", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({index, verbo: {presente, pasado, traduccion, categoria}})
    });
    const data = await res.json();
    if (data.ok) datos.listarVerbos();
  },
  eliminar: async (index) => {
    if (!confirm("¿Eliminar verbo?")) return;
    const res = await fetch("/eliminar_verbo", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({index})
    });
    const data = await res.json();
    if (data.ok) datos.listarVerbos();
  }
};


// ===== Lógica de práctica =====
const practica = {
  usuario: "invitado",
  tipo: "todos",
  cantidad: 10,
  limitado: true,
  ilimitado: false,
  preguntas: [],
  idx: 0,
  correctas: 0,
  incorrectas: 0,
  streak: 0,
  streakMax: 0,
  startTs: 0,
  timerInt: null,

  usarInvitado() {
    this.usuario = "invitado";
    alert("Entraste como invitado.");
  },
  setUsuario() {
    const nombre = document.getElementById("nombreUsuario").value.trim();
    this.usuario = nombre || "invitado";
    alert(`Usuario: ${this.usuario}`);
  },
  setTipo(t) { this.tipo = t; document.getElementById("pillTipo").textContent = `Tipo: ${t}`; },
  setCantidad(n) {
    this.cantidad = n; this.ilimitado = false; this.limitado = true;
    document.getElementById("cantidadActual").textContent = `Selección: ${n}`;
    document.getElementById("pillLimite").textContent = `Límite: ${n}`;
  },
  setIlimitado() {
    this.ilimitado = true; this.limitado = false;
    document.getElementById("cantidadActual").textContent = "Selección: Ilimitado";
    document.getElementById("pillLimite").textContent = "Límite: Ilimitado";
  },

  async iniciar() {
    // Preguntas
    const res = await fetch("/preguntas", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        tipo: this.tipo,
        cantidad: this.ilimitado ? "ilimitado" : this.cantidad
      })
    });
    this.preguntas = await res.json();
    this.idx = 0;
    this.correctas = 0;
    this.incorrectas = 0;
    this.streak = 0;
    this.streakMax = 0;
    this.startTs = Date.now();
    this._startTimer();

    // UI
    document.getElementById("pillUsuario").textContent = `👤 ${this.usuario}`;
    document.getElementById("pillTipo
