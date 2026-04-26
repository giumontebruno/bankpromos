const API_BASE = 'https://bankpromos-production.up.railway.app';

let currentTab = 'promos';

async function apiFetch(path, params = {}) {
    const url = new URL(`${API_BASE}${path}`);
    Object.entries(params).forEach(([k, v]) => {
        if (v) url.searchParams.set(k, v);
    });
    try {
        const res = await fetch(url.toString());
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('API error:', e);
        return null;
    }
}

function formatCurrency(num) {
    if (!num) return '-';
    return new Intl.NumberFormat('es-PY', {
        style: 'currency',
        currency: 'PYG',
        maximumFractionDigits: 0
    }).format(num);
}

function getBankLabel(bankId) {
    const map = {
        'py_ueno': 'Ueno',
        'py_itau': 'Itaú',
        'py_continental': 'Continental',
        'py_sudameris': 'Sudameris',
        'py_bnf': 'BNF'
    };
    return map[bankId] || bankId.replace('py_', '').toUpperCase();
}

function renderLoading(container) {
    container.innerHTML = '<div class="loading-state">Buscando...</div>';
}

function renderEmpty(container, message = 'No hay resultados') {
    container.innerHTML = `<div class="empty-state">${message}</div>`;
}

function renderError(container, message = 'Error al cargar datos') {
    container.innerHTML = `<div class="error-state">${message}</div>`;
}

function renderPromoCard(promo) {
    const bank = getBankLabel(promo.bank_id);
    const merchant = promo.merchant_name || promo.title;
    const benefit = promo.discount_percent
        ? `${promo.discount_percent}% ${promo.benefit_type || 'reintegro'}`
        : promo.installment_count
            ? `${promo.installment_count} cuotas`
            : promo.benefit_type || '-';
    const days = promo.valid_days?.length
        ? promo.valid_days.map(d => d.charAt(0).toUpperCase() + d.slice(1)).join(', ')
        : 'Todos los días';
    const isCurated = promo.result_quality_label === 'CURATED';
    const qualityClass = isCurated ? 'curated' : '';
    const qualityLabel = isCurated ? 'Curado' : 'Scraped';

    return `
        <div class="card">
            <div class="card-header">
                <span class="card-merchant">${merchant}</span>
                <span class="badge badge-bank">${bank}</span>
            </div>
            ${promo.title && promo.title !== merchant ? `<div class="card-detail">${promo.title}</div>` : ''}
            <div class="card-meta">
                <span class="badge badge-benefit">${benefit}</span>
                ${promo.category ? `<span class="badge badge-category">${promo.category}</span>` : ''}
                <span class="badge badge-quality ${qualityClass}">${qualityLabel}</span>
            </div>
            <div class="card-detail">Días: ${days}</div>
        </div>
    `;
}

function renderFuelRow(item, rank) {
    const bank = getBankLabel(item.bank_id);
    const isBest = rank === 1;
    const discount = item.discount_percent ? `${item.discount_percent}%` : '-';

    return `
        <tr class="${isBest ? 'best' : ''}">
            <td class="fuel-rank">${rank}</td>
            <td>${bank}</td>
            <td>${item.emblem || '-'}</td>
            <td>${item.fuel_type?.replace('_', ' ') || '-'}</td>
            <td>${formatCurrency(item.base_price)}</td>
            <td class="fuel-discount">${discount}</td>
            <td class="fuel-final">${formatCurrency(item.estimated_final_price)}</td>
        </tr>
    `;
}

async function searchPromos() {
    const query = document.getElementById('promo-query').value.trim();
    const container = document.getElementById('promo-results');
    renderLoading(container);

    const data = await apiFetch('/query', { q: query });
    if (!data) {
        renderError(container, 'No se pudo conectar al servidor');
        return;
    }

    const promos = data.results || [];
    if (promos.length === 0) {
        renderEmpty(container, 'No hay promociones para esta búsqueda');
        return;
    }

    container.innerHTML = promos.map(renderPromoCard).join('');
}

async function searchFuel() {
    const query = document.getElementById('fuel-query').value.trim();
    const container = document.getElementById('fuel-results');
    renderLoading(container);

    const data = await apiFetch('/fuel', { q: query });
    if (!data) {
        renderError(container, 'No se pudo conectar al servidor');
        return;
    }

    const matches = data.results || [];
    if (matches.length === 0) {
        renderEmpty(container, 'No hay resultados de combustible');
        return;
    }

    let html = `
        <div class="fuel-table">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Banco</th>
                        <th>Estación</th>
                        <th>Tipo</th>
                        <th>Base</th>
                        <th>Dto %</th>
                        <th>Final</th>
                    </tr>
                </thead>
                <tbody>
    `;
    matches.forEach((m, i) => {
        html += renderFuelRow(m, i + 1);
    });
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

async function loadStatus() {
    const container = document.getElementById('status-info');
    const data = await apiFetch('/data-status');
    if (!data) {
        container.innerHTML = '<span class="error-state">Estado no disponible</span>';
        return;
    }

    const promosTotal = data.promotions_count || 0;
    const fuelCount = data.fuel_count || 0;
    const curated = data.curated_count || 0;
    const scraped = data.scraped_count || 0;
    const promoDate = data.latest_promotion_inserted_at
        ? new Date(data.latest_promotion_inserted_at).toLocaleDateString('es-PY')
        : '-';
    const fuelDate = data.latest_fuel_inserted_at
        ? new Date(data.latest_fuel_inserted_at).toLocaleDateString('es-PY')
        : '-';

    container.innerHTML = `
        <div class="status-item">
            <span class="status-value">${promosTotal}</span>
            <span>Promos</span>
        </div>
        <div class="status-item">
            <span class="status-value">${fuelCount}</span>
            <span>Fuel</span>
        </div>
        <div class="status-item">
            <span class="status-value">${curated}</span>
            <span>Curadas</span>
        </div>
        <div class="status-item">
            <span class="status-value">${promoDate}</span>
            <span>Actualizado</span>
        </div>
    `;
}

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tab);
    });
    document.querySelectorAll('.tab-content').forEach(c => {
        c.classList.toggle('active', c.id === `${tab}-section`);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tab').forEach(t => {
        t.addEventListener('click', () => switchTab(t.dataset.tab));
    });

    document.getElementById('promo-search-btn').addEventListener('click', searchPromos);
    document.getElementById('promo-query').addEventListener('keypress', e => {
        if (e.key === 'Enter') searchPromos();
    });

    document.getElementById('fuel-search-btn').addEventListener('click', searchFuel);
    document.getElementById('fuel-query').addEventListener('keypress', e => {
        if (e.key === 'Enter') searchFuel();
    });

    loadStatus();
});