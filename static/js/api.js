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
    
    if (!data.success) {
        alert(data.message);
        return; 
    }
    
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

async function fetchData() {
    try {
        const res = await fetch('/api/data');
        const data = await res.json();
        
        if (document.getElementById('st-up')) {
            document.getElementById('st-up').innerText = `${data.dados_velocidade.upload}`;
        }
        if (document.getElementById('st-down')) {
            document.getElementById('st-down').innerText = `${data.dados_velocidade.download}`;
        }

        const onlineIps = {};
        data.all_active_ips.forEach(d => { onlineIps[d.ip] = d; });

        let regHtml = '';
        let index = 1;
        for (const [ip, info] of Object.entries(data.registered_devices)) {
            const isOnline = !!onlineIps[ip];
            const statusTag = isOnline ? '[ONLINE]' : '[OFFLINE]';
            const statusColor = isOnline ? 'text-white' : 'text-gray-500';
            const prefix = index < 10 ? `E0${index}` : `E${index}`;

            regHtml += `
                <tr class="border-b border-white/10 hover:bg-white/5 transition">
                    <td class="py-1 pr-2">${prefix} | ${info.name}</td>
                    <td class="py-1 px-2 font-mono text-xs">| ${ip}</td>
                    <td class="py-1 pl-2 text-right ${statusColor}">| ${statusTag}</td>
                    <td class="py-1 pl-2 text-right">
                        <button onclick="removerDispositivo('${ip}')" class="text-xs text-gray-500 hover:text-white transition">
                            [X]
                        </button>
                    </td>
                </tr>
            `;
            index++;
        }
        
        if(Object.keys(data.registered_devices).length === 0) {
            regHtml = `<tr><td colspan="4" class="text-center py-4 text-gray-400">Nenhum dispositivo cadastrado.</td></tr>`;
        }
        
        if(document.getElementById('registered-table')) {
            document.getElementById('registered-table').innerHTML = regHtml;
        }

        let gridHtml = '';
        let allHtml = '';
        data.all_active_ips.forEach(d => {
            gridHtml += `<div>${d.ip}</div>`;
            allHtml += `
                <tr class="border-b border-white/10 hover:bg-white/5 transition font-mono">
                    <td class="py-1">${d.ip}</td>
                    <td class="py-1">${d.uptime}</td>
                    <td class="py-1">${d.latency} ms</td>
                </tr>
            `;
        });
        
        if(data.all_active_ips.length > 0 && document.getElementById('all-ips-grid')) {
            document.getElementById('all-ips-grid').innerHTML = gridHtml;
        }

        if(document.getElementById('all-ips-table')) {
            document.getElementById('all-ips-table').innerHTML = allHtml;
        }

    } catch(e) {}
}

async function iniciarSpeedtest() {
    const btn = document.getElementById('btn-speedtest');
    const resultDiv = document.getElementById('resultado-speedtest');
    
    btn.disabled = true;
    btn.innerHTML = 'TESTANDO...';
    btn.classList.add('opacity-50');
    
    try {
        const res = await fetch('/api/iniciar_speedtest', { method: 'POST' });
        const data = await res.json();
        
        if (data.sucesso) {
            document.getElementById('st-down').innerText = `${data.download_mbps} MB/s`;
            document.getElementById('st-up').innerText = `${data.upload_mbps} MB/s`;
            if (document.getElementById('st-ping')) {
                document.getElementById('st-ping').innerText = `${data.ping_ms} ms`;
            }
            if (resultDiv) resultDiv.classList.remove('hidden');
        } else {
            alert("Erro ao realizar o teste: " + data.erro);
        }
    } catch (e) {
        alert("Falha na comunicação com o servidor.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = 'Speedtest';
        btn.classList.remove('opacity-50');
    }
}

async function requestGateway(){
    const requestgate = await fetch('/api/requestGateway', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({"AAA":"1"})
        })
    const RES = await requestgate.json()
    console.log(RES.gateway)

    if (document.getElementById('gateway')){
        document.getElementById('gateway').innerHTML = `AVAILABLE IP ADDRESS POOL (${RES.gateway})`
    }
}

window.addEventListener("load", requestGateway())