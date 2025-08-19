import React from 'react';

export default function RecipeSection({ id, title, children, className = '', titleHidden = false, variant = 'card' }) {
  const wrapperClass = variant === 'plain'
    ? `scroll-mt-[88px] relative p-0 mb-6 ${className}`
    : `scroll-mt-[88px] relative rounded-2xl border border-gray-200 p-4 sm:p-6 mb-6 !bg-white card-hard-shadow ${className}`;

  // Only set aria-labelledby if title is a string (for proper accessibility)
  const ariaProps = title && typeof title === 'string' ? { 'aria-labelledby': `${id}-h2` } : {};

  return (
    <section 
      id={id} 
      role="region" 
      {...ariaProps}
      className={wrapperClass}
      style={variant === 'card' ? { backgroundColor: 'white', background: 'white' } : {}}
    >
      {title && (
        <h2 id={`${id}-h2`} tabIndex={-1} className={`${titleHidden ? 'sr-only' : 'scroll-mt-[88px] text-xl font-semibold mb-3 flex items-center gap-2'}`}>
          {typeof title === 'string' ? <span>{title}</span> : title}
        </h2>
      )}
      {children}
    </section>
  );
}


