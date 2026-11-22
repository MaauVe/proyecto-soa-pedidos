/**
 * app.js — Lógica de navegación SPA y Dashboard para LogiFlow SOA
 * Implementación de Bloque 1 (T-23 y T-24).
 */

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initDashboard();
});

// ── 1. NAVEGACIÓN SPA ─────────────────────────────────────────────────────────

function initNavigation() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabName = btn.getAttribute("data-tab");

      // Actualizar botones de pestaña
      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      // Mostrar sección correspondiente y ocultar el resto
      tabContents.forEach((section) => {
        section.classList.remove("active");
        if (section.id === `section-${tabName}`) {
          section.classList.add("active");
        }
      });

      // Disparar carga de datos según la sección activa
      onTabActivated(tabName);
    });
  });
}

function onTabActivated(tabName) {
  switch (tabName) {
    case "dashboard":
      loadDashboard();
      break;
    case "clientes":
      // Bloque 2 (T-25)
      break;
    case "inventario":
      // Bloque 2 (T-26)
      break;
    case "pedidos":
      // Bloque 3 (T-27)
      break;
    case "envios":
      // Bloque 4 (T-28)
      break;
  }
}

// ── 2. UTILIDADES DE RED Y MENSAJES (apiFetch y showToast) ───────────────────

/**
 * Cliente HTTP estándar para el frontend.
 * Agrega automáticamente el header X-API-Key y Content-Type.
 */
async function apiFetch(url, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": CONFIG.API_KEY,
    ...(options.headers || {})
  };

  try {
    const response = await fetch(url, { ...options, headers });

    // Manejo de errores HTTP
    if (!response.ok) {
      let errorMessage = `Error HTTP ${response.status}`;
      try {
        const errorData = await response.json();
        if (typeof errorData.detail === "string") {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail)) {
          errorMessage = errorData.detail.map((d) => d.msg || JSON.stringify(d)).join(", ");
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }
      } catch (_) {
        // Respuesta no es JSON válido
      }

      if (response.status === 401) {
        errorMessage = "Error de autenticación: verifica la API Key en config.js.";
      }

      throw new Error(errorMessage);
    }

    // Si la respuesta no tiene contenido (204 No Content)
    if (response.status === 204) {
      return null;
    }

    return await response.json();
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      throw new Error("No se pudo conectar con el microservicio. Verifica que esté en ejecución y con CORS habilitado.");
    }
    throw err;
  }
}

/**
 * Muestra una notificación emergente tipo toast (desaparece en 5 segundos).
 */
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${message}</span>
    <button style="background:none;border:none;cursor:pointer;font-weight:bold;color:inherit;" onclick="this.parentElement.remove()">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    if (toast.parentElement) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }
  }, 5000);
}

// ── 3. DASHBOARD Y HEALTH CHECK (T-24) ─────────────────────────────────────────

const SERVICES_CONFIG = [
  {
    id: "clientes",
    name: "Servicio Clientes",
    port: 8001,
    url: CONFIG.URL_CLIENTES,
    cardId: "card-clientes"
  },
  {
    id: "inventario",
    name: "Servicio Inventario",
    port: 8002,
    url: CONFIG.URL_INVENTARIO,
    cardId: "card-inventario"
  },
  {
    id: "envios",
    name: "Servicio Envíos",
    port: 8003,
    url: CONFIG.URL_ENVIOS,
    cardId: "card-envios"
  },
  {
    id: "pedidos",
    name: "Servicio Pedidos",
    port: 8004,
    url: CONFIG.URL_PEDIDOS,
    cardId: "card-pedidos"
  }
];

function initDashboard() {
  const btnRefresh = document.getElementById("btn-refresh-dashboard");
  const btnCheckAll = document.getElementById("btn-check-all");

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadDashboard();
      showToast("Actualizando estado de los microservicios...", "info");
    });
  }

  if (btnCheckAll) {
    btnCheckAll.addEventListener("click", () => {
      loadDashboard();
      showToast("Verificando todos los microservicios...", "info");
    });
  }

  // Primera carga al abrir la app
  loadDashboard();
}

/**
 * Consulta en paralelo el endpoint GET /health de cada servicio mediante Promise.allSettled.
 */
