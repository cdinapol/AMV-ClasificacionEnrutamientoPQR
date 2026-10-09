// Configuración del frontend desplegable.
// - Por defecto apunta a la API en Azure (modo "live": CRUD persistente en el backend).
// - Modo local/demo (localStorage): abrir con ?demo=1 (o ?local=1), por si la API no está.
// - Apuntar a otra API con ?api=https://...
(function () {
  var qs = new URLSearchParams(location.search);
  var forceDemo = qs.get("demo") === "1" || qs.get("local") === "1";
  var fromQuery = qs.has("api") ? qs.get("api") : null;
  // Reemplazar __API_BASE__ tras el despliegue (o dejar vacío para modo demo).
  var baked = "https://amvpqr-api-nyd7eoexrtqom.proudpebble-58aa05c7.eastus2.azurecontainerapps.io";
  var resolved = fromQuery !== null ? fromQuery : (baked.indexOf("__API") === 0 ? "" : baked);
  window.AMV_API_BASE = forceDemo ? "" : (resolved || "").replace(/\/$/, "");
  window.AMV_LIVE = !!window.AMV_API_BASE;
})();
