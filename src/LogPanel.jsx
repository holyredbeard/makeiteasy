import React, { useState, useEffect, useRef } from 'react';
import { 
  XMarkIcon, 
  ChevronUpIcon, 
  ChevronDownIcon,
  DocumentArrowDownIcon,
  TrashIcon,
  AdjustmentsHorizontalIcon,
  MagnifyingGlassIcon
} from '@heroicons/react/24/outline';
import logger from './Logger';

const LogPanel = ({ isVisible, onToggle }) => {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState('all'); // all, info, warning, error, success, api, event
  const [searchTerm, setSearchTerm] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logContainerRef = useRef(null);

  useEffect(() => {
    // Lyssna på logguppdateringar
    const handleLogUpdate = (newLogs) => {
      setLogs(newLogs);
    };

    logger.addListener(handleLogUpdate);
    setLogs(logger.getAllLogs());

    return () => {
      logger.removeListener(handleLogUpdate);
    };
  }, []);

  // Auto-scroll till botten när nya loggar kommer
  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Filtrera loggar
  const filteredLogs = logs.filter(log => {
    const matchesFilter = filter === 'all' || log.level === filter;
    const matchesSearch = !searchTerm || 
      log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (log.data && JSON.stringify(log.data).toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesFilter && matchesSearch;
  });

  const getLogIcon = (level) => {
    switch (level) {
      case 'error': return '🔴';
      case 'warning': return '🟡';
      case 'success': return '🟢';
      case 'info': return '🔵';
      case 'debug': return '⚪';
      case 'api': return '📡';
      case 'event': return '⚡';
      case 'stream': return '🌊';
      case 'performance': return '⏱️';
      case 'state': return '🔄';
      default: return '📝';
    }
  };

  const getLogColor = (level) => {
    switch (level) {
      case 'error': return 'text-red-400 bg-red-900/20';
      case 'warning': return 'text-yellow-400 bg-yellow-900/20';
      case 'success': return 'text-green-400 bg-green-900/20';
      case 'info': return 'text-blue-400 bg-blue-900/20';
      case 'debug': return 'text-gray-400 bg-gray-900/20';
      case 'api': return 'text-purple-400 bg-purple-900/20';
      case 'event': return 'text-orange-400 bg-orange-900/20';
      case 'stream': return 'text-cyan-400 bg-cyan-900/20';
      case 'performance': return 'text-pink-400 bg-pink-900/20';
      case 'state': return 'text-indigo-400 bg-indigo-900/20';
      default: return 'text-gray-400 bg-gray-900/20';
    }
  };

  if (!isVisible) return null;

  return (
    <div className={`fixed bottom-4 right-4 bg-black/95 text-white rounded-lg shadow-2xl border border-gray-700 z-50 transition-all duration-300 ${
      isExpanded ? 'w-[800px] h-[600px]' : 'w-[400px] h-[300px]'
    }`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span className="text-lg">🔍</span>
          <h3 className="font-bold text-green-400">FOOD2GUIDE LOGGAR</h3>
          <span className="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
            {filteredLogs.length}/{logs.length}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-gray-400 hover:text-white transition-colors"
            title="Expandera/Krympa"
          >
            {isExpanded ? <ChevronDownIcon className="h-5 w-5" /> : <ChevronUpIcon className="h-5 w-5" />}
          </button>
          <button
            onClick={onToggle}
            className="text-gray-400 hover:text-white transition-colors"
            title="Stäng loggpanel"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="p-3 border-b border-gray-700 space-y-2">
        <div className="flex gap-2 flex-wrap">
          {['all', 'error', 'warning', 'success', 'info', 'api', 'event', 'stream'].map(level => (
            <button
              key={level}
              onClick={() => setFilter(level)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                filter === level 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {level.toUpperCase()}
            </button>
          ))}
        </div>
        
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="h-4 w-4 absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Sök i loggar..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1 text-xs bg-gray-800 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:border-green-500"
            />
          </div>
          <label className="flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-3 h-3"
            />
            Auto-scroll
          </label>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => logger.clear()}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600 hover:bg-red-700 rounded transition-colors"
            title="Rensa alla loggar"
          >
            <TrashIcon className="h-3 w-3" />
            Rensa
          </button>
          <button
            onClick={() => logger.exportLogs()}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 rounded transition-colors"
            title="Exportera loggar till fil"
          >
            <DocumentArrowDownIcon className="h-3 w-3" />
            Exportera
          </button>
        </div>
      </div>

      {/* Logs */}
      <div 
        ref={logContainerRef}
        className="flex-1 overflow-y-auto p-2 space-y-1"
        style={{ height: isExpanded ? '460px' : '160px' }}
      >
        {filteredLogs.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {logs.length === 0 ? 'Inga loggar än...' : 'Inga loggar matchar filtret'}
          </div>
        ) : (
          filteredLogs.map((log) => (
            <div 
              key={log.id} 
              className={`p-2 rounded text-xs border-l-4 ${getLogColor(log.level)}`}
            >
              <div className="flex items-start gap-2">
                <span className="text-base leading-none">{getLogIcon(log.level)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-gray-400 font-mono text-xs">
                      {log.timeFormatted}
                    </span>
                    <span className="text-xs font-semibold uppercase">
                      {log.level}
                    </span>
                  </div>
                  <div className="text-white break-words">
                    {log.message}
                  </div>
                  {log.data && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-gray-400 hover:text-white">
                        Visa data
                      </summary>
                      <pre className="mt-1 p-2 bg-black/50 rounded text-xs overflow-x-auto">
                        {typeof log.data === 'string' 
                          ? log.data 
                          : JSON.stringify(log.data, null, 2)
                        }
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogPanel;