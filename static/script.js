let respuestaCorrecta = "";
let tipoVerbo = "todos";

function practicar(tipo) {
  tipoVerbo = tipo;
  document.getElementById("practicaCard").classList.remove("hidden");
  cargarPregunta();
}

function cargarPregunta() {
  fetch("/pregunta?tipo=" + tipoVerbo)
    .then(res => res.json())
    .then(data => {
      document.getElementById("pregunta").textContent = data.pregunta;
      respuestaCorrecta = data.respuesta.toLowerCase();
      document.getElementById("respuesta").value = "";
      document.getElementById("resultado").textContent = "";
    });
}

function verificar() {
  const r = document.getElementById("respuesta").value.toLowerCase().trim();
  document.getElementById("resultado").textContent = r === respuestaCorrecta
    ? "✅ ¡Correcto!"
    : "❌ Incorrecto. La respuesta era: " + respuestaCorrecta;
  setTimeout(cargarPregunta, 2000);
}

function agregarVerbo() {
  const presente = document.getElementById("nuevoPresente").value.trim();
  const pasado = document.getElementById("nuevoPasado").value.trim();
  const traduccion = document.getElementById("nuevaTraduccion").value.trim();
  const categoria = document.getElementById("nuevaCategoria").value;

  if (!presente || !pasado || !traduccion) {
    document.getElementById("mensajeAgregar").textContent = "⚠️ Todos los campos son obligatorios.";
    return;
  }

  fetch("/agregar_verbo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presente, pasado, traduccion, categoria })
  })
    .then(res => res.json())
    .then(data => {
      document.getElementById("mensajeAgregar").textContent = data.mensaje;
      mostrarVerbos();
    });
}

function mostrarVerbos() {
  fetch("/verbos")
    .then(res => res.json())
    .then(data => {
      const lista = document.getElementById("listaVerbos");
      lista.innerHTML = "";
      data.forEach((verbo, index) => {
        const li = document.createElement("li");
        li.textContent = `${verbo.presente} – ${verbo.pasado} – ${verbo.traduccion} (${verbo.categoria})`;
        lista.appendChild(li);
      });
    });
}

// Mostrar y ocultar secciones
function mostrarPractica() {
  ocultarTodo();
  document.getElementById("seccionPractica").classList.remove("hidden");
}
function mostrarLista() {
  ocultarTodo();
  document.getElementById("seccionLista").classList.remove("hidden");
}
function toggleAgregar() {
  ocultarTodo();
  document.getElementById("seccionAgregar").classList.remove("hidden");
}
function cerrarPractica() {
  document.getElementById("practicaCard").classList.add("hidden");
}
function cerrarLista() {
  document.getElementById("seccionLista").classList.add("hidden");
}
function ocultarTodo() {
  ["seccionAgregar", "seccionLista", "seccionPractica"].forEach(id => {
    document.getElementById(id).classList.add("hidden");
  });
}

// Modo claro / oscuro
function toggleModo() {
  document.body.classList.toggle("dark");
}

