import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.routes.remediation import router as remediation_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AIC Execution Service",
    version="0.2.0",
    description=(
        "Autonomous Incident Commander — accepts approved Terraform HCL snippets "
        "from the LangGraph agent and applies them directly to the Kubernetes cluster."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.include_router(remediation_router)


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "AIC Execution Service"}
