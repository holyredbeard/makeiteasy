import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, RefreshCcw, Apple, Facebook, Instagram, Youtube, Music, ArrowRight } from 'lucide-react';
import FeatureCards from '../components/FeatureCards';

const colors = {
  bg: '#FAF9F7',
  ink: '#101828',
  muted: '#667085',
  accent: '#0EA5E9',
  accent2: '#F97316',
};

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

const Chip = ({ children }: { children: React.ReactNode }) => (
  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-sm bg-sky-50 text-sky-700 border border-sky-200">
    {children}
  </span>
);

const Card: React.FC<React.PropsWithChildren<{ className?: string }>> = ({ className = '', children }) => (
  <div className={`rounded-2xl bg-white shadow-md hover:shadow-lg hover:-translate-y-0.5 transition transform ${className}`}>{children}</div>
);

export default function Home() {
  // Local helpers (no global state needed)

  // Header hanteras av befintliga Layout.jsx – ingen dubblering här

  const hero = (
    <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] bg-[#659a63]">
      <div className="mx-auto max-w-7xl px-0">
      <div className="overflow-hidden grid grid-cols-1 lg:grid-cols-2 min-h-[520px]">
        {/* Left */}
        <div className="bg-[#659a63] p-8 lg:p-14 flex flex-col justify-center">
          <h1 className="text-white text-4xl lg:text-6xl font-extrabold tracking-tight">Find, Convert & Save Recipes in Seconds</h1>
          <p className="mt-4 text-gray-100/80 text-lg">Turn videos, blogs, and recipe pages into clean, organized recipes instantly.</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href="/extract" className="px-5 py-3 rounded-lg bg-[#cc7c2e] text-white hover:brightness-110">Extract Recipe</a>
            <a href="/collections" className="px-5 py-3 rounded-lg bg-white text-gray-900 hover:bg-gray-50">Explore Recipes</a>
          </div>
        </div>
        {/* Right */}
        <div className="relative flex items-center justify-center p-8 lg:p-14">
          <img
            src={`${STATIC_BASE}/static/images/hero.png`}
            alt="Pasta"
            className="w-full max-w-md lg:max-w-lg rounded-[2rem] object-cover shadow-lg"
            onError={(e)=>{ e.currentTarget.src = `${STATIC_BASE}/static/test_images/test_landscape.jpg`; }}
          />
        </div>
      </div>
      </div>
    </section>
  );

  const features = (
    <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] bg-[#f6f1e9] py-16">
      <div className="max-w-7xl mx-auto px-4 lg:px-6">
        <h2 id="features-heading" className="text-3xl font-bold text-gray-900 text-center">Unique Features</h2>
        <p className="mt-2 text-center text-gray-600">Everything you need for effortless cooking</p>
        <div className="mt-10">
          <FeatureCards />
        </div>
      </div>
    </section>
  );

  const [collectionsData, setCollectionsData] = useState<any[]>([]);
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/collections`, { credentials: 'include' });
        const j = await r.json();
        if (Array.isArray(j)) setCollectionsData(j);
      } catch {}
    })();
  }, []);

  const normalizeUrl = (u) => {
    if (!u) return null; let x = String(u);
    if (x.startsWith('http://127.0.0.1:8000')) x = x.replace('http://127.0.0.1:8000', STATIC_BASE);
    if (x.startsWith('http://localhost:8000')) x = x.replace('http://localhost:8000', STATIC_BASE);
    if (x.startsWith('/')) x = STATIC_BASE + x; return x;
  };

  const collections = (
    <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] py-14" style={{ backgroundColor: '#e2dace' }}>
      <div className="max-w-7xl mx-auto px-4 lg:px-6">
      <h2 className="text-3xl font-bold text-white mb-8">Popular Collections</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
        {collectionsData.slice(0,4).map((c, i)=> (
          <a
            key={c.id || i}
            href={`/collections?open=${c.id || i}`}
            className="relative block rounded-2xl overflow-hidden shadow-md hover:shadow-xl transition"
          >
            <img
              src={normalizeUrl(c.image_url) || 'https://placehold.co/800x600?text=Collection'}
              alt={c.title}
              className="w-full h-56 object-cover"
              onError={(e)=>{ e.currentTarget.src='https://placehold.co/800x600?text=Collection'; }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
            <div className="absolute top-4 right-4 rounded-full px-3 py-1 text-sm font-semibold bg-white/90 text-gray-800 flex items-center gap-1">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="#ef4444" aria-hidden="true"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41 0.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
              <span>{c.likes_count || 0}</span>
            </div>
            <div className="absolute left-4 right-4 bottom-4 text-white">
              <h2 className="text-lg font-bold drop-shadow mb-1 line-clamp-2" title={c.title}>{c.title}</h2>
              <div className="text-sm opacity-95 mb-3">{c.recipes_count} recept • {c.followers_count} följare</div>
              <div className="flex items-center gap-3">
                <img
                  src={normalizeUrl(c.owner_avatar) || 'https://placehold.co/64x64?text=%F0%9F%91%A4'}
                  alt={c.owner_name || 'Owner'}
                  className="h-9 w-9 rounded-full object-cover border-2 border-white/80 shadow-sm"
                  onError={(e)=>{ e.currentTarget.src='https://placehold.co/64x64?text=%F0%9F%91%A4'; }}
                />
                <div className="font-semibold drop-shadow">{c.owner_name || 'Unknown'}</div>
              </div>
            </div>
          </a>
        ))}
      </div>
      <div className="mt-6">
        <a href="/collections" className="inline-flex items-center gap-2 text-[#e68a3d] hover:underline">View All Collections <ArrowRight className="w-4 h-4"/></a>
      </div>
      </div>
    </section>
  );

  const social = (
    <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] bg-[#FAF9F7] py-14">
      <div className="max-w-7xl mx-auto px-4 lg:px-6">
      <h2 className="text-3xl font-bold text-gray-900 mb-3">Connect With Other Cooks</h2>
      <p className="text-gray-600 mb-8">Follow, comment, and share recipes with a growing community of food lovers.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-4 hover:-translate-y-0.5">
          <div className="flex items-center gap-3">
            <img src="/static/test_images/test_portrait.jpg" alt="profile" className="w-10 h-10 rounded-full object-cover" />
            <div>
              <p className="font-medium">Maya</p>
              <p className="text-sm text-gray-600">Shared a recipe · <a className="underline" href="#">Lemon Pasta</a></p>
            </div>
          </div>
        </Card>
        <Card className="p-4 hover:-translate-y-0.5">
          <div className="flex items-center gap-3">
            <img src="/static/test_images/test_landscape.jpg" alt="profile" className="w-10 h-10 rounded-full object-cover" />
            <div className="flex-1">
              <p className="font-medium">Noah</p>
              <p className="text-sm text-gray-600">Commented on</p>
            </div>
            <img src="/static/test_images/test_portrait_cropped.jpg" alt="recipe" className="w-16 h-12 rounded object-cover" />
          </div>
        </Card>
        <Card className="p-4 hover:-translate-y-0.5">
          <div className="flex items-center gap-3">
            <img src="/static/test_images/test_portrait.jpg" alt="profile" className="w-10 h-10 rounded-full object-cover" />
            <div className="flex-1">
              <p className="font-medium">Kai</p>
              <p className="text-sm text-gray-600">Liked</p>
            </div>
            <img src="/static/test_images/test_landscape.jpg" alt="recipe" className="w-16 h-12 rounded object-cover" />
          </div>
        </Card>
      </div>
      <div className="mt-6">
        <button className="px-5 py-3 rounded-lg bg-[#cc7c2e] text-white hover:brightness-110">Join the Community</button>
      </div>
      </div>
    </section>
  );

  // Footer
  const siteFooter = (
    <footer className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] mt-10 bg-[#0f3b2d] text-gray-200">
      <div className="max-w-7xl mx-auto px-4 lg:px-6 py-12 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
        <div>
          <h3 className="text-white font-bold text-xl">Food2Guide</h3>
          <p className="mt-3 text-gray-300">Your all-in-one platform to extract, organize, and enjoy recipes from anywhere.</p>
          <div className="mt-4 flex items-center gap-3">
            <a href="#" aria-label="Facebook" className="p-2 rounded bg-white/10 hover:bg-white/20"><Facebook className="w-5 h-5"/></a>
            <a href="#" aria-label="Instagram" className="p-2 rounded bg-white/10 hover:bg-white/20"><Instagram className="w-5 h-5"/></a>
            <a href="#" aria-label="YouTube" className="p-2 rounded bg-white/10 hover:bg-white/20"><Youtube className="w-5 h-5"/></a>
            <a href="#" aria-label="TikTok" className="p-2 rounded bg-white/10 hover:bg-white/20"><Music className="w-5 h-5"/></a>
          </div>
        </div>
        <div>
          <h4 className="text-white font-semibold mb-3">Features</h4>
          <ul className="space-y-2 text-gray-300">
            <li>Extract Recipes</li>
            <li>Smart Conversions</li>
            <li>Nutrition Analysis</li>
            <li>Save & Organize</li>
            <li>Social Features</li>
          </ul>
        </div>
        <div>
          <h4 className="text-white font-semibold mb-3">Explore</h4>
          <ul className="space-y-2 text-gray-300">
            <li>Popular Collections</li>
            <li>Latest Recipes</li>
            <li>Trending Now</li>
            <li>Dietary Picks (Vegan, Keto, Gluten-Free)</li>
          </ul>
        </div>
        <div>
          <h4 className="text-white font-semibold mb-3">Stay Updated</h4>
          <p className="text-gray-300">Subscribe for new features, tips, and recipe inspiration.</p>
          <div className="mt-3 flex items-center gap-2">
            <input className="flex-1 rounded-lg px-3 py-2 text-gray-900" placeholder="Email address" />
            <button className="px-4 py-2 rounded-lg bg-[#cc7c2e] text-white hover:brightness-110">Subscribe</button>
          </div>
        </div>
      </div>
    </footer>
  );

  

  return (
    <div style={{ background: colors.bg, color: colors.ink }}>
      {hero}
      {features}
      {collections}
      {social}
      {siteFooter}
    </div>
  );
}


