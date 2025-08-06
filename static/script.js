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
  const respuestaUsuario = document.getElementById("respuesta").value.toLowerCase().trim();
  if (respuestaUsuario === respuestaCorrecta) {
    document.getElementById("resultado").textContent = "✅ ¡Correcto!";
  } else {
    document.getElementById("resultado").textContent =
      "❌ Incorrecto. La respuesta era: " + respuestaCorrecta;
  }
  setTimeout(cargarPregunta, 2000);
}

function agregarVerbo() {
  const presente = document.getElementById("nuevoPresente").value.trim();
  const pasado = document.getElementById("nuevoPasado").value.trim();
  const traduccion = document.getElementById("nuevaTraduccion").value.trim();

  if (!presente || !pasado || !traduccion) {
    document.getElementById("mensajeAgregar").textContent = "⚠️ Todos los campos son obligatorios.";
    return;
  }

  fetch("/agregar_verbo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presente, pasado, traduccion })
  })
    .then(response => response.json())
    .then(data => {
      document.getElementById("mensajeAgregar").textContent = data.mensaje;
      if (data.estado === "ok") {
        document.getElementById("nuevoPresente").value = "";
        document.getElementById("nuevoPasado").value = "";
        document.getElementById("nuevaTraduccion").value = "";
        cargarPregunta();
        mostrarVerbos(); // actualiza la lista
      }
    });
}

function mostrarVerbos() {
  fetch("/verbos")
    .then(response => response.json())
    .then(data => {
      const lista = document.getElementById("listaVerbos");
      lista.innerHTML = "";
      if (data.length === 0) {
        lista.innerHTML = "<li>No hay verbos guardados aún.</li>";
        return;
      }
      data.forEach(verbo => {
        const li = document.createElement("li");
        li.textContent = `${verbo.presente} – ${verbo.pasado} – ${verbo.traduccion}`;
        lista.appendChild(li);
      });
    });
}

window.onload = cargarPregunta;
