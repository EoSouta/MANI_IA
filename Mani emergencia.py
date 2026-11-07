import os
import json
import tkinter as tk
from tkinter import messagebox, scrolledtext
import Programa_principal

CONFIG_COMPORTAMENTO = {
    "nome_assistente": "Mani",
    "personalidade": "Técnica, focada em geografia e botânica, direta e precisa.",
    "criadores": "Nhamandu",
    "diretrizes": [
        "Sempre priorizar dados climáticos em tempo real se a pergunta envolver o ambiente local.",
        "Cruzar os requisitos de plantas do plantas.json com o clima do rioxarray sempre que uma planta for citada.",
        "Manter um tom de assistente operacional de emergência."
    ]
}


def analisar_contexto_ia(pergunta):
    pergunta_clean = pergunta.lower()

    caminho_json = os.path.join("dados", "plantas.json")
    banco_plantas = {}
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                banco_plantas = json.load(f)
        except Exception as e:
            print(f"Erro ao ler plantas.json: {e}")

    # 2. Varre o plantas.json procurando a planta mencionada
    planta_encontrada = None
    for nome_planta, info in banco_plantas.items():
        if nome_planta.lower() in pergunta_clean:
            planta_encontrada = {
                "nome": nome_planta,
                "dados": info
            }
            break

    # 3. Coordenadas padrão da operação (Modifique no Programa_principal se necessário)
    coordenadas_atuais = (-22.916, -43.683)

    # 4. Solicita dinamicamente ao programa principal as análises do geobr e rioxarray
    dados_ambientais = Programa_principal.extrair_dados_geo_climaticos(coordenadas_atuais)
    clima = dados_ambientais.get("clima_atual", {})

    # 5. Consolida o prompt final unindo Comportamento + Clima + Memória de Plantas
    prompt_sistema = f"""
    [DIRETRIZES DA IA]: Você é a {CONFIG_COMPORTAMENTO['nome_assistente']}. Sua personalidade é {CONFIG_COMPORTAMENTO['personalidade']}.
    Regras de atuação: {', '.join(CONFIG_COMPORTAMENTO['diretrizes'])}

    [CONDIÇÕES GEOGRÁFICAS E CLIMÁTICAS EM TEMPO REAL (geobr/rioxarray)]:
    - Município/Local: {dados_ambientais.get('municipio')}
    - Bioma Local: {dados_ambientais.get('bioma')}
    - Temperatura Atual: {clima.get('temperatura_solo_c', 'N/A')}°C
    - Umidade do Ar: {clima.get('umidade_relativa_pct', 'N/A')}%
    - Precipitação: {clima.get('precipitacao_acumulada_mm', 'N/A')}mm
    """

    if planta_encontrada:
        prompt_sistema += f"\n[DADOS DE MEMÓRIA DA PLANTA DETECTADA (plantas.json)]:\n"
        prompt_sistema += f"- Espécie: {planta_encontrada['nome']}\n"
        prompt_sistema += f"- Requisitos e Informações: {planta_encontrada['dados']}\n"
    else:
        prompt_sistema += "\n[DADOS DE MEMÓRIA]: Nenhuma planta específica do catálogo foi citada pelo usuário."

    prompt_sistema += f"\n\nPergunta do Usuário: {pergunta}"

    # -----------------------------------------------------------------
    # CHAMADA DA API DO GEMINI / MODELO DA IA
    # -----------------------------------------------------------------
    # Substitua a simulação abaixo pela chamada real do seu modelo enviando 'prompt_sistema'
    # exemplo: resposta = modelo.generate_content(prompt_sistema)

    resposta_ia_simulada = f"[{CONFIG_COMPORTAMENTO['nome_assistente']}]: Analisando {dados_ambientais.get('municipio')} ({clima.get('temperatura_solo_c')}°C). "
    if planta_encontrada:
        resposta_ia_simulada += f"A espécie '{planta_encontrada['nome']}' foi revisada contra estas condições."
    else:
        resposta_ia_simulada += "Condições gerais do bioma revisadas de acordo com as diretrizes operacionais."

    return resposta_ia_simulada


# =====================================================================
# INTERFACE GRÁFICA (MANTIDA E ADAPTADA AO FLUXO DINÂMICO)
# =====================================================================
def enviar_mensagem():
    pergunta = entrada_texto.get("1.0", tk.END).strip()
    if not pergunta:
        return

    # Exibe a pergunta do usuário no chat
    chat_historico.config(state=tk.NORMAL)
    chat_historico.insert(tk.END, f"Você: {pergunta}\n\n")

    # Executa a análise em tempo real cruzando Clima (Principal) e Plantas (Memória)
    resposta_mani = analisar_contexto_ia(pergunta)

    # Exibe a resposta da IA na interface gráfica
    chat_historico.insert(tk.END, f"{resposta_mani}\n\n")
    chat_historico.config(state=tk.DISABLED)

    # Limpa a caixa de entrada
    entrada_texto.delete("1.0", tk.END)
    chat_historico.yview(tk.END)


# Inicialização da Janela da Interface Gráfica
root = tk.Tk()
root.title(f"Sistema Emergencial — {CONFIG_COMPORTAMENTO['nome_assistente']}")
root.geometry("600x500")

# Histórico do Chat
chat_historico = scrolledtext.ScrolledText(root, state=tk.DISABLED, wrap=tk.WORD, bd=2, relief=tk.GROOVE)
chat_historico.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

entrada_texto = tk.Text(root, height=4, bd=2, relief=tk.GROOVE)
entrada_texto.pack(padx=10, pady=5, fill=tk.X, side=tk.LEFT, expand=True)

botao_enviar = tk.Button(root, text="Enviar", command=enviar_mensagem, bg="#4CAF50", fg="white",
                         font=("Arial", 10, "bold"))
botao_enviar.pack(padx=10, pady=5, side=tk.RIGHT, fill=tk.Y)

if __name__ == "__main__":
    root.mainloop()
