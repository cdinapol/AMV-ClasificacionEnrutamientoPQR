// Configuración del frontend desplegable.
// - Vacío  => modo demostración (datos locales en el navegador, localStorage).
// - URL    => modo "live": consume la API del backend (Azure Container Apps).
// Se puede sobreescribir en caliente con ?api=https://... en la URL.
(function () {
  var qs = new URLSearchParams(location.search);
  var fromQuery = qs.get("api");
  // Reemplazar __API_BASE__ tras el despliegue (o dejar vacío para modo demo).
  var baked = "https://amvpqr-api-nyd7eoexrtqom.proudpebble-58aa05c7.eastus2.azurecontainerapps.io";
  window.AMV_API_BASE = (fromQuery || (baked.indexOf("__API") === 0 ? "" : baked)).replace(/\/$/, "");
  window.AMV_LIVE = !!window.AMV_API_BASE;
})();
