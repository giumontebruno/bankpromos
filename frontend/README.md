# Bank Promos PY - Frontend

Frontend estático para consultar promociones bancarias y ahorro en combustible en Paraguay.

## Ejecutar localmente

```bash
cd frontend
python -m http.server 8080
# Abrir http://localhost:8080
```

O simplemente abre `index.html` directamente en el navegador.

## Desplegar como sitio estático

Este frontend es HTML/CSS/JS puro sin build step. Puedes desplegarlo en:

- **Netlify**: Arrastra la carpeta `frontend/`
- **Vercel**: `vercel --prod frontend/`
- **GitHub Pages**: Sube los archivos o usa GitHub Actions
- **Railway**: Agrega un servicio estático pointing a `frontend/`

## Cambiar API base URL

Edita `app.js` línea 2:

```javascript
const API_BASE = 'https://tu-api-production.up.railway.app';
```

## Estructura

```
frontend/
  index.html   # Estructura HTML
  styles.css   # Estilos (mobile-first)
  app.js       # Lógica (fetch al API)
  README.md    # Este archivo
```

## API Endpoints usados

| Endpoint | Descripción |
|----------|-------------|
| `GET /query?q=...` | Buscar promociones |
| `GET /fuel?q=...` | Mejor ahorro en combustible |
| `GET /data-status` | Estado de datos (conteos, fechas) |