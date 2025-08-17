import React from 'react';
import ViewToggle from './ViewToggle';
import DensityToggle from './DensityToggle';
import SortDropdown from './SortDropdown';

const RecipeListToolbar = ({ view, density, sort, onViewChange, onDensityChange, onSortChange }) => {
  return (
    <div className="flex items-center justify-between mb-6 p-4 bg-white rounded-lg border border-gray-200">
      <div className="flex items-center gap-4">
        <ViewToggle view={view} onViewChange={onViewChange} />
        <DensityToggle density={density} onDensityChange={onDensityChange} />
      </div>
      <div className="flex items-center gap-4">
        <SortDropdown sort={sort} onSortChange={onSortChange} />
      </div>
    </div>
  );
};

export default RecipeListToolbar;
