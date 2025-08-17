import React, { useState, useRef, useEffect } from 'react';
import { useOverflowTags } from '../hooks/useOverflowTags';

interface Tag {
  label?: string;
  keyword?: string;
  type?: string;
  cls?: string;
}

interface TagListProps {
  tags: Tag[];
  maxVisible?: number;
  onFilterByChip?: (tag: string) => void;
  className?: string;
}

export default function TagList({ 
  tags, 
  maxVisible = 3, 
  onFilterByChip, 
  className = '' 
}: TagListProps) {
  const { visible, hidden } = useOverflowTags(tags, maxVisible);
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isPopoverOpen) {
        setIsPopoverOpen(false);
        buttonRef.current?.focus();
      }
    };

    if (isPopoverOpen) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [isPopoverOpen]);

  // Close popover on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        isPopoverOpen &&
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setIsPopoverOpen(false);
        buttonRef.current.focus();
      }
    };

    if (isPopoverOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isPopoverOpen]);

  // Focus management for popover
  useEffect(() => {
    if (isPopoverOpen && popoverRef.current) {
      const firstFocusable = popoverRef.current.querySelector('button, [tabindex]:not([tabindex="-1"])') as HTMLElement;
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }
  }, [isPopoverOpen]);

  const togglePopover = (e) => {
    e.stopPropagation();
    setIsPopoverOpen(!isPopoverOpen);
  };

  const renderTag = (tag: Tag, index: number) => {
    const label = tag.label || tag.keyword || '';
    const labelLower = label.toLowerCase();
    
    // Get tag styling based on type or use default
    let tagClass = tag.cls || 'bg-gray-100 text-gray-700 border border-gray-200';
    
    // Apply specific styling for known tags
    if (labelLower === 'vegan') tagClass = 'bg-emerald-600 text-white border-emerald-600';
    else if (labelLower === 'vegetarian') tagClass = 'bg-lime-600 text-white border-lime-600';
    else if (labelLower === 'pescatarian') tagClass = 'bg-sky-600 text-white border-sky-600';
    else if (labelLower === 'zesty') tagClass = 'bg-yellow-500 text-white border-yellow-500';
    else if (labelLower === 'seafood') tagClass = 'bg-blue-600 text-white border-blue-600';
    else if (labelLower === 'fastfood') tagClass = 'bg-orange-500 text-white border-orange-500';
    else if (labelLower === 'spicy') tagClass = 'bg-red-600 text-white border-red-600';
    else if (labelLower === 'chicken') tagClass = 'bg-amber-600 text-white border-amber-600';
    else if (labelLower === 'eggs') tagClass = 'bg-yellow-400 text-white border-yellow-400';
    else if (labelLower === 'cheese') tagClass = 'bg-yellow-300 text-gray-800 border-yellow-300';
    else if (labelLower === 'fruits') tagClass = 'bg-pink-500 text-white border-pink-500';
    else if (labelLower === 'wine') tagClass = 'bg-purple-600 text-white border-purple-600';
    else if (labelLower === 'pasta') tagClass = 'bg-orange-600 text-white border-orange-600';

    return (
      <span 
        key={`${label}-${index}`} 
        className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${tagClass} cursor-pointer hover:opacity-90 transition-opacity hover:scale-105`}
        onClick={(e) => { 
          e.stopPropagation(); 
          if (typeof onFilterByChip === 'function') onFilterByChip(label); 
        }}
        title={`Filter by ${label}`}
      >
        {/* Icons for specific tags */}
        {labelLower === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
        {labelLower === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
        {labelLower === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
        {labelLower === 'pescatarian' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
        {labelLower === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
        {labelLower === 'spicy' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
        {labelLower === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
        {labelLower === 'eggs' && <i className="fa-solid fa-egg mr-1"></i>}
        {labelLower === 'cheese' && <i className="fa-solid fa-cheese mr-1"></i>}
        {labelLower === 'fruits' && <i className="fa-solid fa-apple-whole mr-1"></i>}
        {labelLower === 'wine' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
        {labelLower === 'pasta' && <i className="fa-solid fa-bacon mr-1"></i>}
        
        <span className="font-medium">{label.charAt(0).toUpperCase() + label.slice(1)}</span>
      </span>
    );
  };

  return (
    <div className={`flex flex-wrap gap-2 ${className}`} onClick={(e) => e.stopPropagation()}>
      {/* Render visible tags */}
      {visible.map((tag, index) => renderTag(tag, index))}
      
      {/* Render overflow badge if there are hidden tags */}
      {hidden.length > 0 && (
        <div className="relative">
          <button
            ref={buttonRef}
            onClick={(e) => togglePopover(e)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                togglePopover(e);
              }
            }}
            aria-haspopup="dialog"
            aria-expanded={isPopoverOpen}
            aria-controls="tag-popover"
            className="text-xs px-2 py-1 rounded-full bg-gray-200 text-gray-700 hover:bg-gray-300 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          >
            +{hidden.length}
          </button>
          
                     {/* Popover */}
           {isPopoverOpen && (
             <div
               ref={popoverRef}
               id="tag-popover"
               role="dialog"
               aria-label="Hidden tags"
               className="absolute top-full left-0 mt-1 z-50 bg-white rounded-lg shadow-lg border border-gray-200 p-3 max-h-60 overflow-y-auto min-w-48"
               onClick={(e) => e.stopPropagation()}
             >
              <div className="flex flex-wrap gap-2">
                {hidden.map((tag, index) => renderTag(tag, index))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
