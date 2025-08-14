import React from 'react';

export default function RecipeSection({ id, title, children, className = '', titleHidden = false, variant = 'card' }) {
  const wrapperClass = variant === 'plain'
    ? `scroll-mt-[88px] relative p-0 mb-6 ${className}`
    : `scroll-mt-[88px] relative rounded-2xl border border-black/5 shadow-sm p-4 sm:p-6 mb-6 ${className}`;

  return (
    <section 
      id={id} 
      role="region" 
      {...(title ? { 'aria-labelledby': `${id}-h2` } : {})} 
      className={wrapperClass}
      style={variant === 'card' ? { background: 'rgb(250 250 250 / 95%)' } : {}}
    >
      {title && (
        <h2 id={`${id}-h2`} tabIndex={-1} className={`${titleHidden ? 'sr-only' : 'scroll-mt-[88px] text-xl font-semibold mb-3 flex items-center gap-2'}`}>
          <span>{title}</span>
        </h2>
      )}
      {children}
    </section>
  );
}


