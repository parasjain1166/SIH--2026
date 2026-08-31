# Deploy RailBlock AI on Render

This package is ready to deploy as a Render **Web Service**.

## 1) Upload the project to GitHub

Create a new GitHub repository (for example `railblock-ai`) and upload **the contents of this folder**, not the ZIP itself.

Important files that must be at the repository root:

- `render.yaml`
- `requirements.txt`
- `run_server.py`
- `web/`
- `core/`
- `data/`

## 2) Create the Render service

1. Sign in to Render.
2. Choose **New → Web Service** (or create a Blueprint from `render.yaml`).
3. Connect the GitHub repository.
4. Render should detect the settings from `render.yaml`.
5. Deploy.

The important commands are:

- Build: `pip install -r requirements.txt`
- Start: `gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT web.app:app`
- Health check: `/health`

After the deployment finishes, Render gives a public HTTPS URL such as:

`https://railblock-ai.onrender.com`

Your exact URL depends on the available service name.

## SQLite note

The app uses SQLite. On Render's free web-service filesystem, runtime file changes are not guaranteed to persist across redeploys/restarts. This is fine for a short SIH demo, because the bundled database/CSV seed data loads again, but newly submitted Engineer requests can reset after a service restart.

For persistent Engineer/Officer requests, attach a Render persistent disk and set:

`RAILBLOCK_DB_PATH=/var/data/railblock.db`

with the disk mounted at `/var/data`.

Because persistent disks are a paid Render feature, the free demo can run without this environment variable.

## Local run still works

```bash
python -m pip install -r requirements.txt
python run_server.py
```

Open `http://127.0.0.1:5000` locally.
