import React from 'react';
import { Minus, Plus } from 'lucide-react';

const DensityToggle = ({ density, onDensityChange }) => {
  return (
    <div className="flex bg-gray-100 rounded-lg p-1" role="group" aria-label="Layout density">
      <button
        onClick={() => onDensityChange('minimal')}
        className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
          density === 'minimal'
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
        aria-pressed={density === 'minimal'}
        title="Minimal layout"
      >
        <Minus className="w-4 h-4" />
        <span className="hidden sm:inline">Minimal</span>
      </button>
      <button
        onClick={() => onDensityChange('detailed')}
        className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
          density === 'detailed'
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
        aria-pressed={density === 'detailed'}
        title="Detailed layout"
      >
        <Plus className="w-4 h-4" />
        <span className="hidden sm:inline">Detailed</span>
      </button>
    </div>
  );
};

export default DensityToggle;
