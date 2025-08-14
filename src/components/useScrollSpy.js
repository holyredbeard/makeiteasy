import { useEffect, useRef, useState } from 'react';

// ScrollSpy that picks the section whose top is closest to (but not greater than) the viewport top + offset.
// More stable than pure IntersectionObserver for tall/overlapping sections.
export default function useScrollSpy(sectionIds = [], offset = 80) {
  const [activeId, setActiveId] = useState(sectionIds[0] || null);
  const rafRef = useRef(null);

  useEffect(() => {
    const ids = (sectionIds || []).slice();
    if (ids.length === 0) return undefined;

    const getTop = (el) => {
      const rect = el.getBoundingClientRect();
      return rect.top + window.pageYOffset;
    };

    const compute = () => {
      rafRef.current = null;
      try {
        const current = window.pageYOffset + offset + 1;
        let bestId = ids[0];
        let bestTop = -Infinity;
        for (const id of ids) {
          const el = document.getElementById(id);
          if (!el) continue;
          const top = getTop(el);
          if (top <= current && top > bestTop) {
            bestTop = top; bestId = id;
          }
        }
        if (bestId && bestId !== activeId) setActiveId(bestId);
      } catch {}
    };

    const onScroll = () => {
      if (rafRef.current) return;
      rafRef.current = requestAnimationFrame(compute);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    // initial
    compute();
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [JSON.stringify(sectionIds), offset, activeId]);

  return activeId;
}


