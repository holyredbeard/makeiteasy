import React from 'react';

export default function RecipeSubnav({ items = [], activeId, onClickAnchor }) {
  const [isStuck, setIsStuck] = React.useState(false);
  const sentinelRef = React.useRef(null);

  React.useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return undefined;
    const obs = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        setIsStuck(!e.isIntersecting);
      },
      { root: null, threshold: [1], rootMargin: '0px 0px 0px 0px' }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  if (!items || items.length === 0) return null;
  return (
    <>
      <div ref={sentinelRef} aria-hidden className="h-0" />
      <nav
        aria-label="Recipe sections"
        className={`sticky z-30 top-[62px] bg-white border-b border-gray-200 w-full ${
          isStuck ? 'shadow-sm' : ''
        }`}
      >
        <div className="relative py-2 md:py-3">
          <ul className="flex items-center gap-2 md:gap-3 overflow-x-auto no-scrollbar snap-x snap-mandatory w-full">
            {items.map((it) => (
              <li key={it.id} className="snap-start">
                <a
                  href={`#${it.id}`}
                  data-active={activeId === it.id}
                  onClick={(e) => { e.preventDefault(); onClickAnchor?.(it.id); }}
                  className="px-3 md:px-4 py-1.5 md:py-2 rounded-full text-sm md:text-base font-medium transition-colors text-gray-600 bg-gray-100 hover:bg-gray-200 data-[active=true]:bg-gray-900 data-[active=true]:text-white"
                >
                  {it.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      </nav>
    </>
  );
}


