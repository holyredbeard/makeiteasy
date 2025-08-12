import React, { useState, useEffect, useRef } from 'react';

const ScrapingStatus = ({ isActive, onComplete }) => {
  const [currentMessageIndex, setCurrentMessageIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(false);
  const intervalRef = useRef(null);
  const timeoutRef = useRef(null);

  const statusMessages = [
    "Analyzing the recipe page...",
    "Looking for ingredients...",
    "Extracting instructions...",
    "Reading nutrition facts...",
    "Finalizing recipe format..."
  ];

  useEffect(() => {
    if (isActive) {
      // Start showing messages after 2 seconds
      timeoutRef.current = setTimeout(() => {
        setIsVisible(true);
        startMessageCycle();
      }, 2000);
    } else {
      // Clean up when scraping completes
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      setIsVisible(false);
      setCurrentMessageIndex(0);
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isActive]);

  const startMessageCycle = () => {
    intervalRef.current = setInterval(() => {
      setCurrentMessageIndex((prevIndex) => {
        const nextIndex = (prevIndex + 1) % statusMessages.length;
        return nextIndex;
      });
    }, 4500); // Change message every 4.5 seconds
  };

  if (!isActive) {
    return null;
  }

  return (
    <div className="text-center">
      <div className="flex justify-center mb-4">
        <div className="relative">
          <div className="animate-spin rounded-full h-12 w-12" style={{ filter: 'drop-shadow(0 2px 6px rgba(251,113,133,0.35))' }}>
            <svg width="48" height="48" viewBox="0 0 48 48">
              <circle cx="24" cy="24" r="18" stroke="#fecaca" strokeWidth="8" fill="none" />
              <circle cx="24" cy="24" r="18" stroke="#fb7185" strokeWidth="8" strokeLinecap="round" fill="none" strokeDasharray={`${2*Math.PI*18*0.28} ${2*Math.PI*18}`} />
            </svg>
          </div>
        </div>
      </div>
      
      <h3 className="text-xl font-bold mb-2 text-gray-800">Processing Recipe</h3>
      
      {/* Status message with fade transition */}
      <div className="h-8 flex items-center justify-center">
        <p 
          className={`text-gray-600 transition-opacity duration-500 ${
            isVisible ? 'opacity-100' : 'opacity-0'
          }`}
        >
          {isVisible ? statusMessages[currentMessageIndex] : "Initializing..."}
        </p>
      </div>
      
      {/* Progress dots */}
      <div className="flex justify-center mt-4 space-x-2">
        {statusMessages.map((_, index) => (
          <div
            key={index}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              isVisible && index === currentMessageIndex
                ? 'bg-rose-500 scale-125'
                : isVisible && index < currentMessageIndex
                ? 'bg-orange-300'
                : 'bg-gray-300'
            }`}
          />
        ))}
      </div>
      
      {/* Subtle loading text */}
      <p className="text-sm text-gray-400 mt-4">
        This may take a few moments...
      </p>
    </div>
  );
};

export default ScrapingStatus; 