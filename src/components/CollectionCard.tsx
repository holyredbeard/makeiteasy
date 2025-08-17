import React from 'react';

interface CollectionCardProps {
  id: string;
  title: string;
  image_url: string;
  recipes_count: number;
  followers_count: number;
  creator_name?: string;
  creator_username?: string;
  creator_avatar?: string;
  likes_count?: number;
  onClick?: () => void;
  className?: string;
}

const CollectionCard: React.FC<CollectionCardProps> = ({
  id,
  title,
  image_url,
  recipes_count,
  followers_count,
  creator_name,
  creator_username,
  creator_avatar,
  likes_count = 0,
  onClick,
  className = ''
}) => {
  const handleClick = () => {
    if (onClick) onClick();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <div
      className={`relative aspect-square rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 hover:scale-[1.02] hover:shadow-lg group ${className}`}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`Öppna collection: ${title}`}
    >
      {/* Bild med lazy loading */}
      <img
        src={image_url || 'https://placehold.co/800x800?text=Collection'}
        alt={title}
        className="w-full h-full object-cover aspect-square"
        loading="lazy"
        onError={(e) => {
          e.currentTarget.src = 'https://placehold.co/800x800?text=Collection';
        }}
      />

      {/* Overlay gradient för läsbar text */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />

      {/* Likes badge uppe till höger */}
      {likes_count > 0 && (
        <div className="absolute top-3 right-3 bg-white/90 backdrop-blur-sm rounded-full px-2 py-1 flex items-center gap-1 text-sm font-medium text-gray-700">
          <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
          </svg>
          <span>{likes_count}</span>
        </div>
      )}

      {/* Innehåll nertill */}
      <div className="absolute bottom-0 left-0 right-0 p-4 text-white">
        {/* Titel med truncation */}
        <h3 className="text-lg font-bold mb-2 truncate" title={title}>
          {title}
        </h3>

        {/* Meta-information */}
        <div className="text-sm opacity-90 mb-3">
          {recipes_count} recept • {followers_count} följare
        </div>

        {/* Creator info */}
        {(creator_username || creator_name) && (
          <div className="flex items-center gap-2">
            <img
              src={creator_avatar || 'https://placehold.co/32x32?text=U'}
              alt={`${creator_username || creator_name} avatar`}
              className="w-6 h-6 rounded-full object-cover border border-white"
              onError={(e) => {
                e.currentTarget.src = 'https://placehold.co/32x32?text=U';
              }}
            />
            <a 
              href={`/users/${encodeURIComponent(creator_username || creator_name)}`}
              className="text-sm opacity-90 truncate hover:underline hover:opacity-100 transition-opacity"
              onClick={(e) => e.stopPropagation()}
            >
              {creator_username || creator_name}
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default CollectionCard;
