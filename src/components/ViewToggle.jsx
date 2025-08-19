import React from 'react';
import { Grid3X3, List } from 'lucide-react';

const ViewToggle = ({ view, onViewChange }) => {
  return (
    <div className="flex items-center rounded-full bg-gray-100 p-1" role="group" aria-label="View mode">
      <button
        onClick={() => onViewChange('grid')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onViewChange('grid');
          }
        }}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors ${
          view === 'grid'
            ? 'bg-white text-[#5b8959] font-semibold shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
        title="Switch to grid layout"
        aria-label="Switch to grid layout"
        aria-pressed={view === 'grid'}
      >
        <Grid3X3 className="w-4 h-4" />
        <span className="text-sm font-medium hidden sm:inline">Grid</span>
      </button>
      <button
        onClick={() => onViewChange('list')}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onViewChange('list');
          }
        }}
        className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full transition-colors ${
          view === 'list'
            ? 'bg-white text-[#5b8959] font-semibold shadow-sm'
            : 'text-gray-600 hover:text-gray-900'
        }`}
        title="Switch to list layout"
        aria-label="Switch to list layout"
        aria-pressed={view === 'list'}
      >
        <List className="w-4 h-4" />
        <span className="text-sm font-medium hidden sm:inline">List</span>
      </button>
    </div>
  );
};

export default ViewToggle;
