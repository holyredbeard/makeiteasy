import React, { useState, useEffect } from 'react';
import { Link, Outlet, useNavigate, useLocation } from 'react-router-dom';
import { 
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  BookOpenIcon,
  WrenchScrewdriverIcon,
  XMarkIcon,
  BugAntIcon,
  Cog6ToothIcon,
  CreditCardIcon,
  LifebuoyIcon,
  PlusIcon,
  LinkIcon as LinkOutlineIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';
import { Facebook, Instagram, Youtube, Music } from 'lucide-react';
// Logging UI disabled

const API_BASE = 'http://localhost:8000/api/v1';
const API_ROOT = API_BASE.replace(/\/api\/v1$/, '');

function normalizeBackendUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  return `${API_ROOT}${pathOrUrl.startsWith('/') ? pathOrUrl : '/' + pathOrUrl}`;
}

// Hook to get shopping list badge count
const useShoppingListBadge = () => {
  const [badgeCount, setBadgeCount] = useState(0);

  const updateBadgeCount = () => {
    try {
      const shoppingList = JSON.parse(localStorage.getItem('shoppingList:v1') || '[]');
      const uncheckedCount = shoppingList.filter(item => !item.checked).length;
      setBadgeCount(uncheckedCount);
    } catch (error) {
      setBadgeCount(0);
    }
  };

  useEffect(() => {
    updateBadgeCount();
    
    // Listen for storage changes
    const handleStorageChange = (e) => {
      if (e.key === 'shoppingList:v1') {
        updateBadgeCount();
      }
    };
    
    window.addEventListener('storage', handleStorageChange);
    
    // Also listen for custom events from RecipeView
    const handleShoppingListUpdate = () => {
      updateBadgeCount();
    };
    
    window.addEventListener('shoppingListUpdated', handleShoppingListUpdate);
    
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('shoppingListUpdated', handleShoppingListUpdate);
    };
  }, []);

  return badgeCount;
};

