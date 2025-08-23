Railway deployment notes

1) Start command
- Railway detects `Procfile`. The Procfile included in the repo uses:
  web: uvicorn asgi:application --host 0.0.0.0 --port $PORT --proxy-headers --loop asyncio

2) Required environment variables (examples)
- DATABASE_URL=postgresql://user:pass@host:5432/dbname
- JWT_SECRET=your_jwt_secret_here
- JWT_ALGORITHM=HS256
- CORS_ORIGINS=* (or list)
- OTHER secrets: SMTP_*, TELEGRAM_BOT_TOKEN, etc.

3) Websockets
- Railway supports WebSockets on the web service. Keep `asgi:application` (our `asgi.py`) as the app, and uvicorn will handle websocket connections.
- Ensure `--proxy-headers` is set so remote IPs/headers are forwarded correctly.

4) Database migrations
- In production do not rely on `ModelBase.metadata.create_all` as the only migration strategy. Prefer Alembic.
- For quick deploys you can keep create_all, but for safety run migrations as a Railway "Run Migration" job or through a deployment step.

5) Health check
- Use `GET /health` for Railway health checks.

6) Logs & monitoring
- Railway shows stdout/stderr logs. Configure structured logs if needed.

7) Extra notes
- If you use a managed Postgres plugin on Railway, set `DATABASE_URL` from the plugin.
- For zero-downtime or scale, set `workers` via `--workers` if needed but be mindful of memory.

Example quick deployment steps on Railway UI
- Create a new project, connect repo.
- Set environment variables in the Railway project's settings.
- Deploy — Railway will run the Procfile command.
- (Optional) Run DB migrations via Railway "Run" command: `python -m alembic upgrade head` (if Alembic configured).

If you want, I can:
- Add an Alembic scaffold to the repo and a sample migration.
- Add a small deploy checklist customized to your Railway project (including exact env var names from `config.py`).
