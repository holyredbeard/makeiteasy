import React from 'react';
import ViewToggle from './ViewToggle';
import DensityToggle from './DensityToggle';
import SortDropdown from './SortDropdown';

const RecipeListToolbar = ({ view, density, sort, onViewChange, onDensityChange, onSortChange }) => {
  return (
    <div className="w-full bg-white rounded-2xl border border-gray-200 shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out mb-6">
      <div className="flex items-center justify-between gap-4 px-5 py-3">
        <div className="flex items-center gap-4">
          <ViewToggle view={view} onViewChange={onViewChange} />
          <DensityToggle density={density} onDensityChange={onDensityChange} view={view} />
        </div>
        <div className="flex items-center gap-4">
          <SortDropdown sort={sort} onSortChange={onSortChange} />
        </div>
      </div>
    </div>
  );
};

export default RecipeListToolbar;
