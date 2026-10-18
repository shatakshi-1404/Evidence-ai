# Deploy EvidenceAI (Render backend + Vercel frontend)

Costs money: the Blueprint uses a paid Render database and a ~2 GB web service.
Check current prices on Render before you confirm. Plan names in `render.yaml`
may need adjusting if Render renames them; Render tells you if one is invalid.

## 1. Backend on Render
1. Push this project to GitHub.
2. Render dashboard -> New + -> **Blueprint** -> pick the repo -> Apply.
3. When asked, type:
   - `LLM_API_KEY`: your Groq key
   - `CORS_ORIGINS`: `["https://placeholder.vercel.app"]` (fixed in step 3)
4. Wait for the deploy (first start is slow: it downloads the embedding model).
5. Open `https://YOUR-SERVICE.onrender.com/api/health`. It should show JSON.

## 2. Frontend on Vercel
1. Edit `frontend/vercel.json`: replace `REPLACE-WITH-YOUR-RENDER-URL` with your
   Render service name (the part before `.onrender.com`). Commit and push.
2. Vercel -> Add New -> Project -> pick the repo -> **Root Directory: `frontend`** -> Deploy.

## 3. Connect them
In Render -> evidenceai-api -> Environment, set `CORS_ORIGINS` to
`["https://YOUR-APP.vercel.app"]` (exact Vercel address, no trailing slash). Save.
