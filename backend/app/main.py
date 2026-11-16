from fastapi import FastAPI

app = FastAPI(title="Asistente AI Act")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
