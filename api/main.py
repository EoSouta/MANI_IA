 
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
 
from database import Base, engine, get_db
import models
 
 
# ==========================================
# INICIALIZACAO DO BANCO
# ==========================================
 
Base.metadata.create_all(bind=engine)
 
 
# ==========================================
# CONFIGURACAO DA API
# ==========================================
 
app = FastAPI(
    title="MANI API",
    description="API do Monitoramento Inteligente de Plantacoes",
    version="1.0.0"
)
 
 
# ==========================================
# MODELOS DE ENTRADA
# ==========================================
 
class SensorCreate(BaseModel):
    nome: str
    modelo: Optional[str] = None
    tipo: Optional[str] = None
    comunicacao: Optional[str] = None
    plantacao_id: Optional[int] = None
 
 
class LeituraCreate(BaseModel):
    sensor_id: int
    nitrogenio: Optional[float] = None
    fosforo: Optional[float] = None
    potassio: Optional[float] = None
    temperatura: Optional[float] = None
    umidade: Optional[float] = None
    ph: Optional[float] = None
 
 
# ==========================================
# ROTAS INICIAIS
# ==========================================
 
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
        "versao": "1.0.0",
        "banco": "SQLite"
    }
 
 
# ==========================================
# CADASTRO DE SENSORES
# ==========================================
 
@app.post("/sensores")
def cadastrar_sensor(
    dados: SensorCreate,
    db: Session = Depends(get_db)
):
 
    if dados.plantacao_id is not None:
        plantacao = db.query(models.Plantacao).filter(
            models.Plantacao.id == dados.plantacao_id
        ).first()
 
        if not plantacao:
            raise HTTPException(
                status_code=404,
                detail="Plantacao nao encontrada"
            )
 
    sensor = models.Sensor(**dados.model_dump())
 
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
 
    return {
        "mensagem": "Sensor cadastrado com sucesso!",
        "id": sensor.id,
        "nome": sensor.nome
    }
 
 
# ==========================================
# LISTAGEM DE SENSORES
# ==========================================
 
@app.get("/sensores")
def listar_sensores(db: Session = Depends(get_db)):
 
    sensores = db.query(models.Sensor).all()
 
    return [
        {
            "id": s.id,
            "nome": s.nome,
            "modelo": s.modelo,
            "tipo": s.tipo,
            "comunicacao": s.comunicacao,
            "plantacao_id": s.plantacao_id,
            "ativo": s.ativo
        }
        for s in sensores
    ]
 
 
# ==========================================
# RECEBIMENTO DE LEITURAS
# ==========================================
 
@app.post("/leituras")
def registrar_leitura(
    dados: LeituraCreate,
    db: Session = Depends(get_db)
):
 
    sensor = db.query(models.Sensor).filter(
        models.Sensor.id == dados.sensor_id
    ).first()
 
    if not sensor:
        raise HTTPException(
            status_code=404,
            detail="Sensor nao encontrado"
        )
 
    leitura = models.Leitura(**dados.model_dump())
 
    db.add(leitura)
    db.commit()
    db.refresh(leitura)
 
    return {
        "mensagem": "Leitura armazenada com sucesso!",
        "id": leitura.id,
        "sensor_id": leitura.sensor_id
    }
 
 
# ==========================================
# CONSULTA DO HISTORICO
# ==========================================
 
@app.get("/leituras")
def listar_leituras(
    sensor_id: Optional[int] = None,
    limite: int = 100,
    db: Session = Depends(get_db)
):
 
    if limite < 1 or limite > 1000:
        raise HTTPException(
            status_code=400,
            detail="Limite deve estar entre 1 e 1000"
        )
 
    consulta = db.query(models.Leitura)
 
    if sensor_id is not None:
        consulta = consulta.filter(
            models.Leitura.sensor_id == sensor_id
        )
 
    leituras = consulta.order_by(
        models.Leitura.id.desc()
    ).limit(limite).all()
 
    return [
        {
            "id": l.id,
            "sensor_id": l.sensor_id,
            "nitrogenio": l.nitrogenio,
            "fosforo": l.fosforo,
            "potassio": l.potassio,
            "temperatura": l.temperatura,
            "umidade": l.umidade,
            "ph": l.ph,
            "data_hora": l.data_hora
        }
        for l in leituras
    ]
 