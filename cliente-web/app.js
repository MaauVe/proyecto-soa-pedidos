/**
 * app.js — Lógica de navegación SPA y Dashboard para LogiFlow SOA
 * Implementación de Bloque 1 (T-23 y T-24).
 */

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initDashboard();
  initModal();
  initClientes();
  initInventario();
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
      loadClientes();
      break;
    case "inventario":
      loadInventario();
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

// ── 4. MODAL GLOBAL REUTILIZABLE ──────────────────────────────────────────────

function initModal() {
  const modal = document.getElementById("app-modal");
  const closeBtn = document.getElementById("modal-close-btn");

  if (closeBtn) {
    closeBtn.addEventListener("click", closeModal);
  }

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && modal.style.display !== "none") {
      closeModal();
    }
  });
}

function openModal(title, htmlContent) {
  const modal = document.getElementById("app-modal");
  const titleEl = document.getElementById("modal-title");
  const bodyEl = document.getElementById("modal-body");

  if (!modal || !titleEl || !bodyEl) return;

  titleEl.textContent = title;
  bodyEl.innerHTML = htmlContent;
  modal.style.display = "flex";
}

function closeModal() {
  const modal = document.getElementById("app-modal");
  if (modal) modal.style.display = "none";
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── 5. SECCIÓN CLIENTES (T-25) ────────────────────────────────────────────────

function initClientes() {
  const btnToggle = document.getElementById("btn-toggle-cliente-form");
  const btnCancel = document.getElementById("btn-cancel-cliente-form");
  const cardForm = document.getElementById("card-crear-cliente");
  const form = document.getElementById("form-crear-cliente");
  const btnRefresh = document.getElementById("btn-refresh-clientes");

  if (btnToggle && cardForm) {
    btnToggle.addEventListener("click", () => {
      const isHidden = cardForm.style.display === "none";
      cardForm.style.display = isHidden ? "block" : "none";
      btnToggle.textContent = isHidden ? "✖ Cerrar Formulario" : "➕ Nuevo Cliente";
    });
  }

  if (btnCancel && cardForm && btnToggle) {
    btnCancel.addEventListener("click", () => {
      cardForm.style.display = "none";
      btnToggle.textContent = "➕ Nuevo Cliente";
      form.reset();
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadClientes();
      showToast("Actualizando lista de clientes...", "info");
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleCreateCliente();
    });
  }
}

async function loadClientes() {
  const tbody = document.getElementById("clientes-tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" class="empty-state">Cargando clientes...</td></tr>`;

  try {
    const data = await apiFetch(`${CONFIG.URL_CLIENTES}/customers`);
    const items = data && Array.isArray(data.items) ? data.items : [];

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="empty-state">No hay clientes registrados en el sistema.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map((c) => {
      const statusBadge = c.is_active
        ? `<span class="badge badge-active">Activo</span>`
        : `<span class="badge badge-inactive">Inactivo</span>`;

      const actionButton = c.is_active
        ? `<button class="btn btn-sm btn-danger" onclick="deactivateCliente(${c.id}, '${escapeHtml(c.full_name)}')">Desactivar</button>`
        : `<button class="btn btn-sm btn-success" onclick="reactivateCliente(${c.id}, '${escapeHtml(c.full_name)}')">Reactivar</button>`;

      return `
        <tr>
          <td><strong>#${c.id}</strong></td>
          <td><a href="#" style="color: var(--primary); font-weight: 600; text-decoration: none;" onclick="showClienteDetail(${c.id}); return false;">${escapeHtml(c.full_name)}</a></td>
          <td>${escapeHtml(c.email)}</td>
          <td>${escapeHtml(c.phone || "--")}</td>
          <td><span class="badge" style="background:#f1f5f9; color:#334155;">${escapeHtml(c.coverage_zone)}</span></td>
          <td>${statusBadge}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-sm btn-outline" onclick="showClienteDetail(${c.id})">Ver</button>
            ${actionButton}
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state" style="color: var(--danger);">Error al cargar clientes: ${err.message}</td></tr>`;
    showToast(`Error cargando clientes: ${err.message}`, "error");
  }
}

async function handleCreateCliente() {
  const fullName = document.getElementById("cli-full-name").value.trim();
  const email = document.getElementById("cli-email").value.trim();
  const phone = document.getElementById("cli-phone").value.trim();
  const zone = document.getElementById("cli-zone").value;
  const address = document.getElementById("cli-address").value.trim();

  const payload = {
    full_name: fullName,
    email: email,
    phone: phone,
    coverage_zone: zone,
    delivery_address: address
  };

  try {
    await apiFetch(`${CONFIG.URL_CLIENTES}/customers`, {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast("Cliente registrado exitosamente.", "success");
    document.getElementById("form-crear-cliente").reset();
    document.getElementById("card-crear-cliente").style.display = "none";
    const btnToggle = document.getElementById("btn-toggle-cliente-form");
    if (btnToggle) btnToggle.textContent = "➕ Nuevo Cliente";
    loadClientes();
  } catch (err) {
    showToast(`Error al crear cliente: ${err.message}`, "error");
  }
}

async function showClienteDetail(id) {
  try {
    const c = await apiFetch(`${CONFIG.URL_CLIENTES}/customers/${id}`);
    const content = `
      <div class="detail-grid">
        <span class="detail-label">ID Cliente:</span>
        <span class="detail-value"><strong>#${c.id}</strong></span>

        <span class="detail-label">Nombre Completo:</span>
        <span class="detail-value">${escapeHtml(c.full_name)}</span>

        <span class="detail-label">Correo:</span>
        <span class="detail-value"><a href="mailto:${escapeHtml(c.email)}">${escapeHtml(c.email)}</a></span>

        <span class="detail-label">Teléfono:</span>
        <span class="detail-value">${escapeHtml(c.phone || "No especificado")}</span>

        <span class="detail-label">Zona de Envío:</span>
        <span class="detail-value"><span class="badge" style="background:#e0e7ff; color:#3730a3;">${escapeHtml(c.coverage_zone)}</span></span>

        <span class="detail-label">Dirección:</span>
        <span class="detail-value">${escapeHtml(c.delivery_address)}</span>

        <span class="detail-label">Estado:</span>
        <span class="detail-value">${c.is_active ? '<span class="badge badge-active">Activo</span>' : '<span class="badge badge-inactive">Inactivo</span>'}</span>

        <span class="detail-label">Registrado:</span>
        <span class="detail-value">${new Date(c.created_at).toLocaleString("es-MX")}</span>

        <span class="detail-label">Última Modif.:</span>
        <span class="detail-value">${new Date(c.updated_at).toLocaleString("es-MX")}</span>
      </div>
      <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end;">
        <button class="btn btn-secondary" onclick="closeModal()">Cerrar</button>
      </div>
    `;
    openModal(`Detalle del Cliente #${c.id}`, content);
  } catch (err) {
    showToast(`Error al consultar cliente: ${err.message}`, "error");
  }
}

async function deactivateCliente(id, name) {
  if (!confirm(`¿Estás seguro de desactivar al cliente "${name}" (#${id})?`)) return;
  try {
    await apiFetch(`${CONFIG.URL_CLIENTES}/customers/${id}`, { method: "DELETE" });
    showToast(`Cliente #${id} desactivado exitosamente.`, "success");
    loadClientes();
  } catch (err) {
    showToast(`Error al desactivar cliente: ${err.message}`, "error");
  }
}

async function reactivateCliente(id, name) {
  if (!confirm(`¿Deseas reactivar al cliente "${name}" (#${id})?`)) return;
  try {
    await apiFetch(`${CONFIG.URL_CLIENTES}/customers/${id}/reactivate`, { method: "PATCH" });
    showToast(`Cliente #${id} reactivado exitosamente.`, "success");
    loadClientes();
  } catch (err) {
    showToast(`Error al reactivar cliente: ${err.message}`, "error");
  }
}

// ── 6. SECCIÓN INVENTARIO (T-26) ──────────────────────────────────────────────

function initInventario() {
  const btnToggle = document.getElementById("btn-toggle-inventario-form");
  const btnCancel = document.getElementById("btn-cancel-producto-form");
  const cardForm = document.getElementById("card-crear-producto");
  const form = document.getElementById("form-crear-producto");
  const btnRefresh = document.getElementById("btn-refresh-inventario");

  if (btnToggle && cardForm) {
    btnToggle.addEventListener("click", () => {
      const isHidden = cardForm.style.display === "none";
      cardForm.style.display = isHidden ? "block" : "none";
      btnToggle.textContent = isHidden ? "✖ Cerrar Formulario" : "➕ Nuevo Producto";
    });
  }

  if (btnCancel && cardForm && btnToggle) {
    btnCancel.addEventListener("click", () => {
      cardForm.style.display = "none";
      btnToggle.textContent = "➕ Nuevo Producto";
      form.reset();
    });
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      loadInventario();
      showToast("Actualizando inventario...", "info");
    });
  }

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await handleCreateProduct();
    });
  }
}

