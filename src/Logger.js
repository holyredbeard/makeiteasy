/**
 * DETALJERAT LOGGSYSTEM FÖR FOOD2GUIDE
 * 
 * Detta system loggar ALLT som händer i applikationen
 * och visar det både i webbläsarkonsolen och i UI:t
 */

class Logger {
  constructor() {
    this.logs = [];
    this.listeners = [];
    this.isEnabled = true;
    
    // Kör konsol-meddelande vid start
    this.info('🚀 FOOD2GUIDE LOGGER STARTAD - All aktivitet kommer att loggas här');
    this.info('💡 Öppna webbläsarkonsolen (F12) för att se ALLA loggar');
    
    // Logga när sidan laddas
    this.info(`📱 Sida laddad: ${window.location.href}`);
    this.info(`🌐 User Agent: ${navigator.userAgent}`);
    this.info(`⏰ Tid: ${new Date().toLocaleString('sv-SE')}`);
  }

  // Lägg till lyssnare för logguppdateringar
  addListener(callback) {
    this.listeners.push(callback);
  }

  // Ta bort lyssnare
  removeListener(callback) {
    this.listeners = this.listeners.filter(l => l !== callback);
  }

  // Meddela alla lyssnare om nya loggar
  notifyListeners() {
    this.listeners.forEach(callback => {
      try {
        callback([...this.logs]);
      } catch (error) {
        console.error('Logger listener error:', error);
      }
    });
  }

  // Skapa en loggpost
  createLogEntry(level, message, data = null) {
    const timestamp = new Date().toISOString();
    const timeFormatted = new Date().toLocaleTimeString('sv-SE');
    
    const logEntry = {
      id: Date.now() + Math.random(),
      timestamp,
      timeFormatted,
      level,
      message,
      data,
      stack: level === 'error' ? new Error().stack : null
    };

    this.logs.push(logEntry);
    
    // Begränsa antal loggar i minnet
    if (this.logs.length > 1000) {
      this.logs = this.logs.slice(-500);
    }

    this.notifyListeners();
    return logEntry;
  }

  // INFO-loggar (blå)
  info(message, data = null) {
    const entry = this.createLogEntry('info', message, data);
    console.log(`🔵 [${entry.timeFormatted}] INFO: ${message}`, data || '');
    return entry;
  }

  // SUCCESS-loggar (grön)
  success(message, data = null) {
    const entry = this.createLogEntry('success', message, data);
    console.log(`🟢 [${entry.timeFormatted}] SUCCESS: ${message}`, data || '');
    return entry;
  }

  // WARNING-loggar (gul)
  warn(message, data = null) {
    const entry = this.createLogEntry('warning', message, data);
    console.warn(`🟡 [${entry.timeFormatted}] WARNING: ${message}`, data || '');
    return entry;
  }

  // ERROR-loggar (röd)
  error(message, error = null, data = null) {
    const entry = this.createLogEntry('error', message, { error, data });
    console.error(`🔴 [${entry.timeFormatted}] ERROR: ${message}`, error || '', data || '');
    return entry;
  }

  // DEBUG-loggar (grå)
  debug(message, data = null) {
    const entry = this.createLogEntry('debug', message, data);
    console.log(`⚪ [${entry.timeFormatted}] DEBUG: ${message}`, data || '');
    return entry;
  }

  // API-anrop loggar
  apiCall(method, url, requestData = null) {
    const entry = this.createLogEntry('api', `${method} ${url}`, requestData);
    console.log(`📡 [${entry.timeFormatted}] API CALL: ${method} ${url}`, requestData || '');
    return entry;
  }

  // API-svar loggar
  apiResponse(method, url, status, responseData = null, error = null) {
    const level = status >= 400 ? 'error' : status >= 300 ? 'warning' : 'success';
    const emoji = status >= 400 ? '❌' : status >= 300 ? '⚠️' : '✅';
    const entry = this.createLogEntry(level, `${method} ${url} → ${status}`, { responseData, error });
    
    if (error) {
      console.error(`${emoji} [${entry.timeFormatted}] API ERROR: ${method} ${url} → ${status}`, error, responseData || '');
    } else {
      console.log(`${emoji} [${entry.timeFormatted}] API RESPONSE: ${method} ${url} → ${status}`, responseData || '');
    }
    return entry;
  }

  // Event-loggar
  event(eventName, data = null) {
    const entry = this.createLogEntry('event', `EVENT: ${eventName}`, data);
    console.log(`⚡ [${entry.timeFormatted}] EVENT: ${eventName}`, data || '');
    return entry;
  }

  // State-ändringar
  stateChange(component, oldState, newState) {
    const entry = this.createLogEntry('state', `STATE CHANGE: ${component}`, { oldState, newState });
    console.log(`🔄 [${entry.timeFormatted}] STATE CHANGE: ${component}`, { oldState, newState });
    return entry;
  }

  // Streaming-loggar
  stream(message, data = null) {
    const entry = this.createLogEntry('stream', message, data);
    console.log(`🌊 [${entry.timeFormatted}] STREAM: ${message}`, data || '');
    return entry;
  }

  // Performance-loggar
  performance(operation, duration, data = null) {
    const entry = this.createLogEntry('performance', `${operation} took ${duration}ms`, data);
    console.log(`⏱️ [${entry.timeFormatted}] PERFORMANCE: ${operation} took ${duration}ms`, data || '');
    return entry;
  }

  // Rensa alla loggar
  clear() {
    this.logs = [];
    this.notifyListeners();
    console.clear();
    this.info('🧹 Loggar rensade');
  }

  // Hämta alla loggar
  getAllLogs() {
    return [...this.logs];
  }

  // Hämta loggar efter level
  getLogsByLevel(level) {
    return this.logs.filter(log => log.level === level);
  }

  // Exportera loggar som JSON
  exportLogs() {
    const logsJson = JSON.stringify(this.logs, null, 2);
    const blob = new Blob([logsJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `food2guide-logs-${new Date().toISOString().slice(0,19)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    this.info('📥 Loggar exporterade till fil');
  }

  // Aktivera/inaktivera loggning
  setEnabled(enabled) {
    this.isEnabled = enabled;
    this.info(`🔧 Loggning ${enabled ? 'aktiverad' : 'inaktiverad'}`);
  }
}

// Skapa global logger-instans
const logger = new Logger();

// Fånga alla ohanterade fel
window.addEventListener('error', (event) => {
  logger.error('Ohanterat fel', event.error, {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno
  });
});

// Fånga alla ohanterade promise-fel
window.addEventListener('unhandledrejection', (event) => {
  logger.error('Ohanterat Promise-fel', event.reason);
});

// Logga när sidan lämnas
window.addEventListener('beforeunload', () => {
  logger.info('👋 Sida lämnas');
});

// Exportera logger
export default logger;