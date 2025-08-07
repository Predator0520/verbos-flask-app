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
  resultado.textContent = respuestaUsuario === respuestaCorrecta
    ? "✅ ¡Correcto!" : "❌ Incorrecto. La respuesta era: " + respuestaCorrecta;
  setTimeout(cargarPregunta, 2000);
}

function agregarVerbo() {
  const presente = document.getElementById("nuevoPresente").value.trim();
  const pasado = document.getElementById("nuevoPasado").value.trim();
  const traduccion = document.getElementById("nuevaTraduccion").value.trim();

  if (!presente || !pasado || !traduccion) {
    document.getElementById("mensaje").textContent = "⚠️ Todos los campos son obligatorios.";
    return;
  }

  fetch("/agregar_verbo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presente, pasado, traduccion })
  })
    .then(response => response.json())
    .then(data => {
      document.getElementById("mensaje").textContent = data.mensaje;
      if (data.estado === "ok") {
        document.getElementById("nuevoPresente").value = "";
        document.getElementById("nuevoPasado").value = "";
        document.getElementById("nuevaTraduccion").value = "";
        cargarPregunta();
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
      data.forEach(verbo => {
        const li = document.createElement("li");
        li.innerHTML = `
          ${verbo.presente} – ${verbo.pasado} – ${verbo.traduccion}
          <button onclick="editarVerbo('${verbo.presente}')">✏️</button>
          <button onclick="eliminarVerbo('${verbo.presente}')">🗑️</button>
        `;
        lista.appendChild(li);
      });
    });
}

function eliminarVerbo(presente) {
  fetch("/eliminar_verbo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ presente })
  })
    .then(response => response.json())
    .then(() => mostrarVerbos());
}

function editarVerbo(presente) {
  const nuevoPresente = prompt("Nuevo presente:");
  const nuevoPasado = prompt("Nuevo pasado:");
  const nuevaTraduccion = prompt("Nueva traducción:");

  if (!nuevoPresente || !nuevoPasado || !nuevaTraduccion) return;

  fetch("/editar_verbo", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      original: presente,
      nuevo: {
        presente: nuevoPresente,
        pasado: nuevoPasado,
        traduccion: nuevaTraduccion
      }
    })
  })
    .then(response => response.json())
    .then(() => mostrarVerbos());
}

function toggleModo() {
  document.body.classList.toggle("dark");
}

window.onload = () => {
  cargarPregunta();
};


window.onload = () => {
  cargarPregunta();
};

