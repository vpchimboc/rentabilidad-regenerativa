// Comportamiento mínimo de la interfaz. Todo funciona también sin JavaScript:
// las acciones críticas tienen además una página de confirmación en el servidor.
(function () {
  "use strict";
  var app = document.getElementById("app");
  var boton = document.querySelector("[data-alternar-menu]");

  function menu(abrir) {
    if (!app || !boton) return;
    app.classList.toggle("menu-abierto", abrir);
    boton.setAttribute("aria-expanded", abrir ? "true" : "false");
  }
  if (boton) boton.addEventListener("click", function () {
    menu(!app.classList.contains("menu-abierto"));
  });
  document.querySelectorAll("[data-cerrar-menu]").forEach(function (el) {
    el.addEventListener("click", function () { menu(false); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      menu(false);
      document.querySelectorAll("details.menu-usuario[open]").forEach(function (d) { d.open = false; });
    }
  });
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.menu-usuario[open]").forEach(function (d) {
      if (!d.contains(e.target)) d.open = false;
    });
  });

  // Confirmación en ventana modal para formularios con data-confirmar.
  var modal = document.getElementById("modal-confirmar");
  var pendiente = null;
  document.querySelectorAll("form[data-confirmar]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (form.dataset.confirmado === "1" || !modal || !modal.showModal) return;
      e.preventDefault();
      pendiente = form;
      document.getElementById("modal-titulo").textContent = form.dataset.confirmar;
      document.getElementById("modal-texto").textContent = form.dataset.confirmarTexto || "";
      modal.showModal();
      modal.querySelector("[data-modal-cancelar]").focus();
    });
  });
  if (modal) {
    modal.querySelector("[data-modal-cancelar]").addEventListener("click", function () {
      pendiente = null;
      modal.close();
    });
    modal.querySelector("[data-modal-aceptar]").addEventListener("click", function () {
      modal.close();
      if (pendiente) {
        pendiente.dataset.confirmado = "1";
        var marca = document.createElement("input");
        marca.type = "hidden";
        marca.name = "confirmado";
        marca.value = "1";
        pendiente.appendChild(marca);
        pendiente.requestSubmit ? pendiente.requestSubmit() : pendiente.submit();
      }
    });
  }

  // Estado de carga en el botón que envía un formulario POST.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (e.defaultPrevented || (form.method || "").toLowerCase() !== "post") return;
    var b = e.submitter || form.querySelector("button[type=submit]");
    if (b && b.classList.contains("boton")) {
      b.classList.add("cargando");
      b.setAttribute("aria-busy", "true");
    }
  });
})();
