const API_BASE = "https://bankpromos-production.up.railway.app";

const promoQuery = document.getElementById("promoQuery");
const promoSearchBtn = document.getElementById("promoSearchBtn");
const promoResults = document.getElementById("promoResults");
const promoState = document.getElementById("promoState");

const fuelQuery = document.getElementById("fuelQuery");
const fuelSearchBtn = document.getElementById("fuelSearchBtn");
const fuelResults = document.getElementById("fuelResults");
const fuelState = document.getElementById("fuelState");

const promosCount = document.getElementById("promosCount");
const fuelCount = document.getElementById("fuelCount");
const curatedCount = document.getElementById("curatedCount");
const scrapedCount = document.getElementById("scrapedCount");

function setState(el, text, isError = false) {
  el.textContent = text;
  el.className = isError ? "state error" : "state";
}

function formatGs(value) {
  if (value == null) return "-";
  return new Intl.NumberFormat("es-PY").format(value) + " Gs.";
}

function renderPromoCards(items) {
  if (!items.length) {
    promoResults.innerHTML = "";
    setState(promoState, "No se encontraron promociones.");
    return;
  }

  setState(promoState, `${items.length} resultados encontrados.`);
  promoResults.innerHTML = items.map(item => `
    <article class="card">
      <h3>${item.title ?? "-"}</h3>
      <div class="meta">
        <span class="badge bank">${item.bank_id ?? "-"}</span>
        <span class="badge">${item.category ?? "-"}</span>
        <span class="badge">${item.benefit_type ?? "-"}</span>
        <span class="badge source">${item.result_quality_label ?? "-"}</span>
      </div>
      <p><strong>Comercio:</strong> ${item.merchant_name ?? "-"}</p>
      <p><strong>Descuento:</strong> ${item.discount_percent ?? "-"}%</p>
      <p><strong>Días:</strong> ${(item.valid_days || []).join(", ") || "-"}</p>
    </article>
  `).join("");
}

function renderFuelTable(items) {
  if (!items.length) {
    fuelResults.innerHTML = "";
    setState(fuelState, "No se encontraron resultados para combustible.");
    return;
  }

  setState(fuelState, `${items.length} resultados encontrados.`);

  const rows = items.map((item, idx) => `
    <tr class="${idx === 0 ? "fuel-best" : ""}">
      <td>${idx + 1}</td>
      <td>${item.bank_id ?? "-"}</td>
      <td>${item.emblem ?? "-"}</td>
      <td>${item.fuel_type ?? "-"}</td>
      <td>${formatGs(item.base_price)}</td>
      <td>${item.discount_percent ?? "-"}%</td>
      <td>${formatGs(item.estimated_final_price)}</td>
      <td>${formatGs(item.savings)}</td>
      <td>${(item.valid_days || []).join(", ") || "-"}</td>
    </tr>
  `).join("");

  fuelResults.innerHTML = `
    <table class="fuel-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Banco</th>
          <th>Emblema</th>
          <th>Tipo</th>
          <th>Base</th>
          <th>%</th>
          <th>Final</th>
          <th>Ahorro</th>
          <th>Días</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function loadStatus() {
  try {
    const res = await fetch(`${API_BASE}/data-status`);
    const data = await res.json();
    promosCount.textContent = data.promotions_count ?? "-";
    fuelCount.textContent = data.fuel_count ?? "-";
    curatedCount.textContent = data.curated_count ?? "-";
    scrapedCount.textContent = data.scraped_count ?? "-";
  } catch {
    promosCount.textContent = "-";
    fuelCount.textContent = "-";
    curatedCount.textContent = "-";
    scrapedCount.textContent = "-";
  }
}

async function searchPromos() {
  const q = promoQuery.value.trim();
  if (!q) {
    setState(promoState, "Escribí una búsqueda.");
    return;
  }

  setState(promoState, "Buscando...");
  promoResults.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/query?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderPromoCards(data.results || []);
  } catch {
    setState(promoState, "No se pudo consultar la API.", true);
  }
}

async function searchFuel() {
  const q = fuelQuery.value.trim();
  if (!q) {
    setState(fuelState, "Escribí una búsqueda.");
    return;
  }

  setState(fuelState, "Buscando...");
  fuelResults.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/fuel?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    renderFuelTable(data.results || []);
  } catch {
    setState(fuelState, "No se pudo consultar la API.", true);
  }
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  const promoTab = document.getElementById("promosTab");
  const fuelTab = document.getElementById("fuelTab");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");

      if (tab.dataset.tab === "promos") {
        promoTab.classList.add("active");
        fuelTab.classList.remove("active");
      } else {
        fuelTab.classList.add("active");
        promoTab.classList.remove("active");
      }
    });
  });
}

promoSearchBtn.addEventListener("click", searchPromos);
fuelSearchBtn.addEventListener("click", searchFuel);
promoQuery.addEventListener("keydown", e => {
  if (e.key === "Enter") searchPromos();
});
fuelQuery.addEventListener("keydown", e => {
  if (e.key === "Enter") searchFuel();
});

setupTabs();
loadStatus();