async function loadDashboard() {
  const startTime = new Date();
  updateGlobalBannerLoading();

  // Marcar tarjetas en estado de carga
  SERVICES_CONFIG.forEach((svc) => setCardLoading(svc.cardId));

  // Consultar en paralelo los 4 servicios
  const checks = SERVICES_CONFIG.map(async (svc) => {
    const t0 = performance.now();
    try {
      // /health es público según spec
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 4000);

      const res = await fetch(`${svc.url}/health`, {
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      const elapsedMs = Math.round(performance.now() - t0);

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }

      const data = await res.json();
      return {
        id: svc.id,
        cardId: svc.cardId,
        ok: true,
        data,
        latency: elapsedMs
      };
    } catch (err) {
      const elapsedMs = Math.round(performance.now() - t0);
      return {
        id: svc.id,
        cardId: svc.cardId,
        ok: false,
        error: err.name === "AbortError" ? "Timeout de conexión" : (err.message || "No disponible"),
        latency: elapsedMs
      };
    }
  });

  const results = await Promise.allSettled(checks);

  let activeCount = 0;
  results.forEach((res) => {
    if (res.status === "fulfilled") {
      const item = res.value;
      if (item.ok) {
        activeCount++;
        renderCardSuccess(item.cardId, item.data, item.latency);
      } else {
        renderCardError(item.cardId, item.error, item.latency);
      }
    }
  });

  updateGlobalBannerResult(activeCount, SERVICES_CONFIG.length, startTime);
}

function setCardLoading(cardId) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const badge = card.querySelector(".service-status-badge");
  if (badge) {
    badge.className = "service-status-badge status-badge-loading";
    badge.innerHTML = `<span class="status-dot loading"></span> Verificando...`;
  }
}

function renderCardSuccess(cardId, data, latency) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const badge = card.querySelector(".service-status-badge");
  if (badge) {
    badge.className = "service-status-badge status-badge-ok";
    badge.innerHTML = `<span class="status-dot ok"></span> Activo`;
  }

  const versionEl = card.querySelector(".card-version");
  if (versionEl) {
    versionEl.textContent = `Versión: ${data.version || "0.1.0"}`;
  }

  const latencyEl = card.querySelector(".card-latency");
  if (latencyEl) {
    latencyEl.textContent = `Latencia: ${latency} ms`;
  }
}

function renderCardError(cardId, errorMsg, latency) {
  const card = document.getElementById(cardId);
  if (!card) return;

  const badge = card.querySelector(".service-status-badge");
  if (badge) {
    badge.className = "service-status-badge status-badge-error";
    badge.innerHTML = `<span class="status-dot error"></span> Caído`;
  }

  const versionEl = card.querySelector(".card-version");
  if (versionEl) {
    versionEl.textContent = `Error: ${errorMsg}`;
  }

  const latencyEl = card.querySelector(".card-latency");
  if (latencyEl) {
    latencyEl.textContent = `Latencia: ${latency} ms`;
  }
}

function updateGlobalBannerLoading() {
  const banner = document.getElementById("global-status");
  const title = document.getElementById("global-status-title");
  const desc = document.getElementById("global-status-desc");

  if (!banner || !title || !desc) return;

  banner.className = "global-status-banner";
  banner.style.backgroundColor = "#f1f5f9";
  banner.style.borderColor = "#cbd5e1";
  banner.style.color = "#334155";
  title.textContent = "Verificando microservicios...";
  desc.textContent = "Consultando endpoints de salud /health en paralelo...";
}

function updateGlobalBannerResult(activeCount, totalCount, date) {
  const banner = document.getElementById("global-status");
  const title = document.getElementById("global-status-title");
  const desc = document.getElementById("global-status-desc");
  const timeEl = document.getElementById("global-status-time");

  if (!banner || !title || !desc) return;

  banner.style.backgroundColor = "";
  banner.style.borderColor = "";
  banner.style.color = "";

  const timeStr = date.toLocaleTimeString("es-MX", { hour12: false });
  if (timeEl) timeEl.textContent = `Última verificación: ${timeStr}`;

  if (activeCount === totalCount) {
    banner.className = "global-status-banner all-ok";
    title.textContent = `✅ Todos los microservicios están operativos (${activeCount}/${totalCount})`;
    desc.textContent = "El sistema SOA está completamente disponible para operaciones de clientes, inventario, pedidos y envíos.";
  } else {
    banner.className = "global-status-banner has-errors";
    title.textContent = `⚠️ Atención: ${totalCount - activeCount} servicio(s) no disponible(s) (${activeCount}/${totalCount} activos)`;
    desc.textContent = "Verifique las tarjetas de estado para identificar los servicios caídos e inicie los servidores correspondientes.";
  }
}
