let respuestaCorrecta = "";

function cargarPregunta() {
  fetch("/pregunta")
    .then(response => response.json())
    .then(data => {
      document.getElementById("pregunta").textContent = data.pregunta;
      respuestaCorrecta = data.respuesta.toLowerCase();
      document.getElementById("respuesta").value = "";
      document.getElementById("resultado").textContent = "";
    });
}

function verificar() {
  let respuestaUsuario = document.getElementById("respuesta").value.toLowerCase().trim();
  if (respuestaUsuario === respuestaCorrecta) {
    document.getElementById("resultado").textContent = "✅ ¡Correcto!";
  } else {
    document.getElementById("resultado").textContent = "❌ Incorrecto. La respuesta era: " + respuestaCorrecta;
  }
  setTimeout(cargarPregunta, 2000);
}

function agregarVerbo() {
  const presente = document.getElementById("nuevoPresente").value.trim();
  const pasado = document.getElementById("nuevoPasado").value.trim();
  const traduccion = document.getElementById("nuevaTraduccion").value.trim();

  fetch("/agregar_verbo", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ presente, pasado, traduccion })
  })
  .then(response => response.json())
  .then(data => {
    document.getElementById("mensajeAgregar").textContent = data.mensaje;
    if (data.estado === "ok") {
      document.getElementById("nuevoPresente").value = "";
      document.getElementById("nuevoPasado").value = "";
      document.getElementById("nuevaTraduccion").value = "";
    }
  });
}

window.onload = cargarPregunta;
