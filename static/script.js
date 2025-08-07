// script.js
let verbos = [];
let respuestaCorrecta = "";
let tipoVerbo = "todos";
let usuario = "";
let limitePreguntas = 10;
let preguntasRespondidas = 0;
let respuestasCorrectas = 0;
let respuestasIncorrectas = 0;
let practicaIlimitada = false;

// Cargar verbos desde archivo JSON
fetch("/static/verbos.json")
  .then((response) => response.json())
  .then((data) => {
    verbos = data;
  });

function iniciarPractica() {
  const nombreInput = document.getElementById("nombreUsuario");
  const nombre = nombreInput.value.trim();
  usuario = nombre !== "" ? nombre : "Invitado";
  document.getElementById("seleccionTipo").classList.remove("hidden");
  document.getElementById("inicioPractica").classList.add("hidden");
}

function seleccionarTipo(tipo) {
  tipoVerbo = tipo;
  document.getElementById("seleccionCantidad").classList.remove("hidden");
  document.getElementById("seleccionTipo").classList.add("hidden");
}

function aumentarLimite() {
  if (limitePreguntas < 40) {
    limitePreguntas += 5;
    document.getElementById("contadorLimite").textContent = limitePreguntas;
  }
}

function seleccionarCantidad() {
  practicaIlimitada = false;
  document.getElementById("seleccionCantidad").classList.add("hidden");
  document.getElementById("practicaCard").classList.remove("hidden");
  cargarPregunta();
}

function seleccionarIlimitado() {
  practicaIlimitada = true;
  document.getElementById("seleccionCantidad").classList.add("hidden");
  document.getElementById("practicaCard").classList.remove("hidden");
  cargarPregunta();
}

function cargarPregunta() {
  const verbosFiltrados = tipoVerbo === "todos"
    ? verbos
    : verbos.filter((v) => v.tipo === tipoVerbo);
  const aleatorio = verbosFiltrados[Math.floor(Math.random() * verbosFiltrados.length)];

  const preguntaHTML = document.getElementById("pregunta");
  const tipo = Math.floor(Math.random() * 3);

  if (tipo === 0) {
    preguntaHTML.textContent = `¿Cuál es el presente de '${aleatorio.pasado}'?`;
    respuestaCorrecta = aleatorio.presente;
  } else if (tipo === 1) {
    preguntaHTML.textContent = `¿Cómo se traduce '${aleatorio.presente}' al español?`;
    respuestaCorrecta = aleatorio.significado;
  } else {
    preguntaHTML.textContent = `¿Cuál es el pasado de '${aleatorio.presente}'?`;
    respuestaCorrecta = aleatorio.pasado;
  }

  document.getElementById("respuesta").value = "";
  document.getElementById("resultado").textContent = "";
}

function verificar() {
  const respuestaUsuario = document.getElementById("respuesta").value.trim().toLowerCase();

  if (respuestaUsuario === respuestaCorrecta.toLowerCase()) {
    document.getElementById("resultado").textContent = "✅ ¡Correcto!";
    respuestasCorrectas++;
  } else {
    document.getElementById("resultado").textContent = `❌ Incorrecto. La respuesta era: ${respuestaCorrecta}`;
    respuestasIncorrectas++;
  }

  preguntasRespondidas++;

  if (!practicaIlimitada && preguntasRespondidas >= limitePreguntas) {
    mostrarEstadisticas();
  } else {
    setTimeout(cargarPregunta, 2000);
  }
}

function finalizarPractica() {
  mostrarEstadisticas();
}

function mostrarEstadisticas() {
  document.getElementById("practicaCard").classList.add("hidden");
  document.getElementById("estadisticas").classList.remove("hidden");
  const total = respuestasCorrectas + respuestasIncorrectas;
  const porcentaje = total > 0 ? Math.round((respuestasCorrectas / total) * 100) : 0;

  document.getElementById("resumenUsuario").textContent = usuario;
  document.getElementById("resumenCorrectas").textContent = respuestasCorrectas;
  document.getElementById("resumenIncorrectas").textContent = respuestasIncorrectas;
  document.getElementById("resumenPorcentaje").textContent = porcentaje + "%";
}

function cerrarEstadisticas() {
  document.getElementById("estadisticas").classList.add("hidden");
  preguntasRespondidas = 0;
  respuestasCorrectas = 0;
  respuestasIncorrectas = 0;
  document.getElementById("inicioPractica").classList.remove("hidden");
}

function toggleModoOscuro() {
  document.body.classList.toggle("modo-oscuro");
}

document.getElementById("modoOscuroSwitch").addEventListener("change", toggleModoOscuro);
