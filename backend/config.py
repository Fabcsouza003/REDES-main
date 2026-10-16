import platform
import re
import subprocess
import psutil
import socket  # <-- Certifique-se de importar o socket

def listar_e_escolher_interface():
    """Lista as interfaces de rede disponíveis e permite escolher pelo nome."""
    interfaces = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    
    print("\n[+] Interfaces de rede disponíveis no sistema:")
    idx = 1
    mapa_escolhas = {}
    
    for nome_interface, addrs in interfaces.items():
        ativa = stats[nome_interface].isup if nome_interface in stats else False
        status_str = "Ativa" if ativa else "Inativa"
        
        ipv4 = "Sem IPv4"
        for addr in addrs:
            # Correção aqui: usando socket.AF_INET em vez de psutil.AF_INET
            if addr.family == socket.AF_INET:
                ipv4 = addr.address
                
        print(f"  [{idx}] {nome_interface} (IP: {ipv4}) - Status: {status_str}")
        mapa_escolhas[str(idx)] = nome_interface
        idx += 1

    escolha = input("\nDigite o NÚMERO ou o NOME exato da interface que deseja monitorar: ").strip()
    
    if escolha in mapa_escolhas:
        interface_selecionada = mapa_escolhas[escolha]
    else:
        interface_selecionada = escolha

    return interface_selecionada

def obter_configuracoes_interface(nome_interface):
    """Extrai o IP local e descobre o gateway com base na interface escolhida."""
    addrs = psutil.net_if_addrs().get(nome_interface, [])
    ip_local = None
    
    for addr in addrs:
        # Correção aqui também: socket.AF_INET
        if addr.family == socket.AF_INET:
            ip_local = addr.address
            break
            
    if not ip_local:
        raise ValueError(f"A interface '{nome_interface}' não possui um endereço IPv4 configurado!")
        
    interface_ip_prefix = ".".join(ip_local.split(".")[:3]) + "."
    gateway_padrao = interface_ip_prefix + "1"
    
    try:
        sistema = platform.system().lower()
        if "windows" in sistema:
            resultado = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=2)
            for linha in resultado.stdout.splitlines():
                if "0.0.0.0" in linha:
                    colunas = linha.strip().split()
                    for col in colunas:
                        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", col) and col != "0.0.0.0" and col.startswith(interface_ip_prefix):
                            gateway_padrao = col
                            break
        else:
            resultado = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
            match = re.search(r"via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", resultado.stdout)
            if match and match.group(1).startswith(interface_ip_prefix):
                gateway_padrao = match.group(1)
    except Exception:
        pass

    return gateway_padrao, interface_ip_prefix, ip_local

# Executa o fluxo de seleção ao iniciar o backend
NOME_INTERFACE_ESCOLHIDA = listar_e_escolher_interface()
ROUTER_IP, INTERFACE_IP_PREFIX, MEU_PC_IP = obter_configuracoes_interface(NOME_INTERFACE_ESCOLHIDA)

print(f"\n[✔] Interface selecionada: {NOME_INTERFACE_ESCOLHIDA}")
print(f"[✔] IP do PC na interface: {MEU_PC_IP}")
print(f"[✔] Gateway (Router IP): {ROUTER_IP}")
print(f"[✔] Prefixo da Rede: {INTERFACE_IP_PREFIX}\n")