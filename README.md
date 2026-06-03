# Thrillophilia v2 — React + FastAPI

## Upstash Redis Setup (Free)
1. Go to https://upstash.com → Sign up free
2. Create Database → Choose region closest to your Render server (Singapore)
3. Copy the "Redis URL" — looks like: rediss://default:xxxx@xxxx.upstash.io:6379
4. Add as UPSTASH_REDIS_URL in Render environment variables

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # fill in your keys
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

Open http://localhost:5173

## Folder Structure
```
thrillophilia_v2/
├── backend/
│   ├── main.py                  ← FastAPI app
│   ├── routers/                 ← Route handlers
│   ├── services/                ← Business logic + cache
│   ├── models/                  ← Pydantic schemas
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/               ← HeroPage, PlanningPage, ResultsPage
│   │   ├── components/          ← ChatPopup, DestinationGrid, etc.
│   │   ├── hooks/               ← SSE, chat popup hooks
│   │   ├── store/               ← Zustand global state
│   │   ├── api/                 ← Axios client
│   │   └── styles/              ← Tailwind + custom CSS
│   └── package.json
├── agents/                      ← UNCHANGED from v1
├── tools/                       ← UNCHANGED from v1
├── workflow.py                  ← UNCHANGED from v1
├── state.py                     ← UNCHANGED from v1
└── render.yaml
```

## Render Deployment
1. Push to GitHub
2. Go to render.com → New → Blueprint
3. Connect your repo — Render reads render.yaml automatically
4. Add all environment variables marked `sync: false`
5. Deploy
