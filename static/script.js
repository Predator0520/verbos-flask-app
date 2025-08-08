// Helpers de modal (abren/cierran siempre)
const show = (id)=>{const m=document.getElementById(id); if(!m) return; m.classList.remove("hidden"); m.style.display="flex";}
const hide = (id)=>{const m=document.getElementById(id); if(!m) return; m.classList.add("hidden"); m.style.display="none";}

// ===== UI =====
const ui = {
  mostrar: (id) => {
    // cierra modales si estaban abiertos
    hide("modalVerb"); hide("resumen");

    // cambia sección
    ["menu","setup","play","lista","stats"].forEach(sec => {
      document.getElementById(sec).classList.add("hidden");
    });
    document.getElementById(id).classList.remove("hidden");

    // deshabilita "Ver Verbos" cuando no corresponde
    document.getElementById("btn-ver-verbos").disabled = (id === "play" || id === "setup");

    // prepara wizard
    if(id==="setup"){
      ui.irPaso(1);
      setTimeout(() => {
        const wh = (practica.modo === 'wh');
        document.getElementById("blockWH").classList.toggle("hidden", !wh);
        document.getElementById("blockTipos").classList.toggle("hidden", wh);
      }, 0);
      document.getElementById("setupTitle").textContent =
        practica.modo==='simple' ? "🧠 Configurar: Simple Past" :
        practica.modo==='continuous' ? "🧠 Configurar: Past Continuous" :
        "🧠 Configurar: WH Questions";
    }
  },
  irPaso: (n) => {
    ["step1","step2","step3"].forEach(s => document.getElementById(s).classList.add("hidden"));
    document.getElementById(`step${n}`).classList.remove("hidden");
  },
  cerrarResumen: ()=> hide("resumen"),

  // Sidebar usuarios + stats
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
              <tr><th>Fecha</th><th>Usuario</th><th>Modo</th><th>Límite</th><th>Correctas</th><th>Incorrectas</th><th>%</th><th>Racha</th><th>Tiempo</th></tr>
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
  },

  // ===== Dropdown del Menú en la barra =====
  toggleMenuDropdown: (open=null) => {
    const dd = document.getElementById("menuDropdown");
    const isOpen = !dd.classList.contains("hidden");
    const next = (open===null ? !isOpen : !!open);
    dd.classList.toggle("hidden", !next);
  }
};

// Cerrar dropdown al hacer click fuera
document.addEventListener("click", (e)=>{
  const btn = document.getElementById("btn-menu");
  const dd  = document.getElementById("menuDropdown");
  if (!btn || !dd) return;
  if (dd.classList.contains("hidden")) return;
  if (!btn.contains(e.target) && !dd.contains(e.target)){
    dd.classList.add("hidden");
  }
});

