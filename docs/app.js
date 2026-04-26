const API_BASE = "https://bankpromos-production.up.railway.app";

const CATEGORIES = [
  { id: "Combustible", icon: "⛽" },
  { id: "Supermercados", icon: "🛒" },
  { id: "Gastronomía", icon: "🍔" },
  { id: "Tecnología", icon: "📱" },
  { id: "Indumentaria", icon: "👕" },
  { id: "Salud", icon: "💊" },
  { id: "Viajes", icon: "✈️" },
  { id: "Belleza", icon: "💅" },
];

const state = {
  currentView: "today",
  promos: [],
  fuelResults: [],
  promosCount: 0,
  bestCategory: "-",
  bestFuel: "-",
  lastUpdate: "-",
  searchQuery: "",
};

function getInitials(name) {
  if (!name) return "?";
  const words = name.trim().split(" ").filter(w => w.length > 0);
  if (words.length === 1) return words[0].substring(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function getBankClass(bank) {
  if (!bank) return "";
  const bankLower = bank.toLowerCase();
  if (bankLower.includes("itau")) return "bank-itau";
  if (bankLower.includes("ueno")) return "bank-ueno";
  if (bankLower.includes("sudameris")) return "bank-sudameris";
  if (bankLower.includes("continental")) return "bank-continental";
  if (bankLower.includes("bnf")) return "bank-bnf";
  return "";
}

function renderPromoCard(promo) {
  const initials = getInitials(promo.display_name);
  const bankClass = getBankClass(promo.bank_id);
  const discount = promo.highlight_value || "-";
  const discountLabel = promo.highlight_type || "";

  return `
    <article class="promo-card" data-promo='${JSON.stringify(promo).replace(/'/g, "&#39;")}'>
      <div class="promo-card-header">
        <div class="promo-logo ${bankClass}">${initials}</div>
        <div class="promo-info">
          <h3 class="promo-merchant">${promo.display_name || "-"}</h3>
          <p class="promo-category">${promo.category || "-"}</p>
        </div>
      </div>
      <div class="promo-highlight">
        <span class="promo-discount">${discount}</span>
        <span class="promo-discount-label">${discountLabel}</span>
      </div>
      <div class="promo-meta">
        <span class="promo-badge bank">${promo.bank_id || "-"}</span>
        ${promo.valid_days_display ? `<span class="promo-badge days">${promo.valid_days_display}</span>` : ""}
        ${promo.cap_display ? `<span class="promo-badge cap">${promo.cap_display}</span>` : ""}
        ${promo.result_quality_label ? `<span class="promo-badge quality">${promo.result_quality_label}</span>` : ""}
      </div>
      ${promo.conditions_short ? `<p class="promo-conditions">${promo.conditions_short}</p>` : ""}
    </article>
  `;
}

function renderPromoGrid(promos, containerId = "promoGrid") {
  const container = document.getElementById(containerId);
  if (!promos.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <h3 class="empty-state-title">Sin resultados</h3>
        <p>No se encontraron promociones.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = promos.map(renderPromoCard).join("");
  document.getElementById("promoCountLabel").textContent = `${promos.length} promos encontradas`;
}

function renderFuelTable(items) {
  const container = document.getElementById("fuelResults");
  if (!items.length) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⛽</div>
        <h3 class="empty-state-title">Sin resultados</h3>
        <p>No se encontraron resultados para combustible.</p>
      </div>
    `;
    return;
  }

  const rows = items.slice(0, 5).map((item, idx) => {
    const isBest = idx === 0;
    return `
      <tr class="${isBest ? "best" : ""}">
        <td>${isBest ? "★" : idx + 1}</td>
        <td>${item.bank_id}</td>
        <td>${item.emblem || "-"}</td>
        <td>${item.fuel_type}</td>
        <td>${formatGs(item.base_price)}</td>
        <td class="discount">${item.discount_percent}%</td>
        <td class="savings">${formatGs(item.estimated_final_price)}</td>
        <td>${formatGs(item.savings)}</td>
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div class="fuel-card">
      <table class="fuel-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Banco</th>
            <th>Estación</th>
            <th>Tipo</th>
            <th>Base</th>
            <th>%</th>
            <th>Final</th>
            <th>Ahorro</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

function formatGs(value) {
  if (value == null) return "-";
  return new Intl.NumberFormat("es-PY").format(value) + " Gs.";
}

function formatDate(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  return date.toLocaleDateString("es-PY", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

async function loadToday() {
  try {
    const res = await fetch(`${API_BASE}/today`);
    const data = await res.json();
    state.promos = data.results || [];
    state.promosCount = state.promos.length;
    renderPromoGrid(state.promos);
    document.getElementById("promosCount").textContent = state.promosCount;
    
    const categories = {};
    state.promos.forEach(p => {
      const cat = p.category || "Otro";
      categories[cat] = (categories[cat] || 0) + 1;
    });
    const bestCat = Object.entries(categories).sort((a, b) => b[1] - a[1])[0];
    state.bestCategory = bestCat ? bestCat[0] : "-";
    document.getElementById("bestCategory").textContent = state.bestCategory;
    
    const now = new Date().toISOString();
    state.lastUpdate = formatDate(now);
    document.getElementById("lastUpdate").textContent = state.lastUpdate;
  } catch (err) {
    console.error("Failed to load today:", err);
    renderPromoGrid([]);
  }
}

async function loadBestFuel() {
  try {
    const res = await fetch(`${API_BASE}/fuel?q=nafta+95`);
    const data = await res.json();
    state.fuelResults = data.results || [];
    renderFuelTable(state.fuelResults);
    
    if (state.fuelResults.length > 0) {
      const best = state.fuelResults[0];
      state.bestFuel = `${best.discount_percent}% en ${best.emblem}`;
      document.getElementById("bestFuel").textContent = state.bestFuel;
    }
  } catch (err) {
    console.error("Failed to load fuel:", err);
    renderFuelTable([]);
  }
}

async function searchQuery(q) {
  if (!q.trim()) return;
  
  const grid = document.getElementById("promoGrid");
  grid.innerHTML = `<div class="loading"><div class="spinner"></div>Buscando...</div>`;
  
  try {
    const res = await fetch(`${API_BASE}/query?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderPromoGrid(data.results || []);
  } catch (err) {
    console.error("Search failed:", err);
    grid.innerHTML = `<div class="empty-state"><p>Error al buscar.</p></div>`;
  }
}

function setupNavigation() {
  const navItems = document.querySelectorAll(".nav-item[data-view]");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      navItems.forEach(n => n.classList.remove("active"));
      item.classList.add("active");
      state.currentView = item.dataset.view;
      
      if (state.currentView === "today") {
        loadToday();
      } else if (state.currentView === "fuel") {
        loadBestFuel();
      } else if (state.currentView === "search") {
        document.getElementById("globalSearch").focus();
      }
    });
  });
}

function setupCategoryChips() {
  const chips = document.querySelectorAll(".category-chip");
  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      chips.forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      const category = chip.dataset.category;
      searchQuery(category);
    });
  });
}

function setupSearch() {
  const searchInput = document.getElementById("globalSearch");
  searchInput.addEventListener("keydown", e => {
    if (e.key === "Enter") {
      const q = searchInput.value.trim();
      if (q) {
        searchQuery(q);
        document.querySelector('.nav-item[data-view="search"]')?.click();
      }
    }
  });
}

function init() {
  setupNavigation();
  setupCategoryChips();
  setupSearch();
  loadToday();
  loadBestFuel();
}

document.addEventListener("DOMContentLoaded", init);