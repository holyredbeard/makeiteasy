import React from 'react';

interface FeatureCard {
  id: string;
  title: string;
  icon: string;
  iconColor: string;
  bullets: string[];
}

interface FeatureCardsProps {
  variant?: 'subtle' | 'border';
}

const features: FeatureCard[] = [
  {
    id: 'video-to-recipe',
    title: 'Video to Recipe',
    icon: 'fas fa-clapperboard',
    iconColor: '#3B82F6',
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
    icon: 'fas fa-exchange-alt',
    iconColor: '#F59E0B',
    bullets: [
      'Scale servings and swap ingredients',
      'One-click presets (Vegan, Gluten-free, etc.)',
      'Highlights what changed and keeps instructions consistent'
    ]
  },
  {
    id: 'nutrition-analysis',
    title: 'Nutrition Analysis',
    icon: 'fas fa-seedling',
    iconColor: '#10B981',
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch [grid-auto-rows:1fr]">
        {features.map((feature) => {
          return (
            <div
              key={feature.id}
              className="h-full rounded-2xl bg-white shadow-md hover:shadow-lg transition-all duration-200 p-6 flex flex-col"
              aria-label={`${feature.title} features`}
            >
              {/* Icon and title row */}
              <div className="flex items-center gap-3 mb-4 select-none">
                <div 
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{ backgroundColor: feature.iconColor }}
                >
                  <i className={`${feature.icon} text-white`} aria-hidden="true"></i>
                </div>
                <h3 className="text-xl font-bold tracking-tight text-slate-900 text-balance">
                  {feature.title}
                </h3>
              </div>

              {/* Bullets */}
              <ul className="space-y-2 text-slate-600 leading-relaxed flex-1 text-sm">
                {feature.bullets.map((bullet, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="text-slate-400 mt-1.5 flex-shrink-0">•</span>
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
