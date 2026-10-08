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

function getIcon(type) {
    if(type === 'Smartphone') return '<i class="fa-solid fa-mobile-screen-button text-purple-400"></i>';
    if(type === 'Laptop') return '<i class="fa-solid fa-laptop text-blue-400"></i>';
    if(type === 'Desktop') return '<i class="fa-solid fa-desktop text-blue-400"></i>';
    if(type === 'Server') return '<i class="fa-solid fa-server text-green-400"></i>';
    return '<i class="fa-solid fa-tv text-yellow-400"></i>';
}