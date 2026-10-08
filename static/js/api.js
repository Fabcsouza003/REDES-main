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
        
        document.getElementById('ui-speed').innerText = `${data.dados_velocidade.download} / ${data.dados_velocidade.upload}`;

        const onlineIps = {};
        data.all_active_ips.forEach(d => { onlineIps[d.ip] = d; });

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
        
        if(document.getElementById('registered-table')) {
            document.getElementById('registered-table').innerHTML = regHtml;
        }

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
        
        if(document.getElementById('all-ips-table')) {
            document.getElementById('all-ips-table').innerHTML = allHtml;
        }

    } catch(e) {}
}

async function iniciarSpeedtest() {
    const btn = document.getElementById('btn-speedtest');
    const resultDiv = document.getElementById('resultado-speedtest');
    
    // Muda o botão para estado de carregamento
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin mr-2"></i>Testando... (Aguarde 20s)';
    btn.classList.replace('bg-purple-600', 'bg-gray-600');
    
    // Esconde resultados anteriores
    resultDiv.classList.add('hidden');

    try {
        // Chama a rota que criaremos no backend
        const res = await fetch('/api/iniciar_speedtest', { method: 'POST' });
        const data = await res.json();
        
        if (data.sucesso) {
            // Mostra os resultados na tela
            document.getElementById('st-down').innerText = `${data.download_mbps} Mbps`;
            document.getElementById('st-up').innerText = `${data.upload_mbps} Mbps`;
            document.getElementById('st-ping').innerText = `${data.ping_ms} ms`;
            resultDiv.classList.remove('hidden');
        } else {
            alert("Erro ao realizar o teste: " + data.erro);
        }
    } catch (e) {
        alert("Falha na comunicação com o servidor.");
    } finally {
        // Restaura o botão ao normal
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-gauge-high mr-2"></i>Testar Velocidade Máxima';
        btn.classList.replace('bg-gray-600', 'bg-purple-600');
    }
}