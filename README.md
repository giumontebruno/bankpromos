# Bank Promos PY API

Scraper de promociones y beneficios bancarios de Paraguay.

## Configuración

```bash
pip install -e ".[dev]"
python -m playwright install chromium
```

## Uso CLI

```bash
# Ver bancos disponibles
python -m bankpromos list

# Collect data (all scrapers, normalize, dedupe, score, persist)
python -m bankpromos collect --all --force

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
| BANKPROMOS_DISABLE_LIVE_SCRAPING | false | Disable scrapers (Railway) |
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

## Data Pipeline

Scraping runs in GitHub Actions, Railway serves cached data only.

### How It Works

1. GitHub Actions runs every 6 hours via `collect-data.yml`
2. Scrapers fetch fresh data from bank websites
3. Data is normalized, deduplicated, and scored
4. SQLite database (`data/bankpromos.db`) is committed to repo
5. Railway pulls updated database and serves it via API

### Why This Architecture

Railway containers cannot access external bank websites. Scraping locally and committing the database to GitHub solves this limitation.

### Manual Trigger

Go to **Actions > Collect Bank Promotions Data > Run workflow** to trigger scraping manually.

### Railway Configuration

Set environment variable:
```
BANKPROMOS_DISABLE_LIVE_SCRAPING=true
```

This ensures Railway:
- Loads data from SQLite only
- Does NOT run Playwright scrapers
- Responds quickly with cached data

## Railway Deployment

### Quick Deploy

```bash
railway init --name bankpromos
railway up
railway domain
```

### Configuration

Railway automatically provides the `PORT` environment variable. Do not hardcode it.

**Dockerfile requirements:**
- Use `${PORT:-8000}` in CMD
- Do not set `ENV PORT=8000` (let Railway provide it)

**Health check:**
- Path: `/health`
- The app logs port on startup: `Starting Bank Promos PY API on port {port}...`

**Environment variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| BANKPROMOS_DB_PATH | data/bankpromos.db | SQLite path |
| BANKPROMOS_DISABLE_LIVE_SCRAPING | true | Required for Railway |
| BANKPROMOS_CACHE_HOURS | 12 | Cache hours |
| BANKPROMOS_DEBUG | false | Debug mode |

**Required:**
- `PORT` - Provided by Railway automatically

### Troubleshooting

```bash
# View logs
railway logs --service <service-id>

# Redeploy
railway deployment redeploy --service <service-id> --yes
```

## GitHub Actions + Koyeb Deployment (Legacy)

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