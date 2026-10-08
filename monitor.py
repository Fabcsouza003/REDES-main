import os
import re
import sys
import time
import platform
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, jsonify, render_template_string, request
import speedtest

# ==========================================
# CONFIGURAÇÕES DA REDE LOCAL
# ==========================================
ROUTER_IP = "192.168.10.1"         
INTERFACE_IP_PREFIX = "192.168.10."  

# Armazena os dispositivos cadastrados pelo usuário
# Formato: { "192.168.10.15": {"name": "Meu iPhone", "type": "Smartphone"} }
REGISTERED_DEVICES = {}

# Armazena quando cada IP foi visto pela primeira vez para calcular o Uptime
DEVICE_FIRST_SEEN = {}

# Estado global
STATE = {
    "all_active_ips": [],
    "lat_roteador": None,
    "dados_velocidade": {"download": "Medindo...", "upload": "Medindo...", "latency": "Medindo..."},
}

app = Flask(__name__)

# ==========================================
# LÓGICA DE DETECÇÃO 
# ==========================================
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

def rotina_varredura_rede():
    while True:
        todos_os_ips = [f"{INTERFACE_IP_PREFIX}{i}" for i in range(1, 255)]
        with ThreadPoolExecutor(max_workers=100) as executor:
            executor.map(forcar_ping_rapido, todos_os_ips)
            
        try:
            resultado = subprocess.run(["arp", "-a"], stdout=subprocess.PIPE, text=True, timeout=2.0)
            linhas = resultado.stdout.split("\n")
        except Exception:
            linhas = []

        with ThreadPoolExecutor(max_workers=30) as executor:
            resultados = executor.map(processar_linha_arp, linhas)
            
        ips_online_agora = []
        agora = time.time()
        
        for r in resultados:
            if r:
                ip = r["ip"]
                ips_online_agora.append(r)
                if ip not in DEVICE_FIRST_SEEN:
                    DEVICE_FIRST_SEEN[ip] = agora # Registra o momento em que conectou
        
        # Remove do Uptime quem desconectou
        ips_apenas = [d["ip"] for d in ips_online_agora]
        ips_para_remover = [ip for ip in DEVICE_FIRST_SEEN if ip not in ips_apenas]
        for ip in ips_para_remover:
            del DEVICE_FIRST_SEEN[ip]

        # Formata os dados para o frontend
        lista_formatada = []
        for d in ips_online_agora:
            tempo_online = agora - DEVICE_FIRST_SEEN[d["ip"]]
            lista_formatada.append({
                "ip": d["ip"],
                "latency": d["latency"],
                "uptime": formatar_uptime(tempo_online)
            })

        STATE["lat_roteador"] = calcular_latencia(ROUTER_IP)
        STATE["all_active_ips"] = sorted(lista_formatada, key=lambda x: int(x["ip"].split(".")[-1]))
        
        time.sleep(1.5)

import psutil

def formatar_velocidade(bytes_por_segundo):
    if bytes_por_segundo >= 1024 * 1024:
        return f"{bytes_por_segundo / (1024 * 1024):.1f} MB/s"
    elif bytes_por_segundo >= 1024:
        return f"{bytes_por_segundo / 1024:.1f} KB/s"
    else:
        return f"{bytes_por_segundo:.0f} B/s"

def rotina_trafego_tempo_real():
    io_anterior = psutil.net_io_counters()
    tempo_anterior = time.time()
    
    while True:
        time.sleep(0.8) # Espera exatos 800ms
        
        io_atual = psutil.net_io_counters()
        tempo_atual = time.time()
        
        delta_tempo = tempo_atual - tempo_anterior
        
        # Calcula bytes transferidos no intervalo de tempo
        bytes_baixados = (io_atual.bytes_recv - io_anterior.bytes_recv) / delta_tempo
        bytes_enviados = (io_atual.bytes_sent - io_anterior.bytes_sent) / delta_tempo
        
        STATE["dados_velocidade"] = {
            "download": formatar_velocidade(bytes_baixados),
            "upload": formatar_velocidade(bytes_enviados),
            "latency": f"{STATE.get('lat_roteador', '--')} ms"
        }
        
        # Atualiza os marcadores para o próximo ciclo
        io_anterior = io_atual
        tempo_anterior = tempo_atual

