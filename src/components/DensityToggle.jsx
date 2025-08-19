import React from 'react';
import { Minus, Plus } from 'lucide-react';

const DensityToggle = ({ density, onDensityChange, view }) => {
  const isDisabled = view === 'list';
  
  return (
    <div className={`flex items-center rounded-full p-1 ${isDisabled ? 'bg-gray-50' : 'bg-gray-100'}`} role="group" aria-label="Layout density">
      <button
        onClick={() => !isDisabled && onDensityChange('minimal')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!isDisabled) onDensityChange('minimal');
          }
        }}
        disabled={isDisabled}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors ${
          isDisabled 
            ? 'text-gray-400 cursor-not-allowed'
            : density === 'minimal'
              ? 'bg-white text-[#5b8959] font-semibold shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
        }`}
        title={isDisabled ? "Density not available in list view" : "Minimal layout"}
        aria-label={isDisabled ? "Density not available in list view" : "Switch to minimal layout"}
        aria-pressed={density === 'minimal'}
      >
        <Minus className="w-4 h-4" />
        <span className="text-sm font-medium hidden sm:inline">Minimal</span>
      </button>
      <button
        onClick={() => !isDisabled && onDensityChange('detailed')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            if (!isDisabled) onDensityChange('detailed');
          }
        }}
        disabled={isDisabled}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors ${
          isDisabled 
            ? 'text-gray-400 cursor-not-allowed'
            : density === 'detailed'
              ? 'bg-white text-[#5b8959] font-semibold shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
        }`}
        title={isDisabled ? "Density not available in list view" : "Detailed layout"}
        aria-label={isDisabled ? "Density not available in list view" : "Switch to detailed layout"}
        aria-pressed={density === 'detailed'}
      >
        <Plus className="w-4 h-4" />
        <span className="text-sm font-medium hidden sm:inline">Detailed</span>
      </button>
    </div>
  );
};

export default DensityToggle;