const Header = ({ currentUser, handleLogout, showAuthModal, usageStatus, showTestPdfModal }) => {

  const [openUserMenu, setOpenUserMenu] = useState(false);
  const [openNewMenu, setOpenNewMenu] = useState(false);
  const [scrollY, setScrollY] = useState(0);
  const [logoScale, setLogoScale] = useState(1.0);
  const navigate = useNavigate();
  const location = useLocation();
  const shoppingListBadgeCount = useShoppingListBadge();

  // Check if we're on the landing page (home page)
  const isLandingPage = location.pathname === '/';

  // Scroll animation for logo (only on landing page)
  useEffect(() => {
    if (!isLandingPage) {
      setLogoScale(1.0); // Always small on other pages
      return;
    }

    const handleScroll = () => {
      const s = window.scrollY || 0;
      setScrollY(s);
      // start scale 1.5 -> min 1.0 when scrolled ~400px
      const scale = Math.max(1.0, 1.5 - s / 400);
      setLogoScale(scale);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, [isLandingPage]);


  return (
    <header className="bg-[#659a63] sticky top-0 z-50" style={{fontFamily: 'Poppins, sans-serif'}}>
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex justify-between items-center py-3">
          <div className="flex items-center gap-2">
            <Link to="/">
              <img 
                className="animated-logo"
                style={{ 
                  height: '48px', 
                  transform: `scale(${logoScale})`, 
                  transformOrigin: 'left center',
                  marginTop: isLandingPage && logoScale > 1.0 ? '20px' : '0px'
                }}
                src="/logo.png" 
                alt="Clip2Cook" 
              />
            </Link>
          </div>
          {currentUser ? (
            <div className="flex items-center gap-6 relative w-full">
              <nav className="flex-1 flex justify-center gap-4 md:gap-5 transform translate-x-4 md:translate-x-6">
                <Link
                  to="/explore"
                  className="text-base text-white px-3 py-1 rounded-lg transition-colors hover:text-[#fffae5] hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                  title="Explore"
                  style={{marginRight: '12px'}}
                >
                  <span className="sm:block">Explore</span>
                </Link>
                <Link
                  to="/collections"
                  className="text-base text-white px-3 py-1 rounded-lg transition-colors hover:text-[#fffae5] hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                  title="Collections"
                  style={{marginRight: '12px'}}
                >
                  <span className="sm:block">Collections</span>
                </Link>
                <Link
                  to="/my-recipes"
                  className="text-base text-white px-3 py-1 rounded-lg transition-colors hover:text-[#fffae5] hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70"
                  title="My Recipes"
                  style={{marginRight: '12px'}}
                >
                  <span className="sm:block">My Recipes</span>
                </Link>
                <Link
                  to="/shopping-list"
                  className="text-base text-white px-3 py-1 rounded-lg transition-colors hover:text-[#fffae5] hover:bg-white/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 relative"
                  title="Shop List"
                  style={{marginRight: '12px'}}
                >
                  <span className="flex items-center gap-3">
                    <i className="fa-solid fa-basket-shopping"></i>
                    <span>Shop List{shoppingListBadgeCount > 0 ? ` (${shoppingListBadgeCount})` : ''}</span>
                  </span>
                </Link>
              </nav>
              {currentUser.is_admin && (
                <button 
                  onClick={showTestPdfModal}
                  className="flex items-center gap-2 text-sm text-white/90 hover:text-white transition-colors"
                >
                  <WrenchScrewdriverIcon className="h-5 w-5" />
                  <span className="hidden sm:block">TEST PDF</span>
                </button>
              )}
              <div style={{marginRight: '12px'}}>
                <NewRecipeSplitButton onCreate={() => navigate('/create')} onExtract={() => navigate('/extract')} />
              </div>
              <button onClick={() => setOpenUserMenu(v => !v)} className="flex items-center gap-2 text-sm text-white hover:text-white/90 transition-colors focus:outline-none">
                {currentUser?.avatar_url ? (
                  <img src={normalizeBackendUrl(currentUser.avatar_url)} alt="avatar" className="h-10 w-10 rounded-full object-cover border border-white" />
                ) : (
                  <UserCircleIcon className="h-10 w-10 text-white border border-white rounded-full" />
                )}
              </button>
              {openUserMenu && (
                <div className="absolute right-0 top-full mt-2 z-50">
                  {/* Arrow behind bubble */}
                  <div className="absolute -top-1 right-3 w-3 h-3 bg-white/95 ring-1 ring-black/5 rotate-45 z-0" />
                  {/* Bubble */}
                  <div className="w-64 origin-top-right rounded-xl ring-1 ring-black/5 shadow-lg bg-white/95 backdrop-blur animate-menu-pop relative z-10">
                    <div className="py-1" role="menu" aria-label="User menu">
                    {/* My Profile (public) */}
                    <Link to={`/users/${encodeURIComponent(currentUser?.username || '')}`} title="View your public profile" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50 font-medium" onClick={() => setOpenUserMenu(false)}>
                      <UserCircleIcon className="h-5 w-5 text-gray-500" />
                      <span>My Profile</span>
                    </Link>
                    {/* Edit Profile */}
                    <Link to="/profile" title="Edit your profile" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50" onClick={() => setOpenUserMenu(false)}>
                      <Cog6ToothIcon className="h-5 w-5 text-gray-500" />
                      <span>Edit Profile</span>
                    </Link>
                    <Link to="/settings" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50" title="Settings">
                      <Cog6ToothIcon className="h-5 w-5 text-gray-500" />
                      <span>Settings</span>
                    </Link>
                    <Link to="/billing" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50" title="Subscription / Billing">
                      <CreditCardIcon className="h-5 w-5 text-gray-500" />
                      <span>Subscription / Billing</span>
                    </Link>
                    <Link to="/help" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50" title="Help & Support">
                      <LifebuoyIcon className="h-5 w-5 text-gray-500" />
                      <span>Help & Support</span>
                    </Link>
                    <div className="my-1 border-t border-gray-200" />
                    <button onClick={handleLogout} className="w-full text-left flex items-center gap-3 px-4 py-2 text-sm hover:bg-red-50 text-red-600">
                      <ArrowRightOnRectangleIcon className="h-5 w-5" />
                      <span>Sign Out</span>
                    </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-4">
              {usageStatus && !usageStatus.is_authenticated && (
                <div className="text-sm text-gray-600">
                  <span className="font-medium text-blue-600">{usageStatus.remaining_usage}</span> free PDFs remaining today
                </div>
              )}
              <button 
                onClick={showAuthModal} 
                className="flex items-center justify-center gap-2 py-2 px-4 border border-[#ff931d] rounded-lg shadow-sm hover:shadow-lg bg-[#fff5d9] text-sm font-medium text-[#ff931d] hover:bg-[#ffedb3] hover:border-[#e67e00] hover:scale-105 transition-all duration-200 ease-in-out"
              >
                  Sign In
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

const NewRecipeSplitButton = ({ onCreate, onExtract }) => {
  const [open, setOpen] = useState(false);
  const containerRef = React.useRef(null);
  const buttonRef = React.useRef(null);
  const menuRef = React.useRef(null);
  const item0Ref = React.useRef(null);
  const item1Ref = React.useRef(null);
  const [menuMinWidth, setMenuMinWidth] = useState(0);
  const [focusIndex, setFocusIndex] = useState(0);

  useEffect(() => {
    const onDocClick = (e) => {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target)) setOpen(false);
    };
    const onEsc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, []);

  useEffect(() => {
    try {
      const w = buttonRef.current ? buttonRef.current.offsetWidth : 0;
      setMenuMinWidth(w);
    } catch {}
  }, [open]);

  const openMenu = () => { setOpen(true); setFocusIndex(0); setTimeout(()=> item0Ref.current?.focus(), 0); };
  const toggleMenu = () => { setOpen(v => { const n = !v; if (n) setTimeout(()=> item0Ref.current?.focus(), 0); return n; }); };

  const onKeyDownToggle = (e) => {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') { e.preventDefault(); toggleMenu(); }
    if (e.key === 'ArrowDown') { e.preventDefault(); if (!open) openMenu(); else { setFocusIndex(0); item0Ref.current?.focus(); } }
  };

  const onKeyDownMenu = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); const next = Math.min(1, focusIndex + 1); setFocusIndex(next); (next === 0 ? item0Ref : item1Ref).current?.focus(); }
    if (e.key === 'ArrowUp') { e.preventDefault(); const next = Math.max(0, focusIndex - 1); setFocusIndex(next); (next === 0 ? item0Ref : item1Ref).current?.focus(); }
    if (e.key === 'Escape') { e.preventDefault(); setOpen(false); }
  };

  return (
    <div className="ml-auto mr-2 relative" ref={containerRef}>
      <div ref={buttonRef} className="inline-flex rounded-lg shadow-sm overflow-hidden">
        <button
          onClick={onExtract}
          className="flex items-center gap-2 bg-[#e68a3d] text-white py-2 px-4 hover:bg-[#d1762a] active:brightness-95 transition-colors"
          title="Create Recipe"
        >
          <PlusIcon className="h-4 w-4" strokeWidth={2} />
          <span>Add Recipe</span>
        </button>
        <button
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => toggleMenu()}
          onKeyDown={onKeyDownToggle}
          className="flex items-center justify-center bg-[#e68a3d] text-white px-2 hover:bg-[#d1762a] active:brightness-95 transition-colors"
          title="More options"
        >
          <ChevronDownIcon className="h-5 w-5" />
        </button>
      </div>
      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label="New recipe menu"
          onKeyDown={onKeyDownMenu}
          className="absolute right-0 mt-2 z-50 origin-top-right rounded-xl ring-1 ring-black/5 shadow-lg bg-white/95 backdrop-blur p-2 animate-menu-pop"
          style={{ minWidth: menuMinWidth || undefined }}
        >
          <div className="absolute -top-1 right-6 w-3 h-3 bg-white/95 ring-1 ring-black/5 rotate-45" />
          <button
            ref={item0Ref}
            role="menuitem"
            className="w-full flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg hover:bg-neutral-50 active:bg-neutral-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#e68a3d]"
            onClick={() => { setOpen(false); onExtract?.(); }}
            title="Extract Recipe"
          >
            <LinkOutlineIcon className="h-5 w-5 text-neutral-600" />
            <span>Extract Recipe</span>
          </button>
          <button
            ref={item1Ref}
            role="menuitem"
            className="mt-1 w-full flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg hover:bg-neutral-50 active:bg-neutral-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#e68a3d]"
            onClick={() => { setOpen(false); onCreate?.(); }}
            title="Create Recipe"
          >
            <PlusIcon className="h-5 w-5 text-neutral-600" />
            <span>Create Recipe</span>
          </button>
        </div>
      )}
    </div>
  );
};

const AuthModal = ({ isOpen, onClose, initiateGoogleSignIn, authTab, setAuthTab, onLogin, onRegister }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Welcome to Clip2Cook!</h2>
            <button 
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          
          <div className="flex justify-center gap-2 bg-gray-100 p-1 rounded-xl shadow-inner mb-6">
            <button 
              onClick={() => setAuthTab('login')} 
              className={`flex-1 px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                authTab === 'login' ? 'bg-white text-green-700 shadow-sm' : 'text-gray-500 hover:bg-gray-200'
              }`}
            >
              Login
            </button>
            <button 
              onClick={() => setAuthTab('register')} 
              className={`flex-1 px-4 py-2 text-sm font-semibold rounded-lg transition-colors ${
                authTab === 'register' ? 'bg-white text-green-700 shadow-sm' : 'text-gray-500 hover:bg-gray-200'
              }`}
            >
              Register
            </button>
          </div>

          {authTab === 'login' ? (
            <div className="space-y-6">
              <form className="space-y-4" onSubmit={async (e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                const email = form.get('email');
                const password = form.get('password');
                await onLogin?.({ email, password });
              }}>
                <div>
                  <label htmlFor="login-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input 
                    type="email" 
                    name="email" 
                    id="login-email" 
                    required 
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                </div>
                <div>
                  <label htmlFor="login-password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                  <input 
                    type="password" 
                    name="password" 
                    id="login-password" 
                    required 
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                </div>
                <button 
                  type="submit" 
                  className="w-full bg-[#fff5d9] hover:bg-[#ffedb3] text-[#ff931d] border border-[#ff931d] hover:border-[#e67e00] font-bold py-3 px-4 rounded-xl shadow-md hover:shadow-xl transition-all duration-200 ease-in-out transform hover:scale-[1.02] hover:-translate-y-0.5"
                >
                  Sign In
                </button>
              </form>
              
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white text-gray-500">or</span>
                </div>
              </div>
              
              <button 
                onClick={initiateGoogleSignIn}
                className="w-full flex items-center justify-center gap-3 py-3 px-4 border border-gray-300 rounded-xl shadow-sm hover:shadow-md bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Continue with Google
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              <form className="space-y-4" onSubmit={async (e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                const full_name = form.get('name');
                const username = form.get('username');
                const email = form.get('email');
                const password = form.get('password');
                await onRegister?.({ full_name, username, email, password });
              }}>
                <div>
                  <label htmlFor="register-name" className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                  <input 
                    type="text" 
                    name="name" 
                    id="register-name" 
                    required 
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                </div>
                <div>
                  <label htmlFor="register-username" className="block text-sm font-medium text-gray-700 mb-1">Username</label>
                  <input 
                    type="text" 
                    name="username" 
                    id="register-username" 
                    required 
                    pattern="^[a-z0-9_]{3,20}$"
                    title="3-20 chars; lowercase letters, numbers and underscore only"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                  <p className="text-xs text-gray-500 mt-1">3-20 characters, lowercase letters, numbers and underscore.</p>
                </div>
                <div>
                  <label htmlFor="register-email" className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                  <input 
                    type="email" 
                    name="email" 
                    id="register-email" 
                    required 
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                </div>
                <div>
                  <label htmlFor="register-password" className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                  <input 
                    type="password" 
                    name="password" 
                    id="register-password" 
                    required 
                    minLength="6"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500" 
                  />
                </div>
                <button 
                  type="submit" 
                  className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-xl shadow-md hover:shadow-lg transition-transform transform hover:scale-[1.02]"
                >
                  Create Account
                </button>
              </form>
              
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-white text-gray-500">or</span>
                </div>
              </div>
              
              <button 
                onClick={initiateGoogleSignIn}
                className="w-full flex items-center justify-center gap-3 py-3 px-4 border border-gray-300 rounded-xl shadow-sm hover:shadow-md bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Sign up with Google
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default function Layout() {
  const [currentUser, setCurrentUser] = useState(null);
  const [authTab, setAuthTab] = useState('login');
  const [usageStatus, setUsageStatus] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [showWelcome, setShowWelcome] = useState(false);
  const [openNewMenu, setOpenNewMenu] = useState(false);
  // const [showLogPanel, setShowLogPanel] = useState(true); // disabled
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === '/';

  const refreshCurrentUser = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
      if (response.ok) {
        const user = await response.json();
        setCurrentUser(user);
      }
    } catch (error) {
      console.error('Failed to fetch user', error);
    }
  };

  useEffect(() => {
    refreshCurrentUser();
    
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
      handleGoogleOAuthCallback(code);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else {
      checkUsageStatus();
    }
  }, []);

  // Global deep-link handler: open variant modal from any route
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const variantId = params.get('variant');
    if (!variantId) return;
    const isDesktop = window.innerWidth >= 768;
    // If already on target route, no redirect
    if (isDesktop) {
      if (location.pathname !== '/my-recipes') {
        navigate(`/my-recipes?variant=${variantId}`, { replace: true });
      }
    } else {
      if (!location.pathname.startsWith(`/recipes/${variantId}`)) {
        navigate(`/recipes/${variantId}`, { replace: true });
      }
    }
  }, [location.pathname, location.search, navigate]);

  const checkUsageStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/usage-status`, { credentials: 'include' });
      if (response.ok) {
        const status = await response.json();
        setUsageStatus(status);
      }
    } catch (error) {
      console.error('Failed to check usage status', error);
    }
  };

  const handleGoogleOAuthCallback = async (code) => {
    try {
      const authResponse = await fetch(`${API_BASE}/auth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
        credentials: 'include'
      });

      if (authResponse.ok) {
        const data = await authResponse.json();
        if (data.user) {
          setCurrentUser(data.user);
          setIsAuthModalOpen(false);
          setShowWelcome(true);
          setTimeout(() => setShowWelcome(false), 4000);
        }
      } else {
        const error = await authResponse.json();
        alert(error.detail || 'Google Sign-In failed');
      }
    } catch (error) {
      console.error('Google OAuth callback error:', error);
      alert('Google Sign-In failed.');
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (error) {
      console.error("Logout failed", error);
    } finally {
      setCurrentUser(null);
      setIsAuthModalOpen(false);
      setAuthTab('login');
      // ensure we show logged-out landing
      navigate('/', { replace: true });
      // refresh usage status (will show unauthenticated quotas)
      checkUsageStatus();
    }
  };

  const doLogin = async ({ email, password }) => {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ email, password }) });
      if (!res.ok) throw new Error('Login failed');
      const data = await res.json();
      setCurrentUser(data.user);
      setIsAuthModalOpen(false);
    } catch (e) {
      alert('Login failed');
    }
  };

  const doRegister = async ({ full_name, username, email, password }) => {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({ full_name, username, email, password }) });
      if (!res.ok) throw new Error('Registration failed');
      const data = await res.json();
      // After registration, user is logged in via cookie in backend
      setCurrentUser(data.user);
      setIsAuthModalOpen(false);
    } catch (e) {
      alert('Registration failed');
    }
  };

  const initiateGoogleSignIn = async () => {
    try {
      const urlResponse = await fetch(`${API_BASE}/auth/google/url`, { credentials: 'include' });
      if (!urlResponse.ok) throw new Error('Failed to get Google OAuth URL');
      const urlData = await urlResponse.json();
      if (!urlData.auth_url) {
          alert('Google Sign-In is not available.');
        return;
      }
      setIsAuthModalOpen(false);
      window.location.href = urlData.auth_url;
    } catch (error) {
      console.error('Google Sign-In error:', error);
      alert('Could not initiate Google Sign-In.');
    }
  };

  return (
    <div className={`font-poppins min-h-screen`}>
      <Header 
        currentUser={currentUser} 
        handleLogout={handleLogout} 
        showAuthModal={() => setIsAuthModalOpen(true)} 
        usageStatus={usageStatus} 
      />
      
      {/* LogPanel disabled */}

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initiateGoogleSignIn={initiateGoogleSignIn}
        authTab={authTab}
        setAuthTab={setAuthTab}
        onLogin={doLogin}
        onRegister={doRegister}
      />

      {showWelcome && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-green-600 text-white px-6 py-3 rounded-xl shadow-lg text-lg font-semibold animate-fade-in-out">
          Welcome, {currentUser?.full_name || currentUser?.email}!
        </div>
      )}

      <main className={`max-w-[1080px] mx-auto ${isHome ? 'py-0 px-0' : 'py-10 px-8'}`}>
        <Outlet context={{ currentUser, refreshCurrentUser, setCurrentUser }} />
      </main>

      {/* Footer */}
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
    </div>
  );
}