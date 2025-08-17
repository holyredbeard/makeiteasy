import { useMemo } from 'react';

/**
 * Hook that splits tags into visible and hidden arrays based on maxVisible count
 * @param {Array} tags - Array of tag objects
 * @param {number} maxVisible - Maximum number of tags to show
 * @returns {Object} { visible, hidden }
 */
export function useOverflowTags(tags = [], maxVisible = 3) {
  return useMemo(() => {
    if (!Array.isArray(tags) || tags.length === 0) {
      return { visible: [], hidden: [] };
    }

    const visible = tags.slice(0, maxVisible);
    const hidden = tags.slice(maxVisible);

    return { visible, hidden };
  }, [tags, maxVisible]);
}
