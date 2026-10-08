import threading
import logging
from backend import create_app
from backend.routes import rotina_varredura_rede, rotina_trafego_tempo_real

app = create_app()

if __name__ == "__main__":
    threading.Thread(target=rotina_varredura_rede, daemon=True).start()
    threading.Thread(target=rotina_trafego_tempo_real, daemon=True).start()
    
    print("\n[+] Painel atualizado! Acesse: http://127.0.0.1:5000\n")
    
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(host='0.0.0.0', port=5000, threaded=True)