# AIC Generic Approval API image.
# Python 3.11 per the stack contract (FastAPI + Pydantic v2 + firebase-admin).
FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app

# Emulator wiring is via env (FIRESTORE_EMULATOR_HOST=firestore:8080,
# FIRESTORE_PROJECT_ID=aic-local) supplied by docker-compose; no scheme, no creds.
# Write-endpoint auth is via env (API_SERVICE_TOKEN); unset + non-emulator fails
# closed. SSRF allowlist via N8N_RESUME_ALLOWED_HOSTS. See README.
EXPOSE 8080

# uvicorn on 8080 (compose maps host->container). Change --port to taste.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