async function loadInventario() {
  const tbody = document.getElementById("inventario-tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Cargando inventario...</td></tr>`;

  try {
    const data = await apiFetch(`${CONFIG.URL_INVENTARIO}/products`);
    const items = data && Array.isArray(data.items) ? data.items : [];

    if (items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="empty-state">No hay productos en inventario.</td></tr>`;
      return;
    }

    tbody.innerHTML = items.map((p) => {
      const stockClass = p.stock === 0 ? "color: var(--danger); font-weight: bold;" : "";
      const statusBadge = p.is_active
        ? `<span class="badge badge-active">Activo</span>`
        : `<span class="badge badge-inactive">Inactivo</span>`;

      return `
        <tr>
          <td><strong>#${p.id}</strong></td>
          <td><span class="sku-badge">${escapeHtml(p.sku)}</span></td>
          <td><a href="#" style="color: var(--primary); font-weight: 600; text-decoration: none;" onclick="showProductDetail(${p.id}); return false;">${escapeHtml(p.name)}</a></td>
          <td>$${p.unit_price.toFixed(2)}</td>
          <td style="${stockClass}">${p.stock} un.</td>
          <td>${p.weight_kg.toFixed(2)} kg</td>
          <td>${statusBadge}</td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-sm btn-outline" onclick="showProductDetail(${p.id})">Ver</button>
            <button class="btn btn-sm btn-secondary" onclick="openEditProductModal(${p.id})">Editar</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" class="empty-state" style="color: var(--danger);">Error al cargar inventario: ${err.message}</td></tr>`;
    showToast(`Error cargando inventario: ${err.message}`, "error");
  }
}

async function handleCreateProduct() {
  const sku = document.getElementById("prod-sku").value.trim();
  const name = document.getElementById("prod-name").value.trim();
  const price = parseFloat(document.getElementById("prod-price").value);
  const weight = parseFloat(document.getElementById("prod-weight").value);
  const stock = parseInt(document.getElementById("prod-stock").value, 10);
  const desc = document.getElementById("prod-desc").value.trim();

  const payload = {
    sku,
    name,
    unit_price: price,
    weight_kg: weight,
    stock,
    description: desc || null
  };

  try {
    await apiFetch(`${CONFIG.URL_INVENTARIO}/products`, {
      method: "POST",
      body: JSON.stringify(payload)
    });

    showToast("Producto creado exitosamente en inventario.", "success");
    document.getElementById("form-crear-producto").reset();
    document.getElementById("card-crear-producto").style.display = "none";
    const btnToggle = document.getElementById("btn-toggle-inventario-form");
    if (btnToggle) btnToggle.textContent = "➕ Nuevo Producto";
    loadInventario();
  } catch (err) {
    showToast(`Error al crear producto: ${err.message}`, "error");
  }
}

async function showProductDetail(id) {
  try {
    const p = await apiFetch(`${CONFIG.URL_INVENTARIO}/products/${id}`);
    const content = `
      <div class="detail-grid">
        <span class="detail-label">ID Producto:</span>
        <span class="detail-value"><strong>#${p.id}</strong></span>

        <span class="detail-label">Código SKU:</span>
        <span class="detail-value"><span class="sku-badge">${escapeHtml(p.sku)}</span></span>

        <span class="detail-label">Nombre:</span>
        <span class="detail-value"><strong>${escapeHtml(p.name)}</strong></span>

        <span class="detail-label">Precio Unitario:</span>
        <span class="detail-value" style="font-size: 1.1rem; color: var(--primary); font-weight: 700;">$${p.unit_price.toFixed(2)}</span>

        <span class="detail-label">Stock Disponible:</span>
        <span class="detail-value"><strong>${p.stock}</strong> unidades</span>

        <span class="detail-label">Peso Unitario:</span>
        <span class="detail-value">${p.weight_kg.toFixed(2)} kg</span>

        <span class="detail-label">Descripción:</span>
        <span class="detail-value">${escapeHtml(p.description || "Sin descripción")}</span>

        <span class="detail-label">Estado:</span>
        <span class="detail-value">${p.is_active ? '<span class="badge badge-active">Activo</span>' : '<span class="badge badge-inactive">Inactivo</span>'}</span>

        <span class="detail-label">Registrado:</span>
        <span class="detail-value">${new Date(p.created_at).toLocaleString("es-MX")}</span>

        <span class="detail-label">Última Modif.:</span>
        <span class="detail-value">${new Date(p.updated_at).toLocaleString("es-MX")}</span>
      </div>
      <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.5rem;">
        <button class="btn btn-secondary" onclick="closeModal()">Cerrar</button>
        <button class="btn btn-primary" onclick="openEditProductModal(${p.id})">Editar Producto</button>
      </div>
    `;
    openModal(`Detalle del Producto: ${p.name}`, content);
  } catch (err) {
    showToast(`Error al consultar producto: ${err.message}`, "error");
  }
}

async function openEditProductModal(id) {
  try {
    const p = await apiFetch(`${CONFIG.URL_INVENTARIO}/products/${id}`);
    const content = `
      <form id="form-edit-producto" onsubmit="handleUpdateProduct(event, ${p.id})">
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">SKU *</label>
            <input type="text" id="edit-prod-sku" class="form-input" value="${escapeHtml(p.sku)}" required />
          </div>
          <div class="form-group">
            <label class="form-label">Nombre del Producto *</label>
            <input type="text" id="edit-prod-name" class="form-input" value="${escapeHtml(p.name)}" required />
          </div>
          <div class="form-group">
            <label class="form-label">Precio Unitario ($) *</label>
            <input type="number" id="edit-prod-price" class="form-input" step="0.01" min="0.01" value="${p.unit_price}" required />
          </div>
          <div class="form-group">
            <label class="form-label">Peso en Kg *</label>
            <input type="number" id="edit-prod-weight" class="form-input" step="0.01" min="0.01" value="${p.weight_kg}" required />
          </div>
          <div class="form-group">
            <label class="form-label">Stock Disponible *</label>
            <input type="number" id="edit-prod-stock" class="form-input" min="0" value="${p.stock}" required />
          </div>
          <div class="form-group" style="grid-column: 1 / -1;">
            <label class="form-label">Descripción</label>
            <textarea id="edit-prod-desc" class="form-textarea" rows="3">${escapeHtml(p.description || "")}</textarea>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem;">
          <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancelar</button>
          <button type="submit" class="btn btn-success">Guardar Cambios</button>
        </div>
      </form>
    `;
    openModal(`Editar Producto #${p.id} — ${p.name}`, content);
  } catch (err) {
    showToast(`Error al cargar datos del producto: ${err.message}`, "error");
  }
}

async function handleUpdateProduct(e, id) {
  e.preventDefault();
  const sku = document.getElementById("edit-prod-sku").value.trim();
  const name = document.getElementById("edit-prod-name").value.trim();
  const price = parseFloat(document.getElementById("edit-prod-price").value);
  const weight = parseFloat(document.getElementById("edit-prod-weight").value);
  const stock = parseInt(document.getElementById("edit-prod-stock").value, 10);
  const desc = document.getElementById("edit-prod-desc").value.trim();

  const payload = {
    sku,
    name,
    unit_price: price,
    weight_kg: weight,
    stock,
    description: desc || null
  };

  try {
    await apiFetch(`${CONFIG.URL_INVENTARIO}/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    });

    showToast(`Producto #${id} actualizado exitosamente.`, "success");
    closeModal();
    loadInventario();
  } catch (err) {
    showToast(`Error al actualizar producto: ${err.message}`, "error");
  }
}
