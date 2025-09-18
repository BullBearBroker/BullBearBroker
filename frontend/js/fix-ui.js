// fix-ui.js - Solución para errores en ui-components.js
console.log('🔧 Aplicando fix para ui-components...');

// Esperar a que el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        // Verificar que los elementos existan antes de manipularlos
        const safeQuerySelector = (selector, defaultValue = null) => {
            try {
                const element = document.querySelector(selector);
                return element || defaultValue;
            } catch (error) {
                console.warn('⚠️ Error con selector:', selector, error);
                return defaultValue;
            }
        };

        // Sobrescribir funciones problemáticas de ui-components
        if (typeof window.showAlert === 'function') {
            const originalShowAlert = window.showAlert;
            window.showAlert = function(message, type = 'info') {
                try {
                    return originalShowAlert.call(this, message, type);
                } catch (error) {
                    console.log('📢 ' + message); // Fallback a console
                }
            };
        }

        // Fix para cualquier otra función problemática
        if (typeof window.updateConnectionStatus === 'function') {
            const originalUpdateStatus = window.updateConnectionStatus;
            window.updateConnectionStatus = function(status) {
                try {
                    return originalUpdateStatus.call(this, status);
                } catch (error) {
                    const element = safeQuerySelector('#connectionStatus');
                    if (element) {
                        element.textContent = status === 'connected' 
                            ? '✅ Conectado' 
                            : '❌ Desconectado';
                    }
                }
            };
        }

        console.log('✅ Fix de UI aplicado correctamente');
    }, 1000);
});