import os
import sys
import json
import re
import subprocess
import unicodedata
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk
import ollama  

# Definições de caminhos e diretórios operacionais
pasta_programa = os.path.dirname(os.path.abspath(__file__))
pasta_parametros = os.path.join(pasta_programa, "parametros")
pasta_dados = os.path.join(pasta_programa, "dados")
os.makedirs(pasta_parametros, exist_ok=True)
os.makedirs(pasta_dados, exist_ok=True)

arquivo_prioridades = os.path.join(pasta_dados, "prioridades_memoria.json")
arquivo_cache_plantas = os.path.join(pasta_dados, "memoria_plantas_cache.json")
arquivo_programa_geografico = os.path.join(pasta_programa, "Programa_principal.py")

WORKER_ID = os.getpid()

processo_geografico = None
coordenadas_geograficas = None
dados_ambientais_reais = None
clima_hipotetico_manual = None

cache_virtual_plantas = {}
dados_prioridades = {"versao": 1, "itens": {}, "pastas": {}, "feedback": []}

# Diretrizes comportamentais integradas da versão de emergência
CONFIG_COMPORTAMENTO = {
    "nome_assistente": "Mani",
    "personalidade": "Técnica, focada em geografia e botânica, direta e precisa.",
    "criadores": "Equipe Nhamandu",
    "diretrizes": [
        "Sempre priorizar dados climáticos em tempo real se a pergunta envolver o ambiente local.",
        "Cruzar os requisitos de plantas do plantas.json com o clima do rioxarray sempre que uma planta for citada.",
        "Manter um tom de assistente operacional de emergência."
        "Qualquer pergunta que não relacionada a geografia, botanica ou agricultura. Responda 'não tenho conhecimento sobre este conteudo. Pergunte algo sobre geografia, botanica, agricultura ou tema semelhante'"
        "Não tente falar o nome do local das cordenadas"
    ]
}

class GerenciadorMemoria:
    def __init__(self):
        self.pasta_memoria = os.path.join(pasta_programa, "memoria")
        os.makedirs(self.pasta_memoria, exist_ok=True)

    def listar_arquivos(self):
        arquivos = []
        for raiz, _, nome_arquivos in os.walk(self.pasta_memoria):
            for nome in nome_arquivos:
                if nome.lower().endswith(".txt"):
                    arquivos.append(os.path.join(raiz, nome))
        return arquivos

    def identificar_arquivo(self, caminho):
        texto = str(caminho).strip().replace("\\", "/")
        marcador = "/memoria/"
        pos = texto.casefold().rfind(marcador)
        if pos >= 0:
            return texto[pos + len(marcador):]
        if texto.casefold().startswith("memoria/"):
            texto = texto[len("memoria/"):]
        if not os.path.isabs(texto):
            return os.path.normpath(texto.replace("/", os.sep)).replace(os.sep, "/")
        return os.path.relpath(texto, self.pasta_memoria).replace(os.sep, "/")

gerenciador_memoria = GerenciadorMemoria()

def solicitar_nome_local_ao_programa_principal(latitude, longitude):
    global processo_geografico
    if not processo_geografico or processo_geografico.poll() is not None:
        return "Serviço geográfico desconectado"

    pedido = {
        "acao": "obter_nome_local",
        "coordenadas": {"latitude": latitude, "longitude": longitude}
    }
    
    try:
        processo_geografico.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n")
        processo_geografico.stdin.flush()
        linha = processo_geografico.stdout.readline()
        if linha:
            resposta = json.loads(linha.strip())
            return resposta.get("nome_local", "Local não identificado")
    except Exception as e:
        return f"Erro na comunicação com o motor geográfico: {e}"
    return "Sem resposta do motor geográfico"

def carregar_prioridades():
    global dados_prioridades
    if os.path.isfile(arquivo_prioridades):
        try:
            with open(arquivo_prioridades, "r", encoding="utf-8") as f:
                dados_prioridades = json.load(f)
        except Exception:
            pass

def salvar_prioridades():
    caminho_tmp = arquivo_prioridades + ".tmp"
    with open(caminho_tmp, "w", encoding="utf-8") as f:
        json.dump(dados_prioridades, f, ensure_ascii=False, indent=2)
    os.replace(caminho_tmp, arquivo_prioridades)

def tokens_relevancia(texto):
    normalizado = unicodedata.normalize("NFKD", str(texto).casefold())
    normalizado = "".join(c for c in normalizado if not unicodedata.combining(c))
    return {t for t in re.findall(r"[a-z0-9]+", normalizado) if len(t) > 1}

def prioridade_aprendida(chave, grupo="itens"):
    return float(dados_prioridades.get(grupo, {}).get(chave, {}).get("peso", 0.0))

def pontuacao_textual_mani(pergunta, identificador, conteudo=""):
    tokens_pergunta = tokens_relevancia(pergunta)
    if not tokens_pergunta:
        return 0.0
    tokens_nome = tokens_relevancia(identificador.replace("__planta__/", "").replace("/", " "))
    tokens_conteudo = tokens_relevancia(conteudo)
    cobertura_nome = len(tokens_pergunta & tokens_nome) / len(tokens_pergunta)
    cobertura_conteudo = len(tokens_pergunta & tokens_conteudo) / len(tokens_pergunta) if tokens_conteudo else 0.0
    return min(1.0, 0.65 * cobertura_conteudo + 0.35 * cobertura_nome)

def classificar_contextos_mani(pergunta, arquivos_fisicos):
    candidatos = []
    pastas_mapeadas = set()
    raiz = os.path.abspath(gerenciador_memoria.pasta_memoria)

    for caminho in arquivos_fisicos:
        caminho_abs = os.path.abspath(caminho)
        pasta_pai = os.path.dirname(caminho_abs)
        ident = gerenciador_memoria.identificar_arquivo(caminho)

        if pasta_pai == raiz:
            conteudo = ""
            try:
                conteudo = Path(caminho).read_text(encoding="utf-8-sig")
            except Exception:
                pass
            lexical = pontuacao_textual_mani(pergunta, ident, conteudo)
            candidatos.append({"tipo": "arquivo_raiz", "caminho": caminho, "identificador": ident, "score": lexical})
        else:
            if pasta_pai not in pastas_mapeadas:
                pastas_mapeadas.add(pasta_pai)
                ident_pasta = gerenciador_memoria.identificar_arquivo(pasta_pai).replace("\\", "/")
                aprendido = max(-1.0, min(1.0, prioridade_aprendida(ident_pasta, "pastas")))
                lexical = pontuacao_textual_mani(pergunta, ident_pasta, "")
                score = 0.85 * lexical + 0.15 * ((aprendido + 1.0) / 2.0)
                candidatos.append({"tipo": "pasta", "caminho": pasta_pai, "identificador": ident_pasta, "score": score})

    for ident, dados in cache_virtual_plantas.items():
        nome_planta = dados.get("nome", ident.split("/", 1)[-1])
        lexical = pontuacao_textual_mani(pergunta, nome_planta, "")
        candidatos.append({"tipo": "planta", "caminho": ident, "identificador": ident, "score": lexical})

    return sorted(candidatos, key=lambda c: c["score"], reverse=True)

def iniciar_programa_geografico():
    global processo_geografico, coordenadas_geograficas
    if processo_geografico and processo_geografico.poll() is None: 
        return
    if not os.path.isfile(arquivo_programa_geografico): 
        return

    try:
        if coordenadas_geograficas is None:
            coordenadas_geograficas = {"latitude": -22.9068, "longitude": -43.1729, "raio_metros": 1000.0}

        processo_geografico = subprocess.Popen(
            [sys.executable, arquivo_programa_geografico, "--servico-mani",
             "--latitude", str(coordenadas_geograficas["latitude"]),
             "--longitude", str(coordenadas_geograficas["longitude"]),
             "--raio", str(coordenadas_geograficas["raio_metros"]),
             "--worker-id", str(WORKER_ID)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", bufsize=1
        )
    except Exception:
        processo_geografico = None

def solicitar_contexto_geografico(nome_planta, precisa_registro):
    if not processo_geografico or processo_geografico.poll() is not None: 
        return None
    pedido = {
        "acao": "obter_contexto", "nome_planta": nome_planta,
        "precisa_registro_planta": bool(precisa_registro),
        "coordenadas": coordenadas_geograficas, "clima_hipotetico": clima_hipotetico_manual
    }
    try:
        processo_geografico.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n")
        processo_geografico.stdin.flush()
        linha = processo_geografico.stdout.readline()
        return json.loads(linha.strip()) if linha else None
    except Exception:
        return None

def carregar_contexto_planta_virtual(identificador):
    global dados_ambientais_reais
    entrada = cache_virtual_plantas.get(identificador)
    if not entrada: 
        return "", {}

    nome = entrada.get("nome", identificador.split("/", 1)[-1])
    resposta = solicitar_contexto_geografico(nome, precisa_registro=True)

    conteudo_planta = ""
    info_ambiente = {}

    pasta_info = Path(pasta_programa) / "memoria" / "info"
    caminho_geo_padrao = pasta_info / "geografia.json"
    caminho_planta_padrao = pasta_info / "planta_alvo.json"

    caminho_geo_atual = caminho_geo_padrao
    if resposta and resposta.get("arquivo_geografico"):
        caminho_geo_atual = Path(resposta["arquivo_geografico"])

    if caminho_geo_atual.is_file():
        try:
            info_ambiente = json.loads(caminho_geo_atual.read_text(encoding="utf-8").strip())
            dados_ambientais_reais = info_ambiente
        except Exception:
            pass

    caminho_planta_atual = caminho_planta_padrao
    if resposta and resposta.get("arquivo_planta"):
        caminho_planta_atual = Path(resposta["arquivo_planta"])

    if caminho_planta_atual.is_file():
        try:
            conteudo_planta = caminho_planta_atual.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    return conteudo_planta, info_ambiente

def carregar_cache_virtual_plantas():
    global cache_virtual_plantas
    if not os.path.isfile(arquivo_cache_plantas): 
        return
    try:
        with open(arquivo_cache_plantas, "r", encoding="utf-8") as f:
            dados = json.load(f)
        cache_virtual_plantas = dados.get("arquivos", {})
    except Exception:
        pass

def encerrar_programa_geografico():
    global processo_geografico
    if processo_geografico and processo_geografico.poll() is None:
        try:
            processo_geografico.stdin.write(json.dumps({"acao": "encerrar"}) + "\n")
            processo_geografico.stdin.flush()
            processo_geografico.wait(timeout=2)
        except Exception:
            processo_geografico.terminate()
            processo_geografico = None

class AssistenteMani:
    def __init__(self, modelo="llama3.2"):
        self.modelo = modelo
        self.historico = []

    def construir_prompt_sistema(self, contexto_texto, dados_clima, planta_json_dados=None):
        diretriz = (
            f"[DIRETRIZES DA IA]: Você é a {CONFIG_COMPORTAMENTO['nome_assistente']}. "
            f"Sua personalidade é {CONFIG_COMPORTAMENTO['personalidade']}.\n"
            f"Regras de atu'aç  ão: {', '.join(CONFIG_COMPORTAMENTO['diretrizes'])}\n\n"
        )

        if coordenadas_geograficas:
            diretriz += f"--- LOCALIZAÇÃO OPERACIONAL ---\n" \
                        f"Latitude: {coordenadas_geograficas.get('latitude')}\n" \
                        f"Longitude: {coordenadas_geograficas.get('longitude')}\n" \
                        f"Raio de Análise: {coordenadas_geograficas.get('raio_metros')} metros\n\n"

        if dados_clima:
            diretriz += f"--- CONDIÇÕES GEOGRÁFICAS E CLIMÁTICOS EM TEMPO REAL (geobr/rioxarray) ---\n" \
                        f"{json.dumps(dados_clima, ensure_ascii=False, indent=2)}\n\n"

        if planta_json_dados:
            diretriz += f"--- DADOS DE MEMÓRIA DA PLANTA DETECTADA (plantas.json) ---\n" \
                        f"{json.dumps(planta_json_dados, ensure_ascii=False, indent=2)}\n\n"
        elif contexto_texto:
            diretriz += f"--- REQUISITOS TÉCNICOS DA PLANTA ALVO (PLANTA_ALVO.JSON) ---\n{contexto_texto}\n\n"

        diretriz += (
            "INSTRUÇÃO OBRIGATÓRIA: Avalie criticamente se as condições climáticas e geográficas detectadas "
            "são compatíveis com os requisitos biológicos da planta pesquisada. "
            "Determine de forma clara se é viável ou não o plantio ou manejo nessa coordenada baseando-se estritamente nos dados cruzados. "
            "Mantenha rigidamente o tom de assistente operacional de emergência. SEJA EXTREMAMENTE CONCISA, DIRETA E OBJETIVA."
        )
        return diretriz

    def enviar_mensagem(self, mensagem_usuario, contexto_texto="", dados_clima=None, planta_json_dados=None):
        prompt_sistema = self.construir_prompt_sistema(contexto_texto, dados_clima, planta_json_dados)
        mensagens = [{'role': 'system', 'content': prompt_sistema}] + self.historico + [
            {'role': 'user', 'content': mensagem_usuario}]

        try:
            resposta = ollama.chat(model=self.modelo, messages=mensagens)
            texto_resposta = resposta['message']['content']
            self.historico.append({'role': 'user', 'content': mensagem_usuario})
            self.historico.append({'role': 'assistant', 'content': texto_resposta})
            self.historico = self.historico[-10:]
            return texto_resposta
        except Exception as e:
            return f"Erro Operacional: Certifique-se de que o servidor Ollama está ativo. Detalhe: {e}"

class InterfaceMani:
    def __init__(self, root):
        self.root = root
        self.root.title(f"Sistema Emergencial — {CONFIG_COMPORTAMENTO['nome_assistente']}")
        self.root.geometry("1000x650")
        self.root.configure(bg="#202225")

        self.ia = AssistenteMani(modelo="llama3.2")

        carregar_prioridades()
        carregar_cache_virtual_plantas()

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=4)

        # Painel Lateral Avançado (Tema Escuro)
        self.painel_lateral = tk.Frame(self.root, bg="#2f3136")
        self.painel_lateral.grid(row=0, column=0, sticky="nsew", padx=(15, 5), pady=15)

        self.label_avatar = tk.Label(self.painel_lateral, bg="#2f3136")
        self.label_avatar.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.carregar_avatar_personagem("Mani desenho.jpg")

        # Painel do Chat Avançado
        self.painel_chat = tk.Frame(self.root, bg="#202225")
        self.painel_chat.grid(row=0, column=1, sticky="nsew", padx=(5, 15), pady=15)
        self.painel_chat.rowconfigure(0, weight=1)
        self.painel_chat.columnconfigure(0, weight=1)

        self.area_chat = scrolledtext.ScrolledText(
            self.painel_chat, wrap=tk.WORD, bg="#36393f", fg="#dcddde",
            insertbackground="white", font=("Segoe UI", 11), relief=tk.FLAT
        )
        self.area_chat.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        self.area_chat.configure(state=tk.DISABLED)

        # Configurações de tags visuais
        self.area_chat.tag_configure("usuario", foreground="#00b0f4", font=("Segoe UI", 11, "bold"))
        self.area_chat.tag_configure("mani", foreground="#43b581", font=("Segoe UI", 11, "bold"))
        self.area_chat.tag_configure("bold_text", font=("Segoe UI", 11, "bold"))

        self.entrada_texto = tk.Entry(
            self.painel_chat, bg="#40444b", fg="#ffffff", insertbackground="white",
            font=("Segoe UI", 12), relief=tk.FLAT
        )
        self.entrada_texto.grid(row=1, column=0, sticky="ew", ipady=8, padx=(0, 5))
        self.entrada_texto.bind("<Return>", self.disparar_envio)

        self.btn_enviar = tk.Button(
            self.painel_chat, text="Enviar", command=self.disparar_envio,
            bg="#43b581", fg="white", activebackground="#3ca374",
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT, width=12, cursor="hand2"
        )
        self.btn_enviar.grid(row=1, column=1, sticky="ns")

        self.solicitar_dados_geograficos_iniciais()
        self.exibir_mensagem_tela("Mani", "Interface operacional carregada com sucesso. Canal seguro estabelecido. Aguardando comandos botânicos de emergência.")
        self.root.protocol("WM_DELETE_WINDOW", self.ao_fechar_programa)

    def abrir_janela_reconfiguracao_loc(self):
        global coordenadas_geograficas
        janela_loc = tk.Toplevel(self.root)
        janela_loc.title("Reconfigurar Localização - Mani")
        janela_loc.geometry("340x250")
        janela_loc.configure(bg="#2f3136")
        janela_loc.transient(self.root)
        janela_loc.grab_set()

        tk.Label(janela_loc, text="Atualizar Coordenadas Geográficas", bg="#2f3136", fg="#43b581",
                 font=("Segoe UI", 11, "bold")).pack(pady=10)

        tk.Label(janela_loc, text="Latitude:", bg="#2f3136", fg="white").pack()
        ent_lat = tk.Entry(janela_loc)
        ent_lat.pack()
        ent_lat.insert(0, str(coordenadas_geograficas.get("latitude", "-22.9068")))

        tk.Label(janela_loc, text="Longitude:", bg="#2f3136", fg="white").pack()
        ent_lon = tk.Entry(janela_loc)
        ent_lon.pack()
        ent_lon.insert(0, str(coordenadas_geograficas.get("longitude", "-43.1729")))

        tk.Label(janela_loc, text="Raio de Análise (metros):", bg="#2f3136", fg="white").pack()
        ent_raio = tk.Entry(janela_loc)
        ent_raio.pack()
        ent_raio.insert(0, str(coordenadas_geograficas.get("raio_metros", "1000")))

        def atualizar_sistema_geografico():
            global coordenadas_geograficas
            try:
                lat = float(ent_lat.get().strip().replace(",", "."))
                lon = float(ent_lon.get().strip().replace(",", "."))
                raio = float(ent_raio.get().strip().replace(",", "."))

                coordenadas_geograficas = {"latitude": lat, "longitude": lon, "raio_metros": raio}

                encerrar_programa_geografico()
                iniciar_programa_geografico()
                janela_loc.destroy()

                self.exibir_mensagem_tela("Mani", "Sincronizando novas coordenadas com o subsistema geográfico...")

                def processamento_background():
                    nome_do_local = solicitar_nome_local_ao_programa_principal(lat, lon)
                    texto_final = (
                        f"**Localização reconfigurada com sucesso!**\n"
                        f"**Região Detectada:** {nome_do_local}\n"
                        f"**Coordenadas:** {lat}, {lon}\n"
                        f"**Novo Raio de Análise:** {raio} metros."
                    )
                    self.root.after(0, lambda: self.animar_escrita_mani(texto_final))

                threading.Thread(target=processamento_background, daemon=True).start()
            except ValueError:
                messagebox.showerror("Erro", "Por favor, insira valores numéricos válidos.")

        btn_confirmar = tk.Button(janela_loc, text="Aplicar Configurações", command=atualizar_sistema_geografico,
                                  bg="#43b581", fg="white", relief=tk.FLAT, font=("Segoe UI", 10, "bold"), cursor="hand2")
        btn_confirmar.pack(pady=15)

    def carregar_avatar_personagem(self, nome_arquivo):
        caminho_imagem = Path(pasta_programa) / nome_arquivo
        if caminho_imagem.exists():
            try:
                img = Image.open(caminho_imagem)
                img.thumbnail((200, 350))
                self.avatar_tk = ImageTk.PhotoImage(img)
                self.label_avatar.configure(image=self.avatar_tk, text="")
            except Exception as e:
                self.label_avatar.configure(text=f"Erro ao carregar\navatar:\n{e}", fg="red")
        else:
            self.label_avatar.configure(
                text=f"[ Imagem não encontrada ]\nCrie o arquivo:\n{nome_arquivo}\nna pasta do script", fg="#8e9297",
                font=("Segoe UI", 9, "italic"))

    def solicitar_dados_geograficos_iniciais(self):
        global coordenadas_geograficas
        janela_inicio = tk.Toplevel(self.root)
        janela_inicio.title("Configuração de Inicialização - Mani")
        janela_inicio.geometry("320x220")
        janela_inicio.configure(bg="#2f3136")
        janela_inicio.transient(self.root)
        janela_inicio.grab_set()

        tk.Label(janela_inicio, text="Configuração Geográfica Obrigatória", bg="#2f3136", fg="#43b581",
                 font=("Segoe UI", 11, "bold")).pack(pady=10)

        tk.Label(janela_inicio, text="Latitude:", bg="#2f3136", fg="white").pack()
        ent_lat = tk.Entry(janela_inicio)
        ent_lat.pack()
        ent_lat.insert(0, "-22.9068")

        tk.Label(janela_inicio, text="Longitude:", bg="#2f3136", fg="white").pack()
        ent_lon = tk.Entry(janela_inicio)
        ent_lon.pack()
        ent_lon.insert(0, "-43.1729")

        tk.Label(janela_inicio, text="Raio de Análise (metros):", bg="#2f3136", fg="white").pack()
        ent_raio = tk.Entry(janela_inicio)
        ent_raio.pack()
        ent_raio.insert(0, "1000")

        def salvar_e_prosseguir():
            global coordenadas_geograficas
            try:
                lat = float(ent_lat.get().strip().replace(",", "."))
                lon = float(ent_lon.get().strip().replace(",", "."))
                raio = float(ent_raio.get().strip().replace(",", "."))

                coordenadas_geograficas = {"latitude": lat, "longitude": lon, "raio_metros": raio}
                iniciar_programa_geografico()
                janela_inicio.destroy()
            except ValueError:
                messagebox.showerror("Erro", "Insira valores numéricos válidos.")

        btn_confirmar = tk.Button(janela_inicio, text="Iniciar Sistema", command=salvar_e_prosseguir, bg="#43b581", fg="white", relief=tk.FLAT, font=("Segoe UI", 10, "bold"))
        btn_confirmar.pack(pady=15)
        self.root.wait_window(janela_inicio)

    def exibir_mensagem_tela(self, remetente, texto, pular_linha_fim=True):
        self.area_chat.configure(state=tk.NORMAL)
        if remetente == "Você":
            self.area_chat.insert(tk.END, f"\n{remetente}: ", "usuario")
        elif remetente == "Mani":
            self.area_chat.insert(tk.END, f"\n{remetente}: ", "mani")
            if texto:  # Processa os negritos caso o texto seja enviado diretamente
                partes = re.split(r"(\*\*.*?\*\*)", texto, flags=re.DOTALL)
                for parte in partes:
                    if parte.startswith("**") and parte.endswith("**"):
                        self.area_chat.insert(tk.END, parte[2:-2], ("mani", "bold_text"))
                    else:
                        self.area_chat.insert(tk.END, parte)
                if pular_linha_fim:
                    self.area_chat.insert(tk.END, "\n")
        self.area_chat.insert(tk.END, f"{texto}" + ("\n" if pular_linha_fim else ""))
        self.area_chat.configure(state=tk.DISABLED)
        self.area_chat.yview(tk.END)

    def animar_escrita_mani(self, texto_completo):
        self.exibir_mensagem_tela("Mani", "", pular_linha_fim=False)
        partes = re.split(r"(\*\*.*?\*\*)", texto_completo, flags=re.DOTALL)

        caracteres_fila = []
        for parte in partes:
            if parte.startswith("**") and parte.endswith("**"):
                conteudo_negrito = parte[2:-2]
                for char in conteudo_negrito:
                    caracteres_fila.append((char, True))
            else:
                for char in parte:
                    caracteres_fila.append((char, False))

        def imprimir_proximo(index=0):
            if index < len(caracteres_fila):
                char, em_negrito = caracteres_fila[index]
                self.area_chat.configure(state=tk.NORMAL)
                if em_negrito:
                    self.area_chat.insert(tk.END, char, ("mani", "bold_text"))
                else:
                    self.area_chat.insert(tk.END, char)
                self.area_chat.configure(state=tk.DISABLED)
                self.area_chat.yview(tk.END)
                self.root.after(15, lambda: imprimir_proximo(index + 1))
            else:
                self.area_chat.configure(state=tk.NORMAL)
                self.area_chat.insert(tk.END, "\n")
                self.area_chat.configure(state=tk.DISABLED)
                self.area_chat.yview(tk.END)

        imprimir_proximo()

    def disparar_envio(self, event=None):
        global clima_hipotetico_manual, dados_ambientais_reais
        entrada = self.entrada_texto.get().strip()
        if not entrada:
            return

        self.entrada_texto.delete(0, tk.END)
        self.exibir_mensagem_tela("Você", entrada)

        if entrada.lower().startswith("/loc"):
            self.abrir_janela_reconfiguracao_loc()
            return

        self.area_chat.configure(state=tk.NORMAL)
        linha_inicio = self.area_chat.index(tk.END + "-1c")
        self.area_chat.insert(tk.END, "\nAguarde, subsistema Mani processando...\n")
        linha_fim = self.area_chat.index(tk.END)
        self.area_chat.configure(state=tk.DISABLED)
        self.area_chat.yview(tk.END)

        self.root.update_idletasks()

        # Varre o plantas.json buscando plantas mencionadas na entrada (Mecanismo do plantas.json)
        # Ajuste adaptativo: varre plantas.json suportando tanto Formato Lista quanto Formato Dicionário
        caminho_json = os.path.join(pasta_dados, "plantas.json")
        planta_encontrada_dados = None

        if os.path.exists(caminho_json):
            try:
                with open(caminho_json, "r", encoding="utf-8") as f:
                    banco_plantas = json.load(f)
                
                if isinstance(banco_plantas, list):
                    for item in banco_plantas:
                        if isinstance(item, dict):
                            nome_planta = item.get("nome") or item.get("especie") or ""

                            if nome_planta and nome_planta.lower() in entrada.lower():
                                planta_encontrada_dados = {"especie": nome_planta, "requisitos": item}
                                break
                
                elif isinstance(banco_plantas, dict):
                    for nome_planta, info in banco_plantas.items():
                        if nome_planta.lower() in entrada.lower():
                            planta_encontrada_dados = {"especie": nome_planta, "requisitos": info}
                            break

            except Exception as e:
                print(f"Erro ao processar plantas.json: {e}")

        arquivos_disponiveis = gerenciador_memoria.listar_arquivos()
        candidatos = classificar_contextos_mani(entrada, arquivos_disponiveis)
        contexto_coletado = ""
        clima_coletado = clima_hipotetico_manual if clima_hipotetico_manual else dados_ambientais_reais

        if candidatos and not planta_encontrada_dados:
            escolhido = candidatos[0]

            if escolhido["score"] > 0.05:
                if escolhido["tipo"] == "arquivo_raiz":
                    try:
                        contexto_coletado = Path(escolhido["caminho"]).read_text(encoding="utf-8-sig")

                    except Exception:
                        pass

                elif escolhido["tipo"] == "planta":
                    contexto_coletado, clima_coletado = carregar_contexto_planta_virtual(escolhido["caminho"])

                elif escolhido["tipo"] == "pasta":
                    arquivos_pasta = [a for a in arquivos_disponiveis if os.path.commonpath(
                        [os.path.abspath(a), os.path.abspath(escolhido["caminho"])]) == os.path.abspath(escolhido["caminho"])]
                    
                    conteudos = []

                    for arq in arquivos_pasta[:3]:
                        try:
                            conteudos.append(Path(arq).read_text(encoding="utf-8-sig"))

                        except Exception:
                            pass

                    contexto_coletado = "\n\n".join(conteudos)

        def executar_chamada_ia():
            resposta = self.ia.enviar_mensagem(
                entrada, 
                contexto_texto=contexto_coletado, 
                dados_clima=clima_coletado, 
                planta_json_dados=planta_encontrada_dados
            )

            self.root.after(0, lambda: limpar_e_exibir(resposta))

        def limpar_e_exibir(resposta):
            self.area_chat.configure(state=tk.NORMAL)

            try:
                self.area_chat.delete(linha_inicio, linha_fim)

            except Exception:
                pass

            self.area_chat.configure(state=tk.DISABLED)
            self.animar_escrita_mani(resposta)

        threading.Thread(target=executar_chamada_ia, daemon=True).start()

    def ao_fechar_programa(self):
        encerrar_programa_geografico()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = InterfaceMani(root)
    root.mainloop()
