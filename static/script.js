function mostrarVerbos() {
  fetch("/verbos")
    .then(response => response.json())
    .then(data => {
      const lista = document.getElementById("listaVerbos");
      lista.innerHTML = ""; // Limpiar lista anterior
      if (data.length === 0) {
        lista.innerHTML = "<li>No hay verbos guardados aún.</li>";
        return;
      }
      data.forEach(verbo => {
        const li = document.createElement("li");
        li.textContent = `${verbo.presente} – ${verbo.pasado} – ${verbo.traduccion}`;
        lista.appendChild(li);
      });
    })
    .catch(error => {
      console.error("Error al obtener verbos:", error);
    });
}
