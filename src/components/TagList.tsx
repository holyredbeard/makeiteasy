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
  const [popoverPosition, setPopoverPosition] = useState({ top: 0, left: 0 });
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
    console.log('Toggle popover clicked, current state:', isPopoverOpen);
    
    if (!isPopoverOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      
      // Calculate initial position
      let top = rect.bottom + window.scrollY + 4;
      let left = rect.left + window.scrollX;
      
      // Ensure modal doesn't go off-screen to the right
      if (left + 200 > viewportWidth) { // 200px is approximate modal width
        left = Math.max(10, viewportWidth - 210);
      }
      
      // Ensure modal doesn't go off-screen to the left
      if (left < 10) {
        left = 10;
      }
      
      // If modal would go off-screen at bottom, position it above the button
      if (top + 240 > viewportHeight + window.scrollY) { // 240px is approximate modal height
        top = rect.top + window.scrollY - 244;
      }
      
      console.log('Setting popover position:', { top, left });
      setPopoverPosition({ top, left });
    }
    
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
    else if (labelLower === 'beef' || labelLower === 'steak') tagClass = 'bg-red-700 text-white border-red-700';
    else if (labelLower === 'pork' || labelLower === 'bacon' || labelLower === 'ham') tagClass = 'bg-pink-600 text-white border-pink-600';
    else if (labelLower === 'fish' || labelLower === 'salmon' || labelLower === 'tuna') tagClass = 'bg-blue-500 text-white border-blue-500';
    else if (labelLower === 'shrimp' || labelLower === 'crab' || labelLower === 'lobster') tagClass = 'bg-orange-400 text-white border-orange-400';
    else if (labelLower === 'squid' || labelLower === 'octopus' || labelLower === 'calamari') tagClass = 'bg-purple-500 text-white border-purple-500';
    else if (labelLower === 'apple' || labelLower === 'banana' || labelLower === 'orange') tagClass = 'bg-green-500 text-white border-green-500';
    else if (labelLower === 'carrot' || labelLower === 'broccoli' || labelLower === 'spinach') tagClass = 'bg-green-600 text-white border-green-600';
    else if (labelLower === 'tomato' || labelLower === 'bellpepper' || labelLower === 'jalapeno') tagClass = 'bg-red-500 text-white border-red-500';
    else if (labelLower === 'potato' || labelLower === 'sweetpotato') tagClass = 'bg-amber-700 text-white border-amber-700';
    else if (labelLower === 'onion' || labelLower === 'garlic') tagClass = 'bg-purple-600 text-white border-purple-600';
    else if (labelLower === 'bread' || labelLower === 'toast' || labelLower === 'bagel') tagClass = 'bg-amber-500 text-white border-amber-500';
    else if (labelLower === 'cake' || labelLower === 'cookie' || labelLower === 'dessert') tagClass = 'bg-pink-400 text-white border-pink-400';
    else if (labelLower === 'coffee' || labelLower === 'tea') tagClass = 'bg-amber-800 text-white border-amber-800';
    else if (labelLower === 'beer' || labelLower === 'whiskey' || labelLower === 'vodka') tagClass = 'bg-amber-800 text-white border-amber-800';

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
        {labelLower === 'pasta' && <i className="fa-solid fa-utensils mr-1"></i>}
        {labelLower === 'beef' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
        {labelLower === 'steak' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
                      {labelLower === 'pork' && <i className="fa-solid fa-bacon mr-1"></i>}
        {labelLower === 'bacon' && <i className="fa-solid fa-bacon mr-1"></i>}
        {labelLower === 'ham' && <i className="fa-solid fa-bacon mr-1"></i>}
        {labelLower === 'fish' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'salmon' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'tuna' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'shrimp' && <i className="fa-solid fa-shrimp mr-1"></i>}
        {labelLower === 'crab' && <i className="fa-solid fa-shrimp mr-1"></i>}
        {labelLower === 'lobster' && <i className="fa-solid fa-shrimp mr-1"></i>}
        {labelLower === 'squid' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'octopus' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'calamari' && <i className="fa-solid fa-fish mr-1"></i>}
        {labelLower === 'apple' && <i className="fa-solid fa-apple-whole mr-1"></i>}
        {labelLower === 'banana' && <i className="fa-solid fa-apple-whole mr-1"></i>}
        {labelLower === 'orange' && <i className="fa-solid fa-apple-whole mr-1"></i>}
        {labelLower === 'carrot' && <i className="fa-solid fa-carrot mr-1"></i>}
        {labelLower === 'broccoli' && <i className="fa-solid fa-seedling mr-1"></i>}
        {labelLower === 'spinach' && <i className="fa-solid fa-leaf mr-1"></i>}
        {labelLower === 'tomato' && <i className="fa-solid fa-apple-whole mr-1"></i>}
        {labelLower === 'bellpepper' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
        {labelLower === 'jalapeno' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
        {labelLower === 'potato' && <i className="fa-solid fa-seedling mr-1"></i>}
        {labelLower === 'sweetpotato' && <i className="fa-solid fa-seedling mr-1"></i>}
        {labelLower === 'onion' && <i className="fa-solid fa-seedling mr-1"></i>}
        {labelLower === 'garlic' && <i className="fa-solid fa-seedling mr-1"></i>}
        {labelLower === 'bread' && <i className="fa-solid fa-bread-slice mr-1"></i>}
        {labelLower === 'toast' && <i className="fa-solid fa-bread-slice mr-1"></i>}
        {labelLower === 'bagel' && <i className="fa-solid fa-bread-slice mr-1"></i>}
        {labelLower === 'cake' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
        {labelLower === 'cookie' && <i className="fa-solid fa-cookie mr-1"></i>}
        {labelLower === 'dessert' && <i className="fa-solid fa-ice-cream mr-1"></i>}
        {labelLower === 'coffee' && <i className="fa-solid fa-mug-hot mr-1"></i>}
        {labelLower === 'tea' && <i className="fa-solid fa-mug-hot mr-1"></i>}
        {labelLower === 'beer' && <i className="fa-solid fa-beer mr-1"></i>}
        {labelLower === 'whiskey' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
                      {labelLower === 'vodka' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'lamb' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'turkey' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'duck' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'cod' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'halibut' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'mackerel' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'sardines' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'anchovies' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'mussel' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'clam' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'oyster' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'scallop' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'tilapia' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'trout' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'bass' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'snapper' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'grouper' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'swordfish' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'milk' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'yogurt' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'butter' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'cream' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'sourcream' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'cottagecheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'ricotta' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'mozzarella' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'cheddar' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'parmesan' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'feta' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'gouda' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'brie' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'bluecheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'swiss' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'provolone' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'havarti' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'manchego' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'pecorino' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'asiago' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'lemon' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'lime' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'grape' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'strawberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'blueberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'raspberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'blackberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'peach' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'pear' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'plum' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'apricot' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'cherry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'pineapple' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'mango' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'kiwi' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'avocado' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'coconut' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'watermelon' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'lettuce' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'kale' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cabbage' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cauliflower' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'zucchini' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'cucumber' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'eggplant' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'mushroom' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'corn' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'peas' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'beans' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'lentils' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'chickpeas' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'quinoa' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'rice' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'pasta' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'noodle' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'flour' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'sugar' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'honey' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'maple' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'oliveoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'vegetableoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'coconutoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'sesameoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'soysauce' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'vinegar' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'mustard' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'ketchup' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'mayonnaise' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'hot sauce' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'sriracha' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'salt' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'pepper' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'basil' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'oregano' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'thyme' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'rosemary' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'sage' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'parsley' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cilantro' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'dill' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'mint' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cumin' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'coriander' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'turmeric' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'ginger' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'cinnamon' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'nutmeg' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'paprika' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'chili' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'cayenne' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'italian' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'mexican' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'indian' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'thai' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'japanese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'swedish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'chinese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'french' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'greek' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'turkish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'mediterranean' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'vietnamese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'korean' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'moroccan' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'american' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'british' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'german' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'spanish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'middleeastern' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'glutenfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'dairyfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'lowcarb' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'highprotein' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'keto' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'paleo' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'sugarfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'quick' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'easy' && <i className="fa-solid fa-thumbs-up mr-1"></i>}
              {labelLower === 'healthy' && <i className="fa-solid fa-heart mr-1"></i>}
              {labelLower === 'savory' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'comfortfood' && <i className="fa-solid fa-heart mr-1"></i>}
              {labelLower === 'kidfriendly' && <i className="fa-solid fa-child mr-1"></i>}
              {labelLower === 'fingerfood' && <i className="fa-solid fa-hand mr-1"></i>}
              {labelLower === 'mealprep' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'budget' && <i className="fa-solid fa-dollar-sign mr-1"></i>}
              {labelLower === 'festive' && <i className="fa-solid fa-star mr-1"></i>}
              {labelLower === 'seasonal' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'holiday' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'summer' && <i className="fa-solid fa-sun mr-1"></i>}
              {labelLower === 'winter' && <i className="fa-solid fa-snowflake mr-1"></i>}
              {labelLower === 'autumn' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'spring' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'brunch' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'snack' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'side' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'appetizer' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'main' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'drink' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'cocktail' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'mocktail' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'roasted' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'boiled' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'steamed' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'raw' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'poached' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'braised' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'slowcooked' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'barbecue' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'smoked' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'blanched' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'seared' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'soup' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'salad' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'stirfry' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'baked' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'grilled' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'fried' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'breakfast' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'lunch' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'dinner' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'pizza' && <i className="fa-solid fa-pizza-slice mr-1"></i>}
              {labelLower === 'burger' && <i className="fa-solid fa-burger mr-1"></i>}
              {labelLower === 'tacos' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'sushi' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'curry' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'stew' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'sandwich' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'wrap' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'casserole' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'pie' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'quiche' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'omelette' && <i className="fa-solid fa-egg mr-1"></i>}
              {labelLower === 'pancake' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'waffle' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'crepe' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'dumpling' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'skewer' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'flatbread' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'bowl' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'onepot' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'gratin' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'stewpot' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              
              <span className="font-medium">{label.charAt(0).toUpperCase() + label.slice(1)}</span>
      </span>
    );
  };

  return (
    <div className={`flex flex-wrap gap-2 ${className}`} onClick={(e) => e.stopPropagation()}>
      {/* Render visible tags */}
      {visible.map((tag, index) => renderTag(tag, index))}
      
      {/* Render overflow badge if there are hidden tags */}
      {(() => { console.log('Hidden tags count:', hidden.length, 'Hidden tags:', hidden); return null; })()}
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
             (() => { console.log('Rendering popover, position:', popoverPosition); return null; })(),
             <div
               ref={popoverRef}
               id="tag-popover"
               role="dialog"
               aria-label="Hidden tags"
               style={{
                 top: `${popoverPosition.top}px`,
                 left: `${popoverPosition.left}px`
               }}
               className="fixed z-[9999] bg-white/90 backdrop-blur rounded-lg shadow-lg border border-gray-200 p-3 max-h-60 overflow-y-auto min-w-48"
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
