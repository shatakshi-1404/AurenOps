# AurenOps — Enterprise AI Operations Agent

FastAPI + LangGraph + Postgres/pgvector + Redis/Celery backend, React + TypeScript frontend.
First workflow: invoice collection with human approval (mock email provider, synthetic data).

## Run

```bash
# 1. infra
docker compose up -d db redis

# 2. backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optionally add GROQ_API_KEY
python -m scripts.init_db && python -m scripts.seed
uvicorn app.main:app --reload                                   # terminal 1
celery -A app.workers.celery_app.celery worker -B -l info -c 2  # terminal 2
pytest -q

# 3. frontend
cd ../frontend
cp .env.example .env
npm install && npm run dev      # http://localhost:5173
```

Demo logins (password `Passw0rd!`): owner@demo.com, admin@demo.com, operator@demo.com, viewer@demo.com.
API docs: http://localhost:8000/docs

## Demo path
1. Sign in as operator@demo.com, pick a suggested prompt, Preview plan, Run workflow.
2. Watch the Mission Canvas; the run pauses at the approval gate.
3. Review in the Approval Inbox (edit a draft, deselect some), Approve.
4. Execution resumes, report is generated (Analytics: CSV/PDF).

## Notes
- Without GROQ_API_KEY every agent uses deterministic fallbacks.
- Not implemented yet: pause/resume, subgraphs, AI eval harness, CI, nginx/frontend Dockerfile.
- Time-saved metric is an estimate (minutes_saved_per_email in config), not a measurement.
