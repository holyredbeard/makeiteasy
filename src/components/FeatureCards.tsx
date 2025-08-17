import React from 'react';
import { Camera, RefreshCcw, Apple } from 'lucide-react';

interface FeatureCard {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  colorTheme: {
    bg: string;
    ring: string;
    text: string;
    border?: string;
  };
  bullets: string[];
}

interface FeatureCardsProps {
  variant?: 'subtle' | 'border';
}

const features: FeatureCard[] = [
  {
    id: 'video-to-recipe',
    title: 'Video to Recipe',
    icon: Camera,
    colorTheme: {
      bg: 'bg-sky-50 dark:bg-sky-900/30',
      ring: 'ring-sky-200/60 dark:ring-sky-700',
      text: 'text-sky-600 dark:text-sky-300',
      border: 'border-sky-200'
    },
    bullets: [
      'Paste a video link → clean recipe (ingredients + steps)',
      'Save to collections or share with friends',
      'Auto-detect quantities & cooking times',
      'Printable version'
    ]
  },
  {
    id: 'smart-conversions',
    title: 'Smart Conversions',
    icon: RefreshCcw,
    colorTheme: {
      bg: 'bg-amber-50 dark:bg-amber-900/30',
      ring: 'ring-amber-200/60 dark:ring-amber-700',
      text: 'text-amber-600 dark:text-amber-300',
      border: 'border-amber-200'
    },
    bullets: [
      'Scale servings and swap ingredients',
      'One-click presets (Vegan, Gluten-free, etc.)',
      'Highlights what changed and keeps instructions consistent'
    ]
  },
  {
    id: 'nutrition-analysis',
    title: 'Nutrition Analysis',
    icon: Apple,
    colorTheme: {
      bg: 'bg-emerald-50 dark:bg-emerald-900/30',
      ring: 'ring-emerald-200/60 dark:ring-emerald-700',
      text: 'text-emerald-600 dark:text-emerald-300',
      border: 'border-emerald-200'
    },
    bullets: [
      'Automatic calories & macros per serving',
      'Clear nutrition chips in recipe view',
      'Great for tracking goals or weekly meal planning'
    ]
  }
];

const FeatureCards: React.FC<FeatureCardsProps> = ({ variant = 'subtle' }) => {
  return (
    <section aria-labelledby="features-heading" className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 md:gap-6 items-stretch [grid-auto-rows:1fr]">
        {features.map((feature) => {
          const IconComponent = feature.icon;
          const bgClass = variant === 'border' 
            ? 'bg-white dark:bg-slate-900' 
            : 'bg-white/80 dark:bg-slate-900/60';
          const borderClass = variant === 'border' 
            ? `border ${feature.colorTheme.border}` 
            : '';

          return (
            <div
              key={feature.id}
              className={`h-full rounded-2xl ${bgClass} ring-1 ring-black/5 dark:ring-white/10 shadow-sm p-6 md:p-7 flex flex-col ${borderClass} transition-all hover:shadow-lg motion-safe:hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-slate-400 dark:focus-visible:ring-slate-300`}
              aria-label={`${feature.title} features`}
            >
              {/* Icon and title row */}
              <div className="flex items-center gap-3 mb-4 select-none">
                <div className={`size-11 rounded-xl ring-1 ring-inset flex items-center justify-center ${feature.colorTheme.bg} ${feature.colorTheme.ring}`}>
                  <IconComponent className={`w-6 h-6 ${feature.colorTheme.text}`} aria-hidden="true" />
                </div>
                <h3 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-100 text-balance">
                  {feature.title}
                </h3>
              </div>

              {/* Bullets */}
              <ul className="space-y-2 text-slate-600 dark:text-slate-300 leading-relaxed flex-1">
                {feature.bullets.map((bullet, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-slate-400 dark:text-slate-500 mt-1.5 flex-shrink-0">•</span>
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default FeatureCards;
