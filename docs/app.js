const API_BASE = "https://bankpromos-production.up.railway.app";

const state = {
  promos: [],
  fuel: [],
  currentCategory: "",
};

function getInitials(name) {
  if (!name) return "?";
  const words = name.trim().split(/\s+/).filter(w => w.length > 0);
  if (words.length === 1) return words[0].substring(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function getBankClass(bank) {
  if (!bank) return "default";
  const b = bank.toLowerCase();
  if (b.includes("itau")) return "bank-itau";
  if (b.includes("ueno")) return "bank-ueno";
  if (b.includes("continental")) return "bank-continental";
  if (b.includes("sudameris")) return "bank-sudameris";
  if (b.includes("bnf")) return "bank-bnf";
  return "default";
}

function formatGs(val) {
  if (val == null) return "-";
  return new Intl.NumberFormat("es-PY").format(val) + " Gs.";
}

const CATEGORY_PRIORITY = {
  "Combustible": 1,
  "Supermercados": 2,
  "Gastronomía": 3,
  "Tecnología": 4,
  "Indumentaria": 5,
  "Belleza": 6,
  "Salud": 7,
  "Viajes": 8,
};

function sortPromos(promos) {
  return [...promos].sort((a, b) => {
    const catA = CATEGORY_PRIORITY[a.category] || 99;
    const catB = CATEGORY_PRIORITY[b.category] || 99;
    if (catA !== catB) return catA - catB;
    return (b.discount_percent || 0) - (a.discount_percent || 0);
  });
}

function renderHero(promo) {
  if (!promo) return "";
  
  return `
    <div class="hero-card">
      <div class="hero-label">Mejor descuento del día</div>
      <h2 class="hero-merchant">${promo.display_name}</h2>
      <div class="hero-discount">${promo.highlight_value}</div>
      ${promo.cap_display ? `<div class="hero-cap">${promo.cap_display}</div>` : ""}
      <div class="hero-meta">
        <span class="hero-badge">${promo.category}</span>
        <span class="hero-badge">${promo.bank_id}</span>
        ${promo.valid_days_display ? `<span class="hero-badge">${promo.valid_days_display}</span>` : ""}
      </div>
    </div>
  `;
}

function renderPromoCard(promo) {
  const initials = getInitials(promo.display_name);
  const bankClass = getBankClass(promo.bank_id);
  
  return `
    <article class="promo-card">
      <div class="promo-header">
        <div class="promo-logo ${bankClass}">${initials}</div>
        <div class="promo-title">
          <h3 class="promo-merchant">${promo.display_name}</h3>
          <p class="promo-category">${promo.category}</p>
        </div>
      </div>
      <div class="promo-highlight">${promo.highlight_value}</div>
      ${promo.cap_display ? `<div class="promo-cap">${promo.cap_display}</div>` : ""}
      <div class="promo-meta">
        <span class="promo-badge bank">${promo.bank_id}</span>
        ${promo.valid_days_display ? `<span class="promo-badge days">${promo.valid_days_display}</span>` : ""}
        ${promo.result_quality_label && promo.result_quality_label !== "UNKNOWN" ? `<span class="promo-badge quality">${promo.result_quality_label}</span>` : ""}
      </div>
      ${promo.conditions_short ? `<p class="promo-conditions">${promo.conditions_short}</p>` : ""}
    </article>
  `;
}

function renderPromoGrid(promos) {
  const grid = document.getElementById("promoGrid");
  const hero = document.getElementById("hero");
  
  if (!promos.length) {
    hero.innerHTML = "";
    grid.innerHTML = `<div class="empty"><div class="empty-icon">📭</div><p>Sin promociones</p></div>`;
    return;
  }
  
  const sorted = sortPromos(promos);
  const topPromo = sorted[0];
  hero.innerHTML = renderHero(topPromo);
  grid.innerHTML = sorted.slice(1).map(renderPromoCard).join("") || sorted.slice(0, 1).map(renderPromoCard).join("");
}

function renderFuelTop(item) {
  if (!item) return "";
  
  return `
    <div class="fuel-top">
      <div class="fuel-top-header">Mejor precio</div>
      <div class="fuel-top-grid">
        <div class="fuel-top-stat">
          <div class="fuel-top-stat-value">${item.discount_percent}%</div>
          <div class="fuel-top-stat-label">descuento</div>
        </div>
        <div class="fuel-top-stat">
          <div class="fuel-top-stat-value">${formatGs(item.savings)}</div>
          <div class="fuel-top-stat-label">ahorro</div>
        </div>
      </div>
      <div style="text-align:center;margin-top:16px;font-weight:600;">
        ${item.emblem} · ${item.bank_id}
      </div>
    </div>
  `;
}

function renderFuelCard(item, rank) {
  const isBest = rank === 1;
  
  return `
    <div class="fuel-card ${isBest ? "best" : ""}">
      <div class="fuel-rank">${rank}</div>
      <div class="fuel-card-info">
        <div class="fuel-card-bank">${item.bank_id}</div>
        <div class="fuel-card-station">${item.emblem} · ${item.fuel_type}</div>
      </div>
      <div class="fuel-card-price">
        <div class="fuel-card-savings">-${item.discount_percent}%</div>
        <div class="fuel-card-final">${formatGs(item.estimated_final_price)}</div>
      </div>
    </div>
  `;
}

function renderFuelList(items) {
  const container = document.getElementById("fuelList");
  
  if (!items.length) {
    container.innerHTML = `<div class="empty"><div class="empty-icon">⛽</div><p>Sin resultados</p></div>`;
    return;
  }
  
  container.innerHTML = renderFuelTop(items[0]) + items.slice(1, 4).map((item, i) => renderFuelCard(item, i + 2)).join("");
}

async function loadPromos() {
  try {
    const res = await fetch(`${API_BASE}/today`);
    const data = await res.json();
    state.promos = data.results || [];
    renderPromoGrid(state.promos);
  } catch (e) {
    renderPromoGrid([]);
  }
}

async function loadFuel() {
  try {
    const res = await fetch(`${API_BASE}/fuel?q=nafta+95`);
    const data = await res.json();
    state.fuel = data.results || [];
    renderFuelList(state.fuel);
  } catch (e) {
    renderFuelList([]);
  }
}

async function search(q) {
  if (!q) {
    loadPromos();
    return;
  }
  
  const grid = document.getElementById("promoGrid");
  grid.innerHTML = `<div class="loading"><div class="spinner"></div>Buscando...</div>`;
  
  try {
    const res = await fetch(`${API_BASE}/query?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderPromoGrid(data.results || []);
  } catch (e) {
    grid.innerHTML = `<div class="empty"><p>Error</p></div>`;
  }
}

function setupCategories() {
  const chips = document.querySelectorAll(".category-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      state.currentCategory = chip.dataset.cat;
      search(state.currentCategory);
    });
  });
}

function setupSearch() {
  const input = document.getElementById("searchInput");
  let debounce;
  
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      clearTimeout(debounce);
      const q = input.value.trim();
      search(q);
    }
  });
  
  input.addEventListener("input", e => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      const q = input.value.trim();
      if (q.length >= 2) search(q);
    }, 400);
  });
}

function init() {
  setupCategories();
  setupSearch();
  loadPromos();
  loadFuel();
}

document.addEventListener("DOMContentLoaded", init);