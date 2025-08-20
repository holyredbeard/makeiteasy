import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, RefreshCcw, Apple, ArrowRight } from 'lucide-react';
import FeatureCards from '../components/FeatureCards';
import PageContainer from '../components/PageContainer';
import CollectionCard from '../components/CollectionCard';

const colors = {
  bg: '#FAF9F7',
  ink: '#101828',
  muted: '#667085',
  accent: '#0EA5E9',
  accent2: '#F97316',
};

const API_BASE = 'http://localhost:8000/api/v1';
const STATIC_BASE = 'http://localhost:8000';

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
            className="w-full max-w-md lg:max-w-lg rounded-[2rem] object-cover shadow-lg aspect-[4/3]"
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
    <section className="relative w-screen left-1/2 right-1/2 -ml-[50vw] -mr-[50vw] py-14" style={{ backgroundColor: 'rgb(241, 230, 214)' }}>
      <PageContainer>
        <h2 className="text-3xl font-bold text-[rgb(236,141,34)] text-center mb-2">Popular Collections</h2>
        <p className="text-center text-gray-600 mb-8">Discover amazing recipe collections from our community</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-6">
          {collectionsData.slice(0,4).map((c, i)=> (
            <CollectionCard
              key={c.id || i}
              id={c.id || i.toString()}
              title={c.title}
              image_url={normalizeUrl(c.image_url)}
              recipes_count={c.recipes_count}
              followers_count={c.followers_count}
              creator_name={c.owner_name}
              creator_username={c.owner_username}
              creator_avatar={normalizeUrl(c.owner_avatar)}
              likes_count={c.likes_count || 0}
              onClick={() => window.location.href = `/collections/${c.id || i}`}
            />
          ))}
        </div>
        <div className="text-center mt-8">
          <a href="/collections" className="inline-flex items-center gap-2 text-[#e68a3d] hover:underline">View All Collections <ArrowRight className="w-4 h-4"/></a>
        </div>
      </PageContainer>
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
            <img src="/static/test_images/test_portrait_cropped.jpg" alt="recipe" className="w-16 h-12 rounded object-cover aspect-square" />
          </div>
        </Card>
        <Card className="p-4 hover:-translate-y-0.5">
          <div className="flex items-center gap-3">
            <img src="/static/test_images/test_portrait.jpg" alt="profile" className="w-10 h-10 rounded-full object-cover" />
            <div className="flex-1">
              <p className="font-medium">Kai</p>
              <p className="text-sm text-gray-600">Liked</p>
            </div>
            <img src="/static/test_images/test_landscape.jpg" alt="recipe" className="w-16 h-12 rounded object-cover aspect-square" />
          </div>
        </Card>
      </div>
      <div className="mt-6">
        <button className="px-5 py-3 rounded-lg bg-[#cc7c2e] text-white hover:brightness-110">Join the Community</button>
      </div>
      </div>
    </section>
  );



  

  return (
    <div style={{ background: colors.bg, color: colors.ink }}>
      {hero}
      {features}
      {collections}
      {social}
    </div>
  );
}


