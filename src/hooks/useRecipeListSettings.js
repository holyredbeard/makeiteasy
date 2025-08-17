import { useState, useEffect } from 'react';

const STORAGE_KEY = 'recipe-list-settings';

const defaultSettings = {
  view: 'grid',
  density: 'detailed',
  sort: 'likes'
};

export const useRecipeListSettings = () => {
  const [settings, setSettings] = useState(defaultSettings);

  // Ladda inställningar från localStorage vid mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        setSettings({ ...defaultSettings, ...parsed });
      }
    } catch (error) {
      console.warn('Failed to load recipe list settings from localStorage:', error);
    }
  }, []);

  // Spara inställningar till localStorage
  const saveSettings = (newSettings) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings));
    } catch (error) {
      console.warn('Failed to save recipe list settings to localStorage:', error);
    }
  };

  const updateView = (view) => {
    const newSettings = { ...settings, view };
    setSettings(newSettings);
    saveSettings(newSettings);
  };

  const updateDensity = (density) => {
    const newSettings = { ...settings, density };
    setSettings(newSettings);
    saveSettings(newSettings);
  };

  const updateSort = (sort) => {
    const newSettings = { ...settings, sort };
    setSettings(newSettings);
    saveSettings(newSettings);
  };

  return {
    view: settings.view,
    density: settings.density,
    sort: settings.sort,
    updateView,
    updateDensity,
    updateSort
  };
};
