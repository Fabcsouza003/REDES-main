import subprocess
import platform
import re

def detectar_gateway_e_prefixo():
    """Detecta de forma precisa o Gateway Padrão ativo da máquina."""
    gateway_padrao = "192.168.1.1" # Fallback caso falhe
    
    try:
        sistema = platform.system().lower()
        
        if "windows" in sistema:
            # Roda o comando 'route print' no Windows para achar o gateway padrão da rota 0.0.0.0
            resultado = subprocess.run(["route", "print", "0.0.0.0"], capture_output=True, text=True, timeout=2)
            linhas = resultado.stdout.splitlines()
            
            for linha in linhas:
                # Procura pela linha que contém a rota padrão (Gateway)
                if "0.0.0.0" in linha:
                    colunas = linha.strip().split()
                    # No route print do Windows, o gateway geralmente é a terceira ou quarta coluna válida
                    for col in colunas:
                        # Valida se parece com um IP IPv4 válido
                        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", col) and col != "0.0.0.0":
                            gateway_padrao = col
                            break
                    if gateway_padrao != "192.168.1.1":
                        break
        else:
            # Para Linux / macOS via comando 'ip route'
            resultado = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=2)
            match = re.search(r"via\s+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", resultado.stdout)
            if match:
                gateway_padrao = match.group(1)
                
    except Exception:
        pass

    router_ip = gateway_padrao
    interface_ip_prefix = ".".join(router_ip.split(".")[:3]) + "."
    
    return router_ip, interface_ip_prefix

# Atribui automaticamente às variáveis de configuração reais
ROUTER_IP, INTERFACE_IP_PREFIX = detectar_gateway_e_prefixo()


print(ROUTER_IP)
print(INTERFACE_IP_PREFIX)