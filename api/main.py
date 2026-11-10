from fastapi import FastAPI

app = FastAPI(
    title="MANI API",
    description="API do Monitoramento Inteligente de Plantações",
    version="1.0.0"
)

@app.get("/")
def inicio():
    return {
        "projeto": "MANI",
        "mensagem": "API funcionando!"
    }

@app.get("/status")
def status():
    return {
        "online": True,
        "sistema": "MANI",
        "versao": "1.0.0"
    }