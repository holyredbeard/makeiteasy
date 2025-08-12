import React from 'react';

/**
 * Animated circular progress spinner.
 * Default style matches an orange ring with a softer background ring.
 */
export default function Spinner({ size = 48, color = '#f97316', background = '#fecaca', thickness = 8, className = '' }) {
  const radius = (size - thickness) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const arcLength = circumference * 0.28; // visible arc portion (28%)

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={`animate-spin ${className}`}
      style={{ animationDuration: '1s' }}
      aria-label="Loading"
    >
      {/* Background ring */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        stroke={background}
        strokeWidth={thickness}
        fill="none"
      />
      {/* Foreground arc */}
      <circle
        cx={center}
        cy={center}
        r={radius}
        stroke={color}
        strokeWidth={thickness}
        strokeLinecap="round"
        fill="none"
        strokeDasharray={`${arcLength} ${circumference}`}
        strokeDashoffset="0"
      />
    </svg>
  );
}


