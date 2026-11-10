 
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
 
# Endereço do banco de dados
DATABASE_URL = "sqlite:///./mani.db"
 
# Conexão com SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
 
# Gerenciador de sessões
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
 
# Base para criação das tabelas
Base = declarative_base()
 
 
# Gerenciamento de conexão
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
 