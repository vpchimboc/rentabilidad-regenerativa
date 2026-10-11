// Menú lateral del editor de datos en pantallas pequeñas.
(function () {
  "use strict";
  var boton = document.querySelector("[data-frr-menu]");
  if (!boton) return;
  function menu(abrir) {
    document.body.classList.toggle("frr-menu-abierto", abrir);
    boton.setAttribute("aria-expanded", abrir ? "true" : "false");
  }
  boton.addEventListener("click", function () {
    menu(!document.body.classList.contains("frr-menu-abierto"));
  });
  document.querySelectorAll("[data-frr-cerrar]").forEach(function (el) {
    el.addEventListener("click", function () { menu(false); });
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") menu(false); });
  // Centra el elemento activo dentro de la barra lateral (sin mover la página).
  var lateral = document.getElementById("frr-sidebar");
  var activo = document.querySelector(".frr-nav-item[aria-current='page']");
  if (lateral && activo) lateral.scrollTop = activo.offsetTop - lateral.clientHeight / 2;
})();
