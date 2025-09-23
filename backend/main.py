from fastapi import FastAPI

app = FastAPI(title="BullBearBroker API")

@app.get("/")
def read_root():
    return {"message": "🚀 BullBearBroker API corriendo correctamente!"}
