import React, { useState, useEffect } from 'react';
import { Link, Outlet, useNavigate } from 'react-router-dom';
import { 
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  BookOpenIcon,
  WrenchScrewdriverIcon,
  XMarkIcon,
  BugAntIcon,
  Cog6ToothIcon,
  CreditCardIcon,
  LifebuoyIcon
} from '@heroicons/react/24/outline';
// Logging UI disabled

const API_BASE = 'http://localhost:8001/api/v1';
const API_ROOT = API_BASE.replace(/\/api\/v1$/, '');

function normalizeBackendUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  return `${API_ROOT}${pathOrUrl.startsWith('/') ? pathOrUrl : '/' + pathOrUrl}`;
}

const Header = ({ currentUser, handleLogout, showAuthModal, usageStatus, showTestPdfModal }) => {
  const [openUserMenu, setOpenUserMenu] = useState(false);
  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200/80 shadow-sm sticky top-0 z-50 font-poppins">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex justify-between items-center py-3">
          <div className="flex items-center gap-2">
            <Link to="/">
              <img className="h-10 w-auto" src="/logo.png" alt="Clip2Cook" />
            </Link>
          </div>
          {currentUser ? (
            <div className="flex items-center gap-6 relative">
              <Link to="/my-recipes" className="flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 transition-colors">
                <BookOpenIcon className="h-5 w-5" />
                <span className="hidden sm:block">My Recipes</span>
              </Link>
              {currentUser.is_admin && (
                <button 
                  onClick={showTestPdfModal}
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
                >
                  <WrenchScrewdriverIcon className="h-5 w-5" />
                  <span className="hidden sm:block">TEST PDF</span>
                </button>
              )}
              <button onClick={() => setOpenUserMenu(v => !v)} className="flex items-center gap-2 text-sm text-gray-700 hover:text-gray-900 transition-colors focus:outline-none">
                {currentUser?.avatar_url ? (
                  <img src={normalizeBackendUrl(currentUser.avatar_url)} alt="avatar" className="h-8 w-8 rounded-full object-cover" />
                ) : (
                  <UserCircleIcon className="h-8 w-8 text-gray-500" />
                )}
              </button>
              {openUserMenu && (
                <div className="absolute right-0 top-full mt-2 w-64 bg-white border border-gray-200 rounded-xl shadow-lg z-50">
                  <div className="py-1">
                    <Link to="/profile" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50" onClick={() => setOpenUserMenu(false)}>
                      <UserCircleIcon className="h-5 w-5 text-gray-500" />
                      <span>Profile</span>
                    </Link>
                    <Link to="#" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50">
                      <Cog6ToothIcon className="h-5 w-5 text-gray-500" />
                      <span>Settings</span>
                    </Link>
                    <Link to="#" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50">
                      <CreditCardIcon className="h-5 w-5 text-gray-500" />
                      <span>Subscription / Billing</span>
                    </Link>
                    <Link to="#" className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50">
                      <LifebuoyIcon className="h-5 w-5 text-gray-500" />
                      <span>Help & Support</span>
                    </Link>
                    <div className="my-1 border-t border-gray-200" />
                    <button onClick={handleLogout} className="w-full text-left flex items-center gap-3 px-4 py-2 text-sm hover:bg-gray-50 text-red-600">
                      <ArrowRightOnRectangleIcon className="h-5 w-5" />
                      <span>Sign Out</span>
                    </button>
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
                className="flex items-center justify-center gap-2 py-2 px-4 border border-gray-300 rounded-lg shadow-sm hover:shadow-md bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition-all"
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
                  className="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-3 px-4 rounded-xl shadow-md hover:shadow-lg transition-transform transform hover:scale-[1.02]"
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
  // const [showLogPanel, setShowLogPanel] = useState(true); // disabled
  const navigate = useNavigate();

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
    <div className="font-poppins bg-[#f9fafb] min-h-screen">
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

      <main className="max-w-[1080px] mx-auto py-10 px-8">
        <Outlet context={{ currentUser, refreshCurrentUser, setCurrentUser }} />
      </main>
    </div>
  );
}