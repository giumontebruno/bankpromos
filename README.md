# Bank Promos PY API

Scraper de promociones y beneficios bancarios de Paraguay.

## Configuración

```bash
pip install -e .
```

## Uso CLI

```bash
# Ver bancos disponibles
python -m bankpromos list

# Collect data
python -m bankpromos collect --all

# Query promotions
python -m bankpromos query "combustible" --all

# Query fuel
python -m bankpromos fuel "nafta 95" --all

# Start API server
uvicorn bankpromos.api:app --host 0.0.0.0 --port 8000
```

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| PORT | 8000 | API port |
| BANKPROMOS_DB_PATH | data/bankpromos.db | SQLite path |
| BANKPROMOS_CACHE_HOURS | 12 | Cache hours |
| BANKPROMOS_DEBUG | false | Debug mode |
| BANKPROMOS_CORS_ORIGINS | * | CORS origins |

## API Endpoints

- GET /health - Health check
- GET /cache - Cache status
- GET /banks - List banks
- POST /collect - Collect data
- GET /query?q=... - Query promotions
- GET /fuel?q=... - Query fuel prices
- GET /fuel-prices - All fuel prices
- POST /collect-fuel - Collect fuel data

## GitHub Actions + Koyeb Deployment

### Required Secrets

Configure these in GitHub repository settings:

- `KOYOEB_API_TOKEN` - Koyeb API token
- `KOYOEB_APP_NAME` - Your Koyeb app name
- `KOYOEB_SERVICE_NAME` - Your Koyeb service name

### What Happens

On **push to main**:
1. CI workflow runs tests
2. If tests pass, deploy workflow triggers
3. API service updates in Koyeb

### Deployment Verification

Check these endpoints first:

```bash
curl https://your-app.koyeb.app/health
# Expected: {"status":"ok"}

curl https://your-app.koyeb.app/banks
# Expected: List of banks

curl https://your-app.koyeb.app/cache
# Expected: Cache status
```

### Rollback

If deployment fails:
```bash
git revert HEAD
git push origin main
```

Or push previous commit:
```bash
git checkout main
git push origin main~1:main --force
```