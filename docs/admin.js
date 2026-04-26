const API = 'https://bankpromos-production.up.railway.app';

async function apiCall(path, options = {}) {
    const res = await fetch(`${API}${path}`, options);
    return res.json();
}

async function loadAdminStats() {
    const statsDiv = document.getElementById('admin-stats');
    const curated = await apiCall('/admin/curated');
    const summary = await apiCall('/summary');
    const status = await apiCall('/data-status');
    
    const curatedCount = curated?.total || 0;
    const activeToday = summary?.active_today_count || 0;
    const topCats = summary?.top_categories?.join(', ') || '-';
    const promoDate = status?.latest_promotion_inserted_at 
        ? new Date(status.latest_promotion_inserted_at).toLocaleDateString('es-PY') 
        : '-';
    
    statsDiv.innerHTML = `
        <div style="display:flex;gap:1.5rem;flex-wrap:wrap;">
            <div><strong>${curatedCount}</strong> curadas</div>
            <div><strong>${activeToday}</strong> activas hoy</div>
            <div>Top: ${topCats}</div>
            <div>Actualizado: ${promoDate}</div>
        </div>
    `;
}

async function loadAnalyticsStats() {
    const container = document.getElementById('admin-analytics');
    const data = await apiCall('/analytics/summary');
    if (!data) {
        container.innerHTML = '<span>Analytics no disponible</span>';
        return;
    }
    const today = data.today || {};
    container.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;">
            <div><strong>${today.searches || 0}</strong> búsquedas</div>
            <div><strong>${today.fuel_searches || 0}</strong> combustible</div>
            <div><strong>${today.today_views || 0}</strong> hoy</div>
            <div><strong>${today.personalized_views || 0}</strong> personalizado</div>
        </div>
        ${today.top_queries?.length ? `<div style="margin-top:0.5rem;"><small>Top: ${today.top_queries.slice(0,3).map(q => q.query).join(', ')}</small></div>` : ''}
    `;
}

async function loadCurated() {
    const data = await apiCall('/admin/curated');
    const list = document.getElementById('curated-list');
    
    if (!data.results || data.results.length === 0) {
        list.innerHTML = '<div class="admin-item">No hay promos curadas</div>';
        return;
    }

    list.innerHTML = data.results.map(p => `
        <div class="admin-item">
            <span>${p.id || '---'}</span>
            <span>${p.merchant_name} - ${p.title}</span>
            <span>${p.discount_percent || '-'}</span>
            <button class="btn-small btn-edit" onclick="editPromo('${p.id}')">Edit</button>
            <button class="btn-small btn-delete" onclick="deletePromo('${p.id}')">Delete</button>
        </div>
    `).join('');
}

async function addPromo() {
    const promo = {
        bank_id: document.getElementById('bank_id').value,
        merchant_name: document.getElementById('merchant_name').value,
        title: document.getElementById('title').value,
        category: document.getElementById('category').value,
        discount_percent: document.getElementById('discount_percent').value,
        benefit_type: document.getElementById('benefit_type').value,
        valid_days: document.getElementById('valid_days').value.split(',').map(d => d.trim()),
        source_url: document.getElementById('source_url').value,
        raw_text: document.getElementById('raw_text').value,
    };

    const result = await apiCall('/admin/curated', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(promo),
    });

    if (result.success) {
        document.querySelectorAll('.admin-form input').forEach(i => i.value = '');
        loadCurated();
    } else {
        alert('Error: ' + (result.detail || 'Unknown error'));
    }
}

async function editPromo(id) {
    alert('Editar no implementado aún. Usa directamente la API.');
}

async function deletePromo(id) {
    if (!confirm('¿Eliminar esta promo?')) return;
    
    const result = await apiCall(`/admin/curated/${id}`, {
        method: 'DELETE',
    });

    if (result.success) {
        loadCurated();
    } else {
        alert('Error: ' + (result.detail || 'Unknown error'));
    }
}

async function loadCorrections() {
    const data = await apiCall('/admin/corrections');
    const list = document.getElementById('corrections-list');
    
    if (!data.results || data.results.length === 0) {
        list.innerHTML = '<div class="review-item">No hay correcciones guardadas</div>';
        return;
    }

    list.innerHTML = data.results.map(c => `
        <div class="review-item" id="correction-${c.id}">
            <div class="review-item-header">
                <span>${c.source_bank}</span>
                <span>${c.source_file}</span>
                <span>${c.apply_to_future ? 'Auto' : 'Manual'}</span>
            </div>
            <div class="review-item-body">
                <div class="review-field"><strong>Detectado:</strong> ${(c.original_detected_merchant || '-')}</div>
                <div class="review-field"><strong>Corregido merchant:</strong> ${c.corrected_merchant_name || '-'}</div>
                <div class="review-field"><strong>Corregido categoría:</strong> ${c.corrected_category || '-'}</div>
                <div class="review-field"><strong>Corregido descuento:</strong> ${c.corrected_discount_percent || '-'}</div>
                <div class="review-field"><strong>Corregido cap:</strong> ${c.corrected_cap_amount || '-'}</div>
                <div class="review-text"><strong>Texto original:</strong> ${(c.original_detected_text || '').slice(0, 100)}</div>
            </div>
            <div class="review-actions">
                <button class="btn-small btn-edit" onclick="editCorrection('${c.id}')">Editar</button>
                <button class="btn-small btn-delete" onclick="deleteCorrection('${c.id}')">Eliminar</button>
            </div>
        </div>
    `).join('');
}

async function loadReviewItems() {
    const data = await apiCall('/admin/review-items');
    const container = document.getElementById('review-items-container');
    const list = document.getElementById('review-list');
    
    if (!data.results || data.results.length === 0) {
        container.style.display = 'block';
        list.innerHTML = '<div class="review-item">No hay items para revisar. Ejecuta una extracción de PDFs primero.</div>';
        return;
    }

    container.style.display = 'block';
    list.innerHTML = data.results.map((item, idx) => `
        <div class="review-item" id="review-${idx}">
            <div class="review-item-header">
                <span class="review-bank">${item.bank}</span>
                <span class="review-file">${item.source_file}</span>
                <span class="review-reason">${item.reason || '-'}</span>
            </div>
            <div class="review-item-body">
                <div class="review-text"><strong>Texto detectado:</strong> ${(item.detected_text || '').slice(0, 200)}</div>
                <div class="review-field"><strong>Merchant:</strong> <input type="text" id="r-merchant-${idx}" value="${item.detected_merchant || ''}" placeholder="merchant"></div>
                <div class="review-field"><strong>Categoría:</strong> <input type="text" id="r-category-${idx}" value="${item.detected_category || ''}" placeholder="category"></div>
                <div class="review-field"><strong>Descuento %:</strong> <input type="text" id="r-discount-${idx}" value="${item.detected_discount || ''}" placeholder="discount"></div>
                <div class="review-field"><strong>Cap:</strong> <input type="text" id="r-cap-${idx}" value="${item.detected_cap || ''}" placeholder="cap amount"></div>
                <div class="review-field"><strong>Cuotas:</strong> <input type="text" id="r-installments-${idx}" value="${item.detected_installments || ''}" placeholder="installments"></div>
                <div class="review-field"><strong>Días:</strong> <input type="text" id="r-days-${idx}" value="${(item.detected_days || []).join(',')}" placeholder="lunes,martes,..."></div>
                <div class="review-field"><strong>Método pago:</strong> <input type="text" id="r-payment-${idx}" value="${item.detected_payment_method || ''}" placeholder="Visa,Debito,..."></div>
                <div class="review-field"><strong>Condiciones:</strong> <input type="text" id="r-conditions-${idx}" value="${item.detected_conditions || ''}" placeholder="conditions"></div>
            </div>
            <div class="review-actions">
                <button class="btn-small" style="background:#22c55e;color:white;" onclick="saveCorrection(${idx}, ${JSON.stringify(item).replace(/"/g, '&quot;')})">Guardar Corrección</button>
                <button class="btn-small btn-edit" onclick="skipReview(${idx})">Omitir</button>
            </div>
        </div>
    `).join('');
}

async function saveCorrection(idx, item) {
    const merchant = document.getElementById(`r-merchant-${idx}`).value.trim();
    const category = document.getElementById(`r-category-${idx}`).value.trim();
    const discount = document.getElementById(`r-discount-${idx}`).value.trim();
    const cap = document.getElementById(`r-cap-${idx}`).value.trim();
    const installments = document.getElementById(`r-installments-${idx}`).value.trim();
    const days = document.getElementById(`r-days-${idx}`).value.trim();
    const payment = document.getElementById(`r-payment-${idx}`).value.trim();
    const conditions = document.getElementById(`r-conditions-${idx}`).value.trim();

    const correction = {
        source_bank: item.bank,
        source_type: 'pdf',
        source_file: item.source_file,
        source_page: item.page || 0,
        original_detected_text: item.detected_text || '',
        original_detected_merchant: item.detected_merchant || '',
        corrected_merchant_name: merchant || null,
        corrected_category: category || null,
        corrected_discount_percent: discount ? parseFloat(discount) : null,
        corrected_cap_amount: cap ? parseFloat(cap) : null,
        corrected_installment_count: installments ? parseInt(installments) : null,
        corrected_valid_days: days ? days.split(',').map(d => d.trim()).filter(d => d) : [],
        corrected_payment_method: payment || null,
        corrected_conditions_text: conditions || null,
        apply_to_future: true,
        source_crop_path: item.crop_path || null,
    };

    const result = await apiCall('/admin/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(correction),
    });

    if (result.success) {
        document.getElementById(`review-${idx}`).style.opacity = '0.5';
        document.getElementById(`review-${idx}`).style.pointerEvents = 'none';
    } else {
        alert('Error: ' + (result.detail || 'Unknown error'));
    }
}

function skipReview(idx) {
    const el = document.getElementById(`review-${idx}`);
    if (el) {
        el.style.opacity = '0.4';
        el.style.pointerEvents = 'none';
    }
}

async function editCorrection(id) {
    alert('Editar corrección: usa DELETE + POST con los valores corregidos');
}

async function deleteCorrection(id) {
    if (!confirm('¿Eliminar esta corrección?')) return;
    
    const result = await apiCall(`/admin/corrections/${id}`, {
        method: 'DELETE',
    });

    if (result.success) {
        loadCorrections();
    } else {
        alert('Error: ' + (result.detail || 'Unknown error'));
    }
}

async function addCorrection() {
    const correction = {
        source_bank: document.getElementById('corr_bank').value,
        source_type: document.getElementById('corr_type').value || 'pdf',
        source_file: document.getElementById('corr_file').value,
        source_page: parseInt(document.getElementById('corr_page').value) || 0,
        original_detected_text: document.getElementById('corr_orig_text').value,
        original_detected_merchant: document.getElementById('corr_orig_merchant').value,
        corrected_merchant_name: document.getElementById('corr_merchant').value || null,
        corrected_category: document.getElementById('corr_category').value || null,
        corrected_discount_percent: document.getElementById('corr_discount').value ? parseFloat(document.getElementById('corr_discount').value) : null,
        corrected_cap_amount: document.getElementById('corr_cap').value ? parseFloat(document.getElementById('corr_cap').value) : null,
        corrected_installment_count: document.getElementById('corr_installments').value ? parseInt(document.getElementById('corr_installments').value) : null,
        corrected_valid_days: document.getElementById('corr_days').value ? document.getElementById('corr_days').value.split(',').map(d => d.trim()).filter(d => d) : [],
        corrected_payment_method: document.getElementById('corr_payment').value || null,
        corrected_conditions_text: document.getElementById('corr_conditions').value || null,
        apply_to_future: document.getElementById('corr_future').checked,
    };

    const result = await apiCall('/admin/corrections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(correction),
    });

    if (result.success) {
        document.querySelectorAll('.corr-form input').forEach(i => i.value = '');
        loadCorrections();
        alert('Corrección guardada');
    } else {
        alert('Error: ' + (result.detail || 'Unknown error'));
    }
}

async function loadAll() {
    await loadAdminStats();
    await loadAnalyticsStats();
    await loadCurated();
    await loadCorrections();
    await loadReviewItems();
}

if (document.getElementById('curated-list')) {
    loadAll();
}