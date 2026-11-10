import json
import os
import sys
import argparse
from datetime import datetime
import geobr
import rioxarray

def calcular_clima_e_geo_real(latitude, longitude):
    """
    Simula ou calcula em tempo real a extração de dados espaciais (geobr/rioxarray).
    Substitua os retornos fixos abaixo pelas chamadas reais das suas bibliotecas.
    """
    # Exemplo adaptado para a região de Santa Cruz / RJ com base nas coordenadas
    municipio = "Santa Cruz, Rio de Janeiro"
    bioma = "Mata Atlântica"
    
    # Simulação de oscilação climática em tempo real baseada no horário atual
    agora = datetime.now()
    minutos_variacao = (agora.minute * 0.05) - 1.5
    
    clima = {
        "temperatura_solo_c": round(24.8 + minutos_variacao, 2),
        "umidade_relativa_pct": max(10, min(100, int(78 - minutos_variacao * 2))),
        "precipitacao_acumulada_mm": round(12.4 + max(0.0, minutos_variacao), 2),
        "ultima_atualizacao": agora.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    return municipio, bioma, clima

def atualizar_arquivo_json_dados(latitude, longitude, municipio, bioma, clima):
    """ Cria ou substitui o arquivo JSON na pasta 'dados' com as informações mais recentes """
    pasta_dados = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")
    os.makedirs(pasta_dados, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_dados, "dados_localizacao_atual.json")
    
    conteudo_json = {
        "coordenadas": {
            "latitude": latitude,
            "longitude": longitude
        },
        "geografia": {
            "municipio": municipio,
            "bioma": bioma
        },
        "clima_tempo_real": clima
    }
    
    # Escrita segura usando arquivo temporário para evitar corrupção de dados
    caminho_tmp = caminho_arquivo + ".tmp"
    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(conteudo_json, f, ensure_ascii=False, indent=2)
    os.replace(caminho_tmp, caminho_arquivo)

def loop_servico_mani():
    """ Loop de escuta contínuo processando requisições em JSON via STDIN da interface Mani """
    while True:
        try:
            linha = sys.stdin.readline()

            requisicao = json.loads(linha)
            acao = requisicao.get("acao")

            if acao == "encerrar":
                break

            elif acao in ["obter_nome_local", "obter_contexto"]:
                coords = requisicao.get("coordenadas", {})
                lat = coords.get("latitude", -22.9068)
                lon = coords.get("longitude", -43.1729)
                
                # 1. Processa e atualiza os dados climáticos na hora
                municipio, bioma, clima = calcular_clima_e_geo_real(lat, lon)
                
                # 2. Grava ou substitui o arquivo na pasta 'dados'
                atualizar_arquivo_json_dados(lat, lon, municipio, bioma, clima)
                
                # 3. Responde à interface de acordo com o protocolo esperado por Mani.py
                if acao == "obter_nome_local":
                    resposta = {"nome_local": municipio}
                else:
                    # 'obter_contexto' espera os ponteiros de arquivos se houverem
                    resposta = {
                        "arquivo_geografico": None,
                        "arquivo_planta": None
                    }
                
                sys.stdout.write(json.dumps(resposta, ensure_ascii=False) + "\n")
                sys.stdout.flush()

        except Exception as e:
            # Proteção contra quebras de fluxo: responde em JSON mesmo sob erro interno
            erro_resposta = {"nome_local": f"Erro Operacional: {str(e)}"}
            sys.stdout.write(json.dumps(erro_resposta, ensure_ascii=False) + "\n")
            sys.stdout.flush()

def executar_modo_manual():
    print("Mestre Iniciado. Modo Console Manual.")
    lat, lon = -22.916, -43.683
    while True:
        pergunta_usuario = input("\n[Usuário]: ")
        if pergunta_usuario.lower() in ['sair', 'exit']:
            break
        municipio, bioma, clima = calcular_clima_e_geo_real(lat, lon)
        atualizar_arquivo_json_dados(lat, lon, municipio, bioma, clima)
        print(f"\n[Mani Local]: Informações salvas em 'dados/dados_localizacao_atual.json'. Local: {municipio}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--servico-mani", action="store_true")
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--raio", type=float)
    parser.add_argument("--worker-id", type=int)
    
    args, _ = parser.parse_known_args()

    if args.servico_mani:
        loop_servico_mani()
    else:
        executar_modo_manual()