// ===== VERBOS (CRUD + modal) =====
const datos = {
  verbos: [],
  _mode: "add",
  _editIdx: -1,

  listarVerbos: async () => {
    const ul = document.getElementById("listaVerbos");
    ul.innerHTML = "<li>Cargando...</li>";
    const res = await fetch("/obtener_verbos");
    const arr = await res.json();
    datos.verbos = arr;
    if (!arr.length) { ul.innerHTML = "<li>No hay verbos guardados aún.</li>"; return; }

    ul.innerHTML = "";
    arr.forEach((v, idx) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span class="badge ${v.categoria}">${v.categoria}</span>
        <span class="verb">
          ${v.presente} – ${v.pasado} – ${v.continuo || '<i>no continuo</i>'} –
          ${v.traduccion} / ${v.traduccion_pasado} / ${v.traduccion_continuo || '<i>—</i>'}
        </span>
        <button class="mini" data-action="edit" data-idx="${idx}">✏️</button>
        <button class="mini danger" data-action="del" data-idx="${idx}">🗑️</button>
      `;
      ul.appendChild(li);
    });

    ul.querySelectorAll("button[data-action]").forEach(b=>{
      b.onclick = async (e)=>{
        const idx = +e.currentTarget.dataset.idx;
        const act = e.currentTarget.dataset.action;
        if (act === "edit") datos.abrirModalEditar(idx);
        else {
          if (!confirm("¿Eliminar verbo?")) return;
          const res = await fetch("/eliminar_verbo", {
            method:"POST", headers:{ "Content-Type":"application/json" },
            body: JSON.stringify({index: idx})
          });
          const data = await res.json();
          if (data.ok) datos.listarVerbos(); else alert(data.msg || "Error al eliminar");
        }
      }
    });
  },

  abrirModalAgregar: ()=>{
    datos._mode = "add"; datos._editIdx = -1;
    document.getElementById("modalVerbTitle").textContent = "➕ Agregar verbo";
    ["editPresente","editPasado","editTraduccion","editTraduccionPasado","editContinuo","editTraduccionContinuo"].forEach(id=>document.getElementById(id).value="");
    document.getElementById("editCategoria").value="regular";
    show("modalVerb");
    setTimeout(()=>document.getElementById("editPresente").focus(),0);
  },
  abrirModalEditar: (idx)=>{
    datos._mode = "edit"; datos._editIdx = idx;
    const v = datos.verbos[idx];
    document.getElementById("modalVerbTitle").textContent = "✏️ Editar verbo";
    document.getElementById("editPresente").value = v.presente || "";
    document.getElementById("editPasado").value = v.pasado || "";
    document.getElementById("editTraduccion").value = v.traduccion || "";
    document.getElementById("editTraduccionPasado").value = v.traduccion_pasado || "";
    document.getElementById("editContinuo").value = v.continuo || "";
    document.getElementById("editTraduccionContinuo").value = v.traduccion_continuo || "";
    document.getElementById("editCategoria").value = v.categoria || "regular";
    show("modalVerb");
  },
  cerrarModal: ()=> hide("modalVerb"),

  guardarModal: async ()=>{
    const g = id => document.getElementById(id).value.trim().toLowerCase();
    const payload = {
      presente: g("editPresente"),
      pasado: g("editPasado"),
      traduccion: g("editTraduccion"),
      traduccion_pasado: g("editTraduccionPasado"),
      continuo: g("editContinuo"),
      traduccion_continuo: g("editTraduccionContinuo"),
      categoria: document.getElementById("editCategoria").value
    };
    if (!payload.presente || !payload.pasado || !payload.traduccion || !payload.traduccion_pasado){
      alert("Completa base, pasado y sus traducciones. (El continuo puede quedar vacío)");
      payload.continuo = payload.continuo || "";
      payload.traduccion_continuo = payload.traduccion_continuo || payload.traduccion_pasado || payload.traduccion;
    }

    if (datos._mode === "add"){
      const res = await fetch("/agregar_verbo", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(payload) });
      const data = await res.json();
      if (!data.ok){ alert(data.msg || "Error al agregar"); return; }
    }else{
      const res = await fetch("/editar_verbo", { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify({index: datos._editIdx, verbo: payload}) });
      const data = await res.json();
      if (!data.ok){ alert(data.msg || "Error al editar"); return; }
    }
    hide("modalVerb");
    if (!document.getElementById("lista").classList.contains("hidden")) datos.listarVerbos();
  },

  exportar: ()=> window.location="/exportar_verbos",
  importar: async (file)=>{
    if(!file) return;
    const fd=new FormData(); fd.append("file", file);
    const res = await fetch("/importar_verbos",{method:"POST", body:fd});
    const data = await res.json();
    alert(data.msg || (data.ok?"Importado":"Error"));
    if (data.ok) datos.listarVerbos();
    document.getElementById("inputImport").value="";
  }
};

// ===== PRÁCTICA =====
const practica = {
  modo:"simple",     // simple | continuous | wh
  whTipo:"traduccion", // traduccion | oraciones
  usuario:"invitado",
  tipo:"todos",
  cantidad:10,
  ilimitado:false,

  preguntas:[],
  idx:0,
  correctas:0,
  incorrectas:0,
  streak:0,
  streakMax:0,
  startTs:0,
  timerInt:null,

  setModo(m){ this.modo=m; },
  setWHTipo(t){ this.whTipo=t; },
  usarInvitado(){ this.usuario="invitado"; },
  setUsuario(){ this.usuario=(document.getElementById("nombreUsuario").value.trim()||"invitado"); },
  setTipo(t){ this.tipo=t; },
  setCantidad(n){ this.cantidad=n; this.ilimitado=false;
    document.getElementById("cantidadActual").textContent=`Selección: ${n}`;
    document.getElementById("pillLimite").textContent=`Límite: ${n}`;
  },
  setIlimitado(){ this.ilimitado=true;
    document.getElementById("cantidadActual").textContent="Selección: Ilimitado";
    document.getElementById("pillLimite").textContent="Límite: Ilimitado";
  },

  async iniciar(){
    hide("resumen");
    let arr = [];
    try{
      if (this.modo === "wh"){
        const res = await fetch("/preguntas_wh",{method:"POST",headers:{"Content-Type":"application/json"},body: JSON.stringify({cantidad: this.ilimitado?"ilimitado":this.cantidad})});
        arr = await res.json();
        if (this.whTipo === "oraciones"){
          // Convertimos a opción múltiple en el cliente
          const allAnswers = arr.map(x=>x.respuesta);
          arr = arr.map(q=>{
            const correct = q.respuesta;
            const pool = allAnswers.filter(a=>a!==correct);
            const mix = [];
            while(mix.length<3 && pool.length){
              const idx = Math.floor(Math.random()*pool.length);
              const pick = pool.splice(idx,1)[0];
              if (!mix.includes(pick)) mix.push(pick);
            }
            const opciones = [correct, ...mix].sort(()=>Math.random()-0.5);
            return { pregunta: q.pregunta, opciones, correcta: opciones.indexOf(correct) };
          });
        }
      }else{
        const res = await fetch("/preguntas",{method:"POST",headers:{"Content-Type":"application/json"},
          body: JSON.stringify({modo:this.modo,tipo:this.tipo,cantidad:this.ilimitado?"ilimitado":this.cantidad})});
        arr = await res.json();
      }
    }catch(e){ alert("No se pudieron cargar las preguntas."); return; }

    if (!Array.isArray(arr) || arr.length===0){
      alert("No hay preguntas para ese modo/filtro. Agrega verbos o cambia el filtro.");
      ui.mostrar("setup"); ui.irPaso(2); return;
    }

    this.preguntas=arr; this.idx=0; this.correctas=0; this.incorrectas=0;
    this.streak=0; this.streakMax=0; this.startTs=Date.now(); this._startTimer();

    document.getElementById("pillUsuario").textContent=`👤 ${this.usuario}`;
    const modoText = (this.modo==='wh' ? `wh/${this.whTipo}` : this.modo);
    document.getElementById("pillModo").textContent=`Modo: ${modoText}`;
    document.getElementById("pillTipo").textContent=(this.modo==='wh' ? "Tipo: —" : `Tipo: ${this.tipo}`);
    document.getElementById("pillLimite").textContent=`Límite: ${this.ilimitado?"Ilimitado":this.cantidad}`;
    document.getElementById("pillContador").textContent=`0/${this.ilimitado ? "∞" : this.preguntas.length}`;
    document.getElementById("pillStreak").textContent="🔥 racha: 0";
    document.getElementById("resultado").textContent="";

    ui.mostrar("play");
    this._pintarPregunta();
  },

  _pintarPregunta(){
    const boxLibre=document.getElementById("boxLibre");
    const boxOpc=document.getElementById("boxOpciones");

    if (!this.ilimitado && this.idx >= this.preguntas.length){ this.finalizar(); return; }
    const q = this.preguntas[this.idx % this.preguntas.length];
    document.getElementById("pregunta").textContent=q.pregunta;

    if (Array.isArray(q.opciones)){ // opción múltiple
      boxLibre.classList.add("hidden"); boxOpc.classList.remove("hidden");
      boxOpc.innerHTML="";
      q.opciones.forEach((op,i)=>{
        const b=document.createElement("button");
        b.className="mc-option"; b.textContent=op;
        b.onclick=()=>this.verificarOpcion(i);
        boxOpc.appendChild(b);
      });
    }else{
      boxOpc.classList.add("hidden"); boxLibre.classList.remove("hidden");
      const r=document.getElementById("respuesta"); r.value=""; r.focus();
      const btn=document.getElementById("btnVerificar");
      const onInput=()=>btn.disabled=(r.value.trim()==="");
      r.oninput=onInput; onInput();
    }

    document.getElementById("pillContador").textContent=
      `${Math.min(this.idx, this.preguntas.length)}/${this.ilimitado ? "∞" : this.preguntas.length}`;
  },

  verificar(){
    const norm = s => (s??"").toString().trim().toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g,"");
    const q=this.preguntas[this.idx % this.preguntas.length];
    const resp=norm(document.getElementById("respuesta").value||"");
    const exp=q.respuesta; let ok=false;
    if (Array.isArray(exp)) ok=exp.some(a=>norm(a)===resp); else ok=(norm(exp)===resp);
    this._post(ok, q);
  },
  verificarOpcion(iSel){
    const q=this.preguntas[this.idx % this.preguntas.length];
    const ok = (iSel === q.correcta);
    this._post(ok, q);
  },
  _post(ok,q){
    const out=document.getElementById("resultado");
    if (ok){ this.correctas++; this.streak++; this.streakMax=Math.max(this.streakMax,this.streak);
      out.textContent="✅ ¡Correcto!"; if (this.streak && this.streak%5===0) out.textContent+=` 🔥 Racha de ${this.streak}!`;
    }else{ this.incorrectas++; this.streak=0;
      const exp = Array.isArray(q.respuesta)? q.respuesta[0] : (typeof q.respuesta==="string"? q.respuesta : q.opciones[q.correcta]);
      out.textContent=`❌ Incorrecto. Era: ${exp}`;
    }
    this.idx++; this._pintarPregunta();
  },

  finalizar(){
    this._stopTimer();
    const secs=Math.floor((Date.now()-this.startTs)/1000);
    const total=this.correctas+this.incorrectas;
    const porcentaje= total? ((this.correctas/total)*100).toFixed(2) : "0.00";
    const modoText=(this.modo==='wh'?`wh/${this.whTipo}`:this.modo);
    const limiteText=this.ilimitado?"ilimitado":this.cantidad;

    fetch("/guardar_resultado",{method:"POST",headers:{"Content-Type":"application/json"},
      body: JSON.stringify({
        usuario:this.usuario,tipo:modoText,limitado:!this.ilimitado,cantidad:limiteText,
        correctas:this.correctas,incorrectas:this.incorrectas,streak_max:this.streakMax,duracion_segundos:secs
      })
    });

    document.getElementById("rUsuario").textContent=this.usuario;
    document.getElementById("rModo").textContent=modoText;
    document.getElementById("rTipo").textContent=(this.modo==='wh'?"—":this.tipo);
    document.getElementById("rOk").textContent=this.correctas;
    document.getElementById("rBad").textContent=this.incorrectas;
    document.getElementById("rStreak").textContent=this.streakMax;
    document.getElementById("rTiempo").textContent=`${Math.floor(secs/60)}m ${secs%60}s (${porcentaje}%)`;

    show("resumen");
    document.getElementById("btn-ver-verbos").disabled=false;
  },

  _startTimer(){
    const pill=document.getElementById("pillTimer");
    clearInterval(this.timerInt);
    this.timerInt=setInterval(()=>{
      const secs=Math.floor((Date.now()-this.startTs)/1000);
      const mm=String(Math.floor(secs/60)).padStart(2,"0");
      const ss=String(secs%60).padStart(2,"0");
      pill.textContent=`⏱ ${mm}:${ss}`;
    },1000);
  },
  _stopTimer(){ clearInterval(this.timerInt); this.timerInt=null; }
};

// ===== Atajos =====
document.addEventListener("keydown",(e)=>{
  // ESC cierra modales
  if (e.key==="Escape"){ hide("modalVerb"); hide("resumen"); }

  // Enter verifica en modo libre
  const inPlay=!document.getElementById("play").classList.contains("hidden");
  if (inPlay){
    const isMCQ=!document.getElementById("boxOpciones").classList.contains("hidden");
    if (!isMCQ && e.key==="Enter") document.getElementById("btnVerificar").click();
    if (isMCQ && ["1","2","3","4"].includes(e.key)){
      const i=+e.key-1;
      const btn=document.querySelectorAll("#boxOpciones .mc-option")[i];
      if (btn) btn.click();
    }
  }
});

// Dark mode con icono dinámico
(function(){
  const btn=document.getElementById("btn-dark");
  const apply=(dark)=>{
    document.body.classList.toggle("dark",dark);
    localStorage.setItem("dark", dark?"1":"0");
    btn.textContent = dark ? "🌙" : "☀️";
    btn.setAttribute("aria-label", dark ? "Cambiar a claro" : "Cambiar a oscuro");
    btn.title = dark ? "Modo oscuro" : "Modo claro";
  };
  // estado inicial
  const initialDark = (localStorage.getItem("dark")==="1");
  apply(initialDark);
  btn.onclick=()=>apply(!document.body.classList.contains("dark"));
})();
 
// Inicio
ui.mostrar("menu");

// Acciones desde el dropdown del Menú
window._goSimple = ()=>{
  practica.setModo('simple');
  ui.toggleMenuDropdown(false);
  ui.mostrar('setup');
};
window._goContinuous = ()=>{
  practica.setModo('continuous');
  ui.toggleMenuDropdown(false);
  ui.mostrar('setup');
};
window._goWH = ()=>{
  practica.setModo('wh');
  ui.toggleMenuDropdown(false);
  ui.mostrar('setup');
};