# ==========================================
# ROTAS FLASK (API E INTERFACE)
# ==========================================
@app.route('/api/data')
def api_data():
    return jsonify({
        "router_ip": ROUTER_IP,
        "registered_devices": REGISTERED_DEVICES,
        **STATE
    })

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.json
    ip = data.get('ip')
    
    # Validação: verifica se o IP existe na varredura atual
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

@app.route('/api/unregister', methods=['POST'])
def api_unregister():
    ip = request.json.get('ip')
    if ip in REGISTERED_DEVICES:
        del REGISTERED_DEVICES[ip]
    return jsonify({"success": True})

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Network Monitor Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    </head>
    <body class="bg-gray-900 text-gray-200 font-sans p-6">
        
        <div class="max-w-6xl mx-auto space-y-6">
            <!-- Header -->
            <div class="flex items-center justify-between bg-gray-800 p-5 rounded-xl border border-gray-700">
                <div class="flex items-center gap-4">
                    <div class="p-3 bg-blue-600 rounded-lg shadow-lg">
                        <i class="fa-solid fa-network-wired text-xl text-white"></i>
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold text-white">Monitor de Rede</h1>
                        <p class="text-sm text-gray-400">Atualização em Tempo Real</p>
                    </div>
                </div>
                <div class="text-right">
                    <p class="text-xs text-gray-400 uppercase font-semibold">Tráfego Atual (Down/Up)</p>
                    <p class="text-lg font-bold text-green-400" id="ui-speed">-- / --</p>
                </div>
            </div>

            <!-- Abas de Navegação -->
            <div class="border-b border-gray-700 flex gap-6">
                <button onclick="switchTab('registered')" id="tab-btn-registered" class="pb-3 text-blue-400 border-b-2 border-blue-500 font-semibold transition">
                    <i class="fa-solid fa-address-book mr-2"></i>Dispositivos Cadastrados
                </button>
                <button onclick="switchTab('all')" id="tab-btn-all" class="pb-3 text-gray-500 hover:text-gray-300 font-semibold transition">
                    <i class="fa-solid fa-radar mr-2"></i>Varredura Geral (Todos os IPs)
                </button>
            </div>

            <!-- ABA 1: Cadastrados -->
            <div id="tab-registered" class="space-y-4 block">
                <div class="flex justify-end">
                    <button onclick="openRegModal()" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-semibold shadow-lg transition">
                        <i class="fa-solid fa-plus mr-2"></i>Cadastrar Dispositivo
                    </button>
                </div>
                <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-900/50 border-b border-gray-700 text-xs uppercase text-gray-400">
                                <th class="p-4">Status</th>
                                <th class="p-4">Nome / Tipo</th>
                                <th class="p-4">IP</th>
                                <th class="p-4">Latência</th>
                                <th class="p-4 text-center">Ações</th>
                            </tr>
                        </thead>
                        <tbody id="registered-table" class="divide-y divide-gray-700/50"></tbody>
                    </table>
                </div>
            </div>

            <!-- ABA 2: Todos os IPs -->
            <div id="tab-all" class="space-y-4 hidden">
                <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-lg">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-900/50 border-b border-gray-700 text-xs uppercase text-gray-400">
                                <th class="p-4">Endereço IP</th>
                                <th class="p-4">Tempo Conectado</th>
                                <th class="p-4">Latência</th>
                            </tr>
                        </thead>
                        <tbody id="all-ips-table" class="divide-y divide-gray-700/50"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Modal Cadastro -->
        <div id="reg-modal" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
            <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 w-96 shadow-2xl">
                <h2 class="text-xl font-bold text-white mb-4">Novo Dispositivo</h2>
                <div class="space-y-4">
                    <div>
                        <label class="text-xs text-gray-400">Endereço IP</label>
                        <input type="text" id="reg-ip" placeholder="192.168.10.x" class="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="text-xs text-gray-400">Nome de Identificação</label>
                        <input type="text" id="reg-name" placeholder="Ex: iPhone do João" class="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white outline-none focus:border-blue-500">
                    </div>
                    <div>
                        <label class="text-xs text-gray-400">Tipo de Dispositivo</label>
                        <select id="reg-type" class="w-full bg-gray-900 border border-gray-600 rounded p-2 text-white outline-none focus:border-blue-500">
                            <option value="Smartphone">Smartphone</option>
                            <option value="Laptop">Laptop / Notebook</option>
                            <option value="Desktop">Desktop PC</option>
                            <option value="Server">Servidor</option>
                            <option value="SmartTV">Smart TV / IoT</option>
                        </select>
                    </div>
                    <div class="flex gap-2 pt-2">
                        <button onclick="closeRegModal()" class="w-1/2 bg-gray-700 hover:bg-gray-600 text-white p-2 rounded transition">Cancelar</button>
                        <button onclick="salvarDispositivo()" class="w-1/2 bg-blue-600 hover:bg-blue-700 text-white p-2 rounded transition font-bold">Salvar</button>
                    </div>
                </div>
            </div>
        </div>

        <script>
            function switchTab(tab) {
                if (tab === 'registered') {
                    document.getElementById('tab-registered').classList.remove('hidden');
                    document.getElementById('tab-all').classList.add('hidden');
                    document.getElementById('tab-btn-registered').classList.replace('text-gray-500', 'text-blue-400');
                    document.getElementById('tab-btn-registered').classList.add('border-b-2', 'border-blue-500');
                    document.getElementById('tab-btn-all').classList.replace('text-blue-400', 'text-gray-500');
                    document.getElementById('tab-btn-all').classList.remove('border-b-2', 'border-blue-500');
                } else {
                    document.getElementById('tab-all').classList.remove('hidden');
                    document.getElementById('tab-registered').classList.add('hidden');
                    document.getElementById('tab-btn-all').classList.replace('text-gray-500', 'text-blue-400');
                    document.getElementById('tab-btn-all').classList.add('border-b-2', 'border-blue-500');
                    document.getElementById('tab-btn-registered').classList.replace('text-blue-400', 'text-gray-500');
                    document.getElementById('tab-btn-registered').classList.remove('border-b-2', 'border-blue-500');
                }
            }

            function openRegModal() { document.getElementById('reg-modal').classList.remove('hidden'); }
            function closeRegModal() { document.getElementById('reg-modal').classList.add('hidden'); }

                    async function salvarDispositivo() {
            const ip = document.getElementById('reg-ip').value;
            const name = document.getElementById('reg-name').value;
            const type = document.getElementById('reg-type').value;

            if(!ip || !name) return alert("IP e Nome são obrigatórios!");

            const res = await fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ip, name, type})
            });

            const data = await res.json();

            // Se a API retornar erro (como o IP não existir), avisa e cancela a ação
            if (!data.success) {
                alert(data.message);
                return; 
            }

            // Se passar, limpa os campos, fecha o modal e atualiza a tabela
            document.getElementById('reg-ip').value = '';
            document.getElementById('reg-name').value = '';
            closeRegModal();
           fetchData();
        }

            async function removerDispositivo(ip) {
                if(confirm(`Tem certeza que deseja remover ${ip}?`)) {
                    await fetch('/api/unregister', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ip})
                    });
                    fetchData();
                }
            }

            function getIcon(type) {
                if(type === 'Smartphone') return '<i class="fa-solid fa-mobile-screen-button text-purple-400"></i>';
                if(type === 'Laptop') return '<i class="fa-solid fa-laptop text-blue-400"></i>';
                if(type === 'Desktop') return '<i class="fa-solid fa-desktop text-blue-400"></i>';
                if(type === 'Server') return '<i class="fa-solid fa-server text-green-400"></i>';
                return '<i class="fa-solid fa-tv text-yellow-400"></i>';
            }

            async function fetchData() {
                try {
                    const res = await fetch('/api/data');
                    const data = await res.json();
                    
                    document.getElementById('ui-speed').innerText = `${data.dados_velocidade.download} / ${data.dados_velocidade.upload}`;

                    // Cria um mapa de IPs online para consulta rápida
                    const onlineIps = {};
                    data.all_active_ips.forEach(d => { onlineIps[d.ip] = d; });

                    // --- RENDERIZAR TABELA DE CADASTRADOS ---
                    let regHtml = '';
                    for (const [ip, info] of Object.entries(data.registered_devices)) {
                        const isOnline = !!onlineIps[ip];
                        const lat = isOnline ? `${onlineIps[ip].latency} ms` : '--';
                        const dot = isOnline ? 
                            '<div class="h-3 w-3 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e]"></div>' : 
                            '<div class="h-3 w-3 rounded-full bg-red-500"></div>';

                        regHtml += `
                            <tr class="hover:bg-gray-700/30 transition">
                                <td class="p-4 flex justify-center">${dot}</td>
                                <td class="p-4">
                                    <div class="flex items-center gap-3">
                                        <div class="text-xl">${getIcon(info.type)}</div>
                                        <div>
                                            <p class="font-medium text-gray-200">${info.name}</p>
                                            <p class="text-xs text-gray-500">${info.type}</p>
                                        </div>
                                    </div>
                                </td>
                                <td class="p-4 font-mono text-sm text-gray-300">${ip}</td>
                                <td class="p-4 text-sm font-mono text-gray-300">${lat}</td>
                                <td class="p-4 text-center">
                                    <button onclick="removerDispositivo('${ip}')" class="text-gray-500 hover:text-red-400 transition">
                                        <i class="fa-solid fa-trash"></i>
                                    </button>
                                </td>
                            </tr>
                        `;
                    }
                    if(Object.keys(data.registered_devices).length === 0) {
                        regHtml = `<tr><td colspan="5" class="text-center p-6 text-gray-500">Nenhum dispositivo cadastrado.</td></tr>`;
                    }
                    document.getElementById('registered-table').innerHTML = regHtml;

                    // --- RENDERIZAR TABELA DE TODOS OS IPs ---
                    let allHtml = '';
                    data.all_active_ips.forEach(d => {
                        allHtml += `
                            <tr class="hover:bg-gray-700/30 transition">
                                <td class="p-4 font-mono text-sm text-gray-300 flex items-center gap-2">
                                    <i class="fa-solid fa-circle-nodes text-gray-500"></i> ${d.ip}
                                </td>
                                <td class="p-4 text-sm font-mono text-blue-400">${d.uptime}</td>
                                <td class="p-4 text-sm font-mono text-green-400">${d.latency} ms</td>
                            </tr>
                        `;
                    });
                    if(data.all_active_ips.length === 0) {
                        allHtml = `<tr><td colspan="3" class="text-center p-6 text-gray-500">Nenhum IP detectado online.</td></tr>`;
                    }
                    document.getElementById('all-ips-table').innerHTML = allHtml;

                } catch(e) {}
            }

            setInterval(fetchData, 800);
            fetchData(); 
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == "__main__":
    threading.Thread(target=rotina_varredura_rede, daemon=True).start()
    
    # Substitua a linha do speedtest por esta:
    threading.Thread(target=rotina_trafego_tempo_real, daemon=True).start()
    
    print("\n[+] Painel atualizado! Acesse: http://127.0.0.1:5000\n")
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', port=5000, threaded=True)