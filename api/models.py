 
from sqlalchemy import (
    Column, Integer, String, Float, Boolean,
    DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from datetime import datetime
 
from database import Base
 
 
# 1. Plantações
class Plantacao(Base):
    __tablename__ = "plantacoes"
 
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    cultura = Column(String(100))
    ativo = Column(Boolean, default=True)
 
    sensores = relationship("Sensor", back_populates="plantacao")
 
 
# 2. Sensores
class Sensor(Base):
    __tablename__ = "sensores"
 
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    modelo = Column(String(100))
    tipo = Column(String(50))
    comunicacao = Column(String(50))
    ativo = Column(Boolean, default=True)
 
    plantacao_id = Column(Integer, ForeignKey("plantacoes.id"))
 
    plantacao = relationship("Plantacao", back_populates="sensores")
    leituras = relationship("Leitura", back_populates="sensor")
 
 
# 3. Leituras dos sensores
class Leitura(Base):
    __tablename__ = "leituras"
 
    id = Column(Integer, primary_key=True, index=True)
    nitrogenio = Column(Float)
    fosforo = Column(Float)
    potassio = Column(Float)
    temperatura = Column(Float)
    umidade = Column(Float)
    ph = Column(Float)
 
    data_hora = Column(DateTime, default=datetime.utcnow)
 
    sensor_id = Column(Integer, ForeignKey("sensores.id"))
 
    sensor = relationship("Sensor", back_populates="leituras")
 
 
# 4. Alertas
class Alerta(Base):
    __tablename__ = "alertas"
 
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(150), nullable=False)
    descricao = Column(Text)
    nivel = Column(String(30))
    resolvido = Column(Boolean, default=False)
    data_hora = Column(DateTime, default=datetime.utcnow)
 
 
# 5. Histórico da inteligência artificial
class HistoricoIA(Base):
    __tablename__ = "historico_ia"
 
    id = Column(Integer, primary_key=True, index=True)
    pergunta = Column(Text)
    resposta = Column(Text)
    data_hora = Column(DateTime, default=datetime.utcnow)
 