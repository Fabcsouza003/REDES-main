// Aguarda o carregamento completo para iniciar os ciclos
document.addEventListener("DOMContentLoaded", () => {
    // Inicia a primeira busca imediatamente
    fetchData();
    
    // Configura a atualização em tempo real a cada 800ms
    setInterval(fetchData, 800);
});