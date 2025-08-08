let verbos = [];
let tipoSeleccionado = "todos";
let cantidad = 10;
let ilimitado = false;
let usuario = "Invitado";
let preguntas = [];
let indice = 0;
let aciertos = 0;
let errores = 0;

document.addEventListener("DOMContentLoaded", () => {
    cargarVerbos();
});

function cargarVerbos() {
    fetch("/obtener_verbos")
        .then(res => res.json())
        .then(data => verbos = data);
}

function mostrarListaVerbos() {
    ocultarTodo();
    document.getElementById("lista").classList.remove("oculto");
    const lista = document.getElementById("listaVerbos");
    lista.innerHTML = "";
    verbos.forEach((v, i) => {
        lista.innerHTML += `<li>${v.presente} - ${v.pasado} - ${v.traduccion} (${v.tipo}) 
            <button onclick="editar(${i})">✏</button>
            <button onclick="eliminar(${i})">🗑</button>
        </li>`;
    });
}

function mostrarAgregarVerbo() {
    ocultarTodo();
    document.getElementById("agregar").classList.remove("oculto");
}

function agregarVerbo() {
    const nuevo = {
        presente: document.getElementById("presente").value,
        pasado: document.getElementById("pasado").value,
        traduccion: document.getElementById("traduccion").value,
        tipo: document.getElementById("tipoVerbo").value
    };
    fetch("/agregar_verbo", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(nuevo)
    }).then(() => cargarVerbos());
}

function editar(i) {
    const nuevo = prompt("Editar en formato: presente,pasado,traducción,tipo", 
        `${verbos[i].presente},${verbos[i].pasado},${verbos[i].traduccion},${verbos[i].tipo}`);
    if (nuevo) {
        const partes = nuevo.split(",");
        fetch("/editar_verbo", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({index: i, nuevo: {
                presente: partes[0],
                pasado: partes[1],
                traduccion: partes[2],
                tipo: partes[3]
            }})
        }).then(() => cargarVerbos());
    }
}

function eliminar(i) {
    fetch("/eliminar_verbo", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({index: i})
    }).then(() => cargarVerbos());
}

function mostrarInicioPractica() {
    ocultarTodo();
    document.getElementById("practicaConfig").classList.remove("oculto");
}

function modoInvitado() {
    usuario = "Invitado";
}

function setTipo(t) {
    tipoSeleccionado = t;
}

function sumarCantidad() {
    if (cantidad < 40) {
        cantidad += 5;
        document.getElementById("cantidad").textContent = cantidad;
    }
}

function setIlimitado() {
    ilimitado = true;
    document.getElementById("cantidad").textContent = "Ilimitado";
}

function iniciarPractica() {
    const nombreInput = document.getElementById("nombreUsuario").value;
    if (nombreInput) usuario = nombreInput;

    fetch("/pregunta", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            tipo: tipoSeleccionado,
            cantidad: ilimitado ? "ilimitado" : cantidad
        })
    }).then(res => res.json())
      .then(data => {
        preguntas = data;
        indice = 0;
        aciertos = 0;
        errores = 0;
        mostrarPregunta();
    });
}

function mostrarPregunta() {
    ocultarTodo();
    document.getElementById("juego").classList.remove("oculto");
    if (indice < preguntas.length || ilimitado) {
        document.getElementById("pregunta").textContent = preguntas[indice].pregunta;
        document.getElementById("respuesta").value = "";
    } else {
        finalizarPractica();
    }
}

function verificar() {
    const resp = document.getElementById("respuesta").value.trim().toLowerCase();
    if (resp === preguntas[indice].respuesta.toLowerCase()) {
        aciertos++;
    } else {
        errores++;
    }
    indice++;
    mostrarPregunta();
}

function finalizarPractica() {
    ocultarTodo();
    document.getElementById("estadisticas").classList.remove("oculto");
    let texto = `Usuario: ${usuario} - Correctas: ${aciertos}, Incorrectas: ${errores}`;
    if (!ilimitado) {
        const total = aciertos + errores;
        const porcentaje = ((aciertos / total) * 100).toFixed(2);
        texto += ` - Aciertos: ${porcentaje}%`;
    }
    document.getElementById("stats").textContent = texto;
}

function volverMenu() {
    ocultarTodo();
}

function ocultarTodo() {
    document.querySelectorAll("section").forEach(sec => sec.classList.add("oculto"));
}
