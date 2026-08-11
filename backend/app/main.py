from fastapi import FastAPI

app = FastAPI(
    title="MediGuardian AI",
    description="MediGuardian AI - Healthcare Information & Intelligence API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/")
def read_root():
    return {
        "name": "MediGuardian AI",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }
