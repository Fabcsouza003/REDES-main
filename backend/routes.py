import time
import platform
import subprocess
import re
import os
import psutil
from concurrent.futures import ThreadPoolExecutor
from flask import Blueprint, jsonify, request, render_template
import requests
from .config import ROUTER_IP, INTERFACE_IP_PREFIX
from .database import REGISTERED_DEVICES, DEVICE_FIRST_SEEN, STATE
import collections
# Adicione isso junto com o DEVICE_FIRST_SEEN no topo do seu arquivo:
DEVICE_MISSING_COUNT = collections.defaultdict(int) 


main_bp = Blueprint('main', __name__)

def calcular_latencia(ip_destino):
    is_windows = platform.system().lower() == "windows"
    parametro_count = "-n" if is_windows else "-c"
    parametro_timeout = "-w" if is_windows else "-W"
    valor_timeout = "800" if is_windows else "1"
    
    comando = ["ping", parametro_count, "1", parametro_timeout, valor_timeout, ip_destino]
    try:
        resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.0)
        if resultado.returncode == 0:
            for linha in resultado.stdout.split("\n"):
                if "time=" in linha or "tempo=" in linha:
                    parte_tempo = linha.split("time=") if "time=" in linha else linha.split("tempo=")
                    ms = parte_tempo[1].split("ms")[0].strip().replace("<", "")
                    return int(float(ms))
        return None
    except Exception:
        return None

def processar_linha_arp(linha):
    regex_ip = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    ip_match = re.search(regex_ip, linha)
    
    if ip_match:
        ip = ip_match.group(1)
        if ip.startswith(INTERFACE_IP_PREFIX) and ip != ROUTER_IP and not ip.endswith(".255"):
            latencia = calcular_latencia(ip)
            if latencia is not None:
                return {"ip": ip, "latency": latencia}
    return None

def forcar_ping_rapido(ip):
    is_windows = platform.system().lower() == "windows"
    param_count = "-n" if is_windows else "-c"
    param_timeout = "-w" if is_windows else "-W"
    val_timeout = "200" if is_windows else "1" 
    comando = ["ping", param_count, "1", param_timeout, val_timeout, ip]
    try:
        subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=0.5)
    except Exception:
        pass

def formatar_uptime(segundos):
    m, s = divmod(int(segundos), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# Adicione isso junto com o DEVICE_FIRST_SEEN no topo do seu arquivo:


import socket
from concurrent.futures import ThreadPoolExecutor
import subprocess
import time

DEVICE_MISSING_COUNT = collections.defaultdict(int) 

def rotina_varredura_rede():
    # Descobre o IP do próprio PC para garantir que ele apareça no painel
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        MEU_PC_IP = s.getsockname()[0]
        s.close()
    except Exception:
        MEU_PC_IP = None

    while True:
        todos_os_ips = [f"{INTERFACE_IP_PREFIX}{i}" for i in range(1, 255)]
        
        # 50 workers para evitar gargalos excessivos de processos no sistema
        with ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(forcar_ping_rapido, todos_os_ips)
            
        try:
            # Timeout de 5.0 segundos para suportar lentidões do SO
            resultado = subprocess.run(["arp", "-a"], stdout=subprocess.PIPE, text=True, timeout=5.0)
            linhas = resultado.stdout.split("\n")
        except Exception:
            # Pula este ciclo de varredura se o comando travar, mantendo o painel intacto
            time.sleep(2)
            continue

        with ThreadPoolExecutor(max_workers=30) as executor:
            resultados = list(executor.map(processar_linha_arp, linhas))
            
        ips_online_agora = []
        agora = time.time()
        
        # Filtra e limpa resultados nulos da varredura ARP
        resultados_validos = [r for r in resultados if r]
        ips_detectados_no_arp = [r["ip"] for r in resultados_validos]

        # --- TRATAMENTO 1 e 2: Forçar a inclusão do Roteador e do Próprio PC ---
        # (O Windows não lista o próprio IP no arp -a, e às vezes omite o roteador)
        for ip_obrigatorio in [ROUTER_IP, MEU_PC_IP]:
            if ip_obrigatorio and ip_obrigatorio not in ips_detectados_no_arp:
                lat = calcular_latencia(ip_obrigatorio) if ip_obrigatorio == ROUTER_IP else 0
                resultados_validos.append({
                    "ip": ip_obrigatorio,
                    "latency": lat,
                    "mac": "Interface Local" if ip_obrigatorio == MEU_PC_IP else "N/A"
                })
                ips_detectados_no_arp.append(ip_obrigatorio)

        # Processa quem foi visto nesta varredura
        for r in resultados_validos:
            ip = r["ip"]
            ips_online_agora.append(r)
            DEVICE_MISSING_COUNT[ip] = 0 # Reseta o contador de falhas se foi visto
            if ip not in DEVICE_FIRST_SEEN:
                DEVICE_FIRST_SEEN[ip] = agora 
        
        # --- TRATAMENTO 3: Lógica de tolerância de 3 ciclos para remoção ---
        for ip in list(DEVICE_FIRST_SEEN.keys()):
            if ip not in ips_detectados_no_arp:
                DEVICE_MISSING_COUNT[ip] += 1
                # Se ainda não estourou o limite de 3 falhas, mantém o dispositivo ativo
                if DEVICE_MISSING_COUNT[ip] < 3:
                    # Tenta recuperar os dados antigos dele para não sumir do painel neste ciclo
                    # (Apenas reconstrói uma estrutura básica para manter o Uptime correndo)
                    ips_online_agora.append({
                        "ip": ip,
                        "latency": "timeout",
                        "mac": "Oculto"
                    })
                else:
                    # Estourou 3 falhas seguidas? Remove definitivamente da rede
                    del DEVICE_FIRST_SEEN[ip]
                    del DEVICE_MISSING_COUNT[ip]

        # Formata a lista final que vai para o painel de exibição
        lista_formatada = []
        # Remove duplicatas caso ocorram no append da tolerância
        ips_processados_unicos = []
        
        for d in ips_online_agora:
            if d["ip"] in ips_processados_unicos:
                continue
            ips_processados_unicos.append(d["ip"])
            
            tempo_online = agora - DEVICE_FIRST_SEEN[d["ip"]]
            lista_formatada.append({
                "ip": d["ip"],
                "latency": d["latency"],
                "uptime": formatar_uptime(tempo_online)
            })

        # --- TRATAMENTO 4: Tratamento de erros e ordenação segura por octeto ---
        STATE["lat_roteador"] = calcular_latencia(ROUTER_IP)
        
        try:
            STATE["all_active_ips"] = sorted(
                lista_formatada, 
                key=lambda x: int(x["ip"].split(".")[-1]) if x["ip"] else 999
            )
        except (ValueError, IndexError):
            STATE["all_active_ips"] = lista_formatada # Fallback caso venha um IP inválido string

        # Intervalo estável de 5 segundos para preservar a performance da máquina
        time.sleep(5.0)



def formatar_velocidade(bytes_por_segundo):
    # Converte Bytes em bits (1 Byte = 8 bits)
    bits_por_segundo = bytes_por_segundo * 8
    
    # 1.000.000 bits = 1 Megabit (Padrão de telecomunicações)
    if bits_por_segundo >= 1_000_000:
        return f"{bits_por_segundo / 1_000_000:.2f} Mbps"
    elif bits_por_segundo >= 1_000:
        return f"{bits_por_segundo / 1_000:.2f} Kbps"
    else:
        return f"{bits_por_segundo:.0f} bps"
def rotina_trafego_tempo_real():
    io_anterior = psutil.net_io_counters()
    tempo_anterior = time.time()
    
    while True:
        time.sleep(0.8) 
        
        io_atual = psutil.net_io_counters()
        tempo_atual = time.time()
        
        delta_tempo = tempo_atual - tempo_anterior
        
        bytes_baixados = (io_atual.bytes_recv - io_anterior.bytes_recv) / delta_tempo
        bytes_enviados = (io_atual.bytes_sent - io_anterior.bytes_sent) / delta_tempo
        
        STATE["dados_velocidade"] = {
            "download": formatar_velocidade(bytes_baixados),
            "upload": formatar_velocidade(bytes_enviados),
            "latency": f"{STATE.get('lat_roteador', '--')} ms"
        }
        
        io_anterior = io_atual
        tempo_anterior = tempo_atual

@main_bp.route('/')
def index():
    return render_template('dashboard.html')

@main_bp.route('/reportar')
def reportar():
    return render_template('reportar.html')

@main_bp.route('/api/data')
def api_data():
    return jsonify({
        "router_ip": ROUTER_IP,
        "registered_devices": REGISTERED_DEVICES,
        **STATE
    })

@main_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    ip = data.get('ip')
    
    ips_ativos = [d["ip"] for d in STATE["all_active_ips"]]
    if ip not in ips_ativos:
        return jsonify({
            "success": False, 
            "message": f"Falha: O IP {ip} não foi encontrado ativo na rede."
        })

    if ip and data.get('name'):
        REGISTERED_DEVICES[ip] = {
            "name": data.get('name'),
            "type": data.get('type')
        }
        return jsonify({"success": True})
        
    return jsonify({"success": False, "message": "Dados inválidos."})


import time
import os
import requests
import threading
from flask import jsonify

def rodar_speedtest_cloudflare():
    # Atualiza o STATE para que o seu frontend mostre o progresso
    STATE["speedtest_status"].update({
        "rodando": True, 
        "etapa": "A medir Ping...",
        "down": "--", 
        "up": "--", 
        "ping": "--"
    })
    
    try:
        # 1. PING
        inicio_ping = time.time()
        requests.get("https://speed.cloudflare.com/__down?bytes=10", timeout=10)
        ping_ms = (time.time() - inicio_ping) * 1000
        STATE["speedtest_status"]["ping"] = f"{round(ping_ms, 2)} ms"

        # 2. DOWNLOAD (Limitado a 10 segundos)
        STATE["speedtest_status"]["etapa"] = "A testar Download..."
        url_download = "https://speed.cloudflare.com/__down?bytes=50000000"
        inicio_dl = time.time()
        resposta_dl = requests.get(url_download, stream=True, timeout=10)
        
        total_baixado = 0
        for chunk in resposta_dl.iter_content(chunk_size=65536):
            if chunk:
                total_baixado += len(chunk)
            
            # Trava de segurança: se passar de 10 segundos, interrompe a transferência
            if time.time() - inicio_dl > 10:
                break
                
        tempo_dl = time.time() - inicio_dl
        download_mbps = ((total_baixado * 8) / 1_000_000) / tempo_dl
        STATE["speedtest_status"]["down"] = f"{round(download_mbps, 2)} Mbps"

        # 3. UPLOAD (Fixo em 2MB para evitar encravar)
        STATE["speedtest_status"]["etapa"] = "A testar Upload..."
        tamanho_upload = 2_000_000 
        dados_upload = os.urandom(tamanho_upload)
        
        inicio_ul = time.time()
        requests.post("https://speed.cloudflare.com/__up", data=dados_upload, timeout=(5, 20))
        tempo_ul = time.time() - inicio_ul
        
        upload_mbps = ((tamanho_upload * 8) / 1_000_000) / tempo_ul if tempo_ul > 0 else 0
        STATE["speedtest_status"]["up"] = f"{round(upload_mbps, 2)} Mbps"

        # 4. FINALIZAÇÃO
        STATE["speedtest_status"]["etapa"] = "Concluído!"

    except requests.exceptions.RequestException:
        STATE["speedtest_status"]["etapa"] = "Erro: Conexão oscilou ou caiu."
    except Exception as e:
        STATE["speedtest_status"]["etapa"] = f"Erro interno: {str(e)}"
    finally:
        STATE["speedtest_status"]["rodando"] = False

import time
import os
import requests
from flask import jsonify
import time
import os
import requests
from flask import jsonify

@main_bp.route('/api/iniciar_speedtest', methods=['POST'])
def api_iniciar_speedtest():
    url_download = "https://speed.cloudflare.com/__down?bytes=25000000"
    url_upload = "https://speed.cloudflare.com/__up"
    
    # O SEGREDO ESTÁ AQUI: Disfarçamos o Python como se fosse o Google Chrome
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. PING
        inicio_ping = time.time()
        requests.get("https://speed.cloudflare.com/__down?bytes=10", headers=headers, timeout=10)
        ping_ms = (time.time() - inicio_ping) * 1000

        # 2. DOWNLOAD (Forçando parada aos 10 segundos para não travar)
        inicio_dl = time.time()
        resposta_dl = requests.get(url_download, headers=headers, stream=True, timeout=15)
        
        total_baixado = 0
        for chunk in resposta_dl.iter_content(chunk_size=65536):
            if chunk:
                total_baixado += len(chunk)
            
            # Trava rígida: interrompe aos 10 segundos
            if time.time() - inicio_dl > 10:
                break
                
        tempo_dl = time.time() - inicio_dl
        download_mbps = ((total_baixado * 8) / 1_000_000) / tempo_dl if tempo_dl > 0 else 0

        # 3. UPLOAD
        tamanho_upload_bytes = 2_000_000 # Reduzido para 2MB para ser rápido
        dados_upload = os.urandom(tamanho_upload_bytes)
        
        inicio_ul = time.time()
        requests.post(url_upload, headers=headers, data=dados_upload, timeout=20)
        tempo_ul = time.time() - inicio_ul
        
        upload_mbps = ((tamanho_upload_bytes * 8) / 1_000_000) / tempo_ul if tempo_ul > 0 else 0

        return jsonify({
            "sucesso": True,
            "download_mbps": round(download_mbps, 2),
            "upload_mbps": round(upload_mbps, 2),
            "ping_ms": round(ping_ms, 2)
        })

    except requests.exceptions.RequestException as e:
        # Agora o erro vai mostrar exatamente o que deu errado (ex: ReadTimeout, ConnectionError)
        return jsonify({
            "sucesso": False, 
            "erro": f"Falha na conexão: {str(e)}"
        })
    except Exception as e:
        return jsonify({
            "sucesso": False, 
            "erro": f"Erro interno: {str(e)}"
        })
@main_bp.route('/api/unregister', methods=['POST'])
def api_unregister():
    ip = request.json.get('ip')
    if ip in REGISTERED_DEVICES:
        del REGISTERED_DEVICES[ip]
    return jsonify({"success": True})

@main_bp.route("/api/requestGateway", methods=['POST'])
def requestGate():
    return jsonify({"gateway": ROUTER_IP})