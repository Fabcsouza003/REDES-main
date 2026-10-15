function switchTab(tab) {
    const regTab = document.getElementById('tab-registered-view');
    const allTab = document.getElementById('tab-all');
    const btnReg = document.getElementById('tab-btn-registered');
    const btnAll = document.getElementById('tab-btn-all');

    if (!regTab || !allTab) return;

    if (tab === 'registered') {
        regTab.classList.remove('hidden');
        allTab.classList.add('hidden');
        btnReg.classList.add('underline', 'text-white');
        btnReg.classList.remove('text-gray-400');
        btnAll.classList.remove('underline', 'text-white');
        btnAll.classList.add('text-gray-400');
    } else {
        allTab.classList.remove('hidden');
        regTab.classList.add('hidden');
        btnAll.classList.add('underline', 'text-white');
        btnAll.classList.remove('text-gray-400');
        btnReg.classList.remove('underline', 'text-white');
        btnReg.classList.add('text-gray-400');
    }
}

function openRegModal() { 
    document.getElementById('reg-modal').classList.remove('hidden'); 
}

function closeRegModal() { 
    document.getElementById('reg-modal').classList.add('hidden'); 
}

function getIcon(type) {
    return '';
}