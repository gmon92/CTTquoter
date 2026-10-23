(() => {
  const status = document.getElementById('connection_status');
  function updateConnection() {
    status.hidden = navigator.onLine;
    status.textContent = 'You are offline. Reconnect before calculating or adjusting a quote.';
    const button = document.getElementById('calculate_button');
    button.disabled = !navigator.onLine || button.getAttribute('aria-busy') === 'true';
  }
  window.addEventListener('online', updateConnection);
  window.addEventListener('offline', updateConnection);
  window.addEventListener('pageshow', event => {
    if (event.persisted) window.location.reload();
  });
  updateConnection();
  const standalone = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone;
  document.getElementById('install_help').hidden = Boolean(standalone);
  if ('serviceWorker' in navigator && window.isSecureContext) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', {scope: '/', updateViaCache: 'none'}).catch(() => {
        document.getElementById('install_status').textContent = 'Offline notice could not be installed. You can still quote online; reopen the app to retry.';
      });
    });
  }
})();
