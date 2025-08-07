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
  const resultado = document.getElementById("resultado");

  if (respuestaUsuario === respuestaCorrecta) {
    resultado.textContent = "✅ ¡Correcto!";
  } else {
    resultado.textContent = `❌ Incorrecto. La respuesta era: ${respuestaCorrecta}`;
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
        mostrarVerbos();
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

// Mostrar sección correspondiente
function mostrarSeccion(seccion) {
  cerrarSecciones();
  if (seccion === 'practica') {
    document.getElementById("seccionPractica").style.display = "block";
    cargarPregunta();
  } else if (seccion === 'lista') {
    document.getElementById("seccionLista").style.display = "block";
    mostrarVerbos();
  } else if (seccion === 'agregar') {
    document.getElementById("seccionAgregar").style.display = "block";
  }
}

function cerrarSecciones() {
  document.querySelectorAll(".seccion").forEach(sec => sec.style.display = "none");
}

// Modo oscuro / claro
function toggleModo() {
  document.body.classList.toggle("dark");
}
