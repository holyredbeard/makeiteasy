import React from 'react';
import { ChevronDown } from 'lucide-react';

const SortDropdown = ({ sort, onSortChange }) => {
  const sortOptions = [
    { value: 'likes', label: 'Most liked' },
    { value: 'newest', label: 'Newest' },
    { value: 'rating', label: 'Highest rated' },
    { value: 'cooked', label: 'Most cooked' },
    { value: 'alphabetical', label: 'A–Z' }
  ];

  return (
    <div className="relative">
      <label htmlFor="sort-select" className="sr-only">
        Sort
      </label>
      <select
        id="sort-select"
        value={sort}
        onChange={(e) => onSortChange(e.target.value)}
        className="appearance-none bg-white border border-gray-300 rounded-lg px-3 py-2 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        aria-label="Sort"
      >
        {sortOptions.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
    </div>
  );
};

export default SortDropdown;
