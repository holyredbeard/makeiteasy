import React, { useState, useEffect, useRef } from 'react';
import { 
  LinkIcon, 
  MagnifyingGlassIcon, 
  CheckCircleIcon,
  ArrowDownTrayIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
  SparklesIcon,
  FireIcon,
  XMarkIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8000';

const Spinner = ({ size = 'h-5 w-5', color = 'text-white' }) => (
  <svg className={`animate-spin ${size} ${color}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

const Header = ({ currentUser, handleLogout, showAuthModal, usageStatus, showTestPdfModal }) => (
  <header className="bg-white/80 backdrop-blur-sm border-b border-gray-200/80 shadow-sm sticky top-0 z-50 font-poppins">
    <div className="max-w-7xl mx-auto px-6">
      <div className="flex justify-between items-center py-3">
        <div className="flex items-center gap-2">
          <a href="/">
            <img className="h-10 w-auto" src="/logo.png" alt="Food2Guide" />
          </a>
        </div>
        {currentUser ? (
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
                <UserCircleIcon className="h-6 w-6 text-gray-500" />
                <span className="text-sm text-gray-700 font-medium hidden sm:block">{currentUser.full_name || currentUser.email}</span>
            </div>
            {currentUser.is_admin && (
              <button 
                onClick={showTestPdfModal}
                className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
              >
                <WrenchScrewdriverIcon className="h-5 w-5" />
                <span className="hidden sm:block">TEST PDF</span>
              </button>
            )}
            <button onClick={handleLogout} className="flex items-center gap-2 text-sm text-gray-600 hover:text-red-600 transition-colors">
              <ArrowRightOnRectangleIcon className="h-5 w-5" />
              <span className="hidden sm:block">Sign Out</span>
            </button>
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

const AuthModal = ({ isOpen, onClose, handleLogin, handleRegister, initiateGoogleSignIn, authTab, setAuthTab }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Welcome to Food2Guide!</h2>
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
              <form onSubmit={handleLogin} className="space-y-4">
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
              <form onSubmit={handleRegister} className="space-y-4">
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

const TestPdfModal = ({ isOpen, onClose, currentUser }) => {
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('professional');
  const [selectedOrientation, setSelectedOrientation] = useState('landscape');
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Fetch available templates when modal opens
  useEffect(() => {
    if (isOpen && currentUser?.is_admin) {
      fetchTemplates();
    }
  }, [isOpen, currentUser]);

  const fetchTemplates = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/templates`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || []);
      }
    } catch (error) {
      console.error('Error fetching templates:', error);
    }
  };

  const generateTestPdf = async () => {
    setIsGenerating(true);
    try {
      const formData = new FormData();
      formData.append('template_name', selectedTemplate);
      formData.append('image_orientation', selectedOrientation);
      
      const response = await fetch(`${API_BASE}/api/v1/test-pdf`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: formData
      });
      
      if (response.ok) {
        // Download the PDF
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `test-${selectedTemplate}-${selectedOrientation}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        // Close modal
        onClose();
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail || 'Failed to generate test PDF'}`);
      }
    } catch (error) {
      console.error('Error generating test PDF:', error);
      alert('Error generating test PDF. Please try again.');
    } finally {
      setIsGenerating(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">Test PDF Generation</h2>
            <button 
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                CSS Template
              </label>
              <select 
                value={selectedTemplate}
                onChange={(e) => setSelectedTemplate(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {templates.map(template => (
                  <option key={template} value={template}>
                    {template.charAt(0).toUpperCase() + template.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Image Orientation
              </label>
              <select 
                value={selectedOrientation}
                onChange={(e) => setSelectedOrientation(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="landscape">Landscape (YouTube)</option>
                <option value="portrait">Portrait (TikTok/Shorts)</option>
              </select>
            </div>
            
            <div className="pt-4">
              <button
                onClick={generateTestPdf}
                disabled={isGenerating}
                className={`w-full font-bold py-3 px-4 rounded-xl shadow-md hover:shadow-lg transition-transform transform hover:scale-[1.02] ${
                  isGenerating 
                    ? 'bg-gray-400 cursor-not-allowed' 
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                {isGenerating ? 'Generating...' : 'CREATE'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const JobStatus = ({ job, onReset }) => {
  const [status, setStatus] = useState(job.status);
  const [details, setDetails] = useState(job.details);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [error, setError] = useState(null);

  const statusStates = [
    { key: 'downloading', text: 'Downloading' },
    { key: 'transcribing', text: 'Transcribing' },
    { key: 'analyzing', text: 'Analyzing' },
    { key: 'extracting_frames', text: 'Extracting Frames' },
    { key: 'generating_pdf', text: 'Generating PDF' },
  ];
  const currentStatusIndex = statusStates.findIndex(s => status.toLowerCase().includes(s.key));
  
  useEffect(() => {
    if (status === 'completed' || status === 'failed') {
      if (job.pdf_url) setPdfUrl(job.pdf_url);
      return;
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/v1/status/${job.job_id}`);
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        setStatus(data.status);
        setDetails(data.details);

        if (data.status === 'completed') {
          setPdfUrl(data.pdf_url);
          clearInterval(interval);
        } else if (data.status === 'failed') {
          setError(data.details);
          clearInterval(interval);
        }
      } catch (err) {
        setError('Failed to fetch status.');
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [job.job_id, status, job.pdf_url]);

  if (status === 'failed') {
    return (
      <div className="text-center">
        <h3 className="text-xl font-semibold text-red-600">Generation Failed</h3>
        <p className="text-gray-600 my-4">{error || details}</p>
        <button onClick={onReset} className="bg-gray-700 text-white font-bold py-2 px-4 rounded-lg hover:bg-gray-800 transition-colors">Start Over</button>
      </div>
    );
  }

  if (status === 'completed' && pdfUrl) {
    return (
      <div className="text-center">
        <h3 className="text-xl font-semibold text-green-600">Recipe Ready!</h3>
        <p className="text-gray-600 my-4">Your recipe has been generated successfully.</p>
        <div className="flex gap-4 justify-center">
          <a href={`${API_BASE}${pdfUrl}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 bg-green-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-green-700 transition-colors">
            <ArrowDownTrayIcon className="h-5 w-5" /> Download PDF
          </a>
          <button onClick={onReset} className="bg-gray-200 text-gray-800 font-bold py-3 px-6 rounded-lg hover:bg-gray-300 transition-colors">Create Another</button>
        </div>
      </div>
    );
  }

  // Determine current step based on status
  const getCurrentStep = () => {
    if (status.toLowerCase().includes('downloading') || status.toLowerCase().includes('processing')) return 1;
    if (status.toLowerCase().includes('transcribing')) return 2;
    if (status.toLowerCase().includes('analyzing')) return 3;
    if (status.toLowerCase().includes('frames') || status.toLowerCase().includes('extracting') || status.toLowerCase().includes('generating') || status.toLowerCase().includes('pdf')) return 4;
    return 1; // Default to step 1
  };

  const currentStep = getCurrentStep();
  const totalSteps = 4;

  return (
    <div className="text-center">
      <div className="mb-4">
        <span className="inline-block bg-blue-100 text-blue-800 text-sm font-medium px-3 py-1 rounded-full">
          Step {currentStep}/{totalSteps}
        </span>
      </div>
      <h3 className="text-xl font-semibold text-blue-600">Processing Video</h3>
      <p className="text-gray-600 my-4">{details}</p>
      <div className="flex justify-center my-6">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
      <button onClick={onReset} className="bg-gray-200 text-gray-700 font-semibold py-2 px-4 rounded-lg hover:bg-gray-300">Start Over</button>
    </div>
  );
};


export default function Food2Guide() {
  const [activeTab, setActiveTab] = useState('paste');
  const [videoUrl, setVideoUrl] = useState('');
  const [searchQuery, setSearchQuery] = useState("");
  const [language, setLanguage] = useState('en');
  const [searchResults, setSearchResults] = useState([]); // Initialize as empty array
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [job, setJob] = useState(null);
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken'));
  const [currentUser, setCurrentUser] = useState(null);
  const [authTab, setAuthTab] = useState('login');
  const [isSearching, setIsSearching] = useState(false);
  const [searchPage, setSearchPage] = useState(1);
  const [hasMoreResults, setHasMoreResults] = useState(true);
  const [usageStatus, setUsageStatus] = useState(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isTestPdfModalOpen, setIsTestPdfModalOpen] = useState(false);
  const scrollContainerRef = useRef(null);
  // 1. Add state for welcome snackbar
  const [showWelcome, setShowWelcome] = useState(false);
  
  // Advanced Settings state
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [showImages, setShowImages] = useState(true); // Yes (default)
  const [dietPreference, setDietPreference] = useState('regular'); // regular, vegetarian, vegan
  const [allergies, setAllergies] = useState({ gluten: false, nuts: false, eggs: false, dairy: false, shellfish: false });
  const [instructionLevel, setInstructionLevel] = useState('intermediate'); // beginner, intermediate (default), expert
  const [showCalories, setShowCalories] = useState(false); // No (default)
  const [pdfStyle, setPdfStyle] = useState('modern');
  const [includeNutrition, setIncludeNutrition] = useState(true);
  const [includeTips, setIncludeTips] = useState(true);
  const [maxSteps, setMaxSteps] = useState(10);
  const [imageQuality, setImageQuality] = useState('high');
  const [videoSource, setVideoSource] = useState('youtube'); // youtube eller tiktok
  const [searchAttempted, setSearchAttempted] = useState(false); // New state to track if a search has been made
  const [isProcessing, setIsProcessing] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const languages = [
    { code: 'en', name: 'English' },
    { code: 'sv', name: 'Svenska' },
    { code: 'no', name: 'Norsk' },
    { code: 'da', name: 'Dansk' },
    { code: 'de', name: 'Deutsch' },
    { code: 'fr', name: 'Français' },
    { code: 'es', name: 'Español' },
  ];

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (token) {
      setAuthToken(token);
    }
  }, []);

  useEffect(() => {
    if (authToken) {
      checkAuthStatus();
    } else {
      setCurrentUser(null);
    }

    // Always check usage status
    checkUsageStatus();

    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
        handleGoogleOAuthCallback(code);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [authToken]);

  const checkAuthStatus = async () => {
    if (authToken) {
      try {
        const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
          const user = await response.json();
          setCurrentUser(user);
        } else {
          handleLogout();
        }
      } catch (error) {
        console.error('Auth check error:', error);
        handleLogout();
      }
    }
  };

  const checkUsageStatus = async () => {
    try {
      const headers = {};
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }
      
      const response = await fetch(`${API_BASE}/api/v1/usage-status`, { headers });
      if (response.ok) {
        const status = await response.json();
        setUsageStatus(status);
      }
    } catch (error) {
      console.error('Usage status check error:', error);
    }
  };

  const handleAuthAction = async (url, body) => {
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('authToken', data.access_token);
        setAuthToken(data.access_token);
        setIsAuthModalOpen(false); // Close modal on successful auth
        setShowWelcome(true);
        setTimeout(() => setShowWelcome(false), 4000);
      } else {
        const error = await response.json();
        alert(error.detail || 'Action failed');
      }
    } catch (error) {
      alert('An error occurred. Please try again.');
    }
  };

  const handleLogin = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const email = formData.get('email');
    const password = formData.get('password');
    
    // Use regular login endpoint for both admin and regular users
    const body = { email, password };
    handleAuthAction(`${API_BASE}/api/v1/auth/login`, body);
  };

  const handleRegister = (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const body = {
      full_name: formData.get('name'),
      email: formData.get('email'),
      password: formData.get('password')
    };
    handleAuthAction(`${API_BASE}/api/v1/auth/register`, body);
  };



  const handleLogout = () => {
    setAuthToken(null);
    setCurrentUser(null);
    localStorage.removeItem('authToken');
  };

  const initiateGoogleSignIn = async () => {
    try {
      const urlResponse = await fetch(`${API_BASE}/api/v1/auth/google/url`);
      if (!urlResponse.ok) throw new Error('Failed to get Google OAuth URL');
      const urlData = await urlResponse.json();
      if (!urlData.auth_url) {
          alert('Google Sign-In is not available.');
        return;
      }
      setIsAuthModalOpen(false); // Close modal before redirecting
      window.location.href = urlData.auth_url;
    } catch (error) {
      console.error('Google Sign-In error:', error);
      alert('Could not initiate Google Sign-In.');
    }
  };

  const handleGoogleOAuthCallback = async (code) => {
    try {
      const authResponse = await fetch(`${API_BASE}/api/v1/auth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });
      if (authResponse.ok) {
        const data = await authResponse.json();
            localStorage.setItem('authToken', data.access_token);
        setAuthToken(data.access_token);
        setIsAuthModalOpen(false); // Close modal on successful auth
      } else {
        const error = await authResponse.json();
        alert(error.detail || 'Google Sign-In failed');
      }
    } catch (error) {
      console.error('Google OAuth callback error:', error);
        alert('Google Sign-In failed.');
    }
  };

  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (container) {
      if (container.scrollTop + container.clientHeight >= container.scrollHeight - 100) {
        loadMoreResults();
      }
    }
  };

  const loadMoreResults = async () => {
    if (isSearching || !hasMoreResults) return;
    
    setIsSearching(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/search`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}` 
        },
        body: JSON.stringify({ query: searchQuery, language, source: videoSource, page: searchPage + 1 })
      });
      if (response.ok) {
        const data = await response.json();
        setSearchResults(prevResults => [...prevResults, ...data.results]);
        setSearchPage(prevPage => prevPage + 1);
        if (data.results.length < 10) {
          setHasMoreResults(false);
        }
      } else {
        setHasMoreResults(false);
      }
    } catch (error) {
      setHasMoreResults(false);
    } finally {
      setIsSearching(false);
    }
  };

  // Ändra searchYouTube så att den skickar med videoSource
  const searchYouTube = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setSearchAttempted(true); // Mark that a search has been attempted
    setSearchResults([]); // Clear previous results
    setSearchPage(1);
    setHasMoreResults(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/search`, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}` 
        },
        body: JSON.stringify({ query: searchQuery, language, source: videoSource, page: 1 })
      });
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.results);
        if (data.results.length < 10) {
          setHasMoreResults(false);
        }
      } else {
        alert('Search failed.');
        setHasMoreResults(false);
      }
    } catch (error) {
      alert('An error occurred during search.');
      setHasMoreResults(false);
    } finally {
      setIsSearching(false);
    }
  };

  const processVideo = async () => {
    if (!videoUrl && !selectedVideoId) {
      alert('Please provide a video URL or select a video.');
        return;
      }
      
    setJob(null);
    
    try {
      const headers = {
        'Content-Type': 'application/json'
      };
      
      // Add auth header only if user is logged in
      if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
      }

      const response = await fetch(`${API_BASE}/api/v1/generate`, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
          youtube_url: videoUrl,
          video_id: selectedVideoId,
          language: language,
          pdf_style: pdfStyle,
          include_nutrition: includeNutrition,
          include_tips: includeTips,
          max_steps: maxSteps,
          image_quality: imageQuality,
          // Advanced Settings
          show_images: showImages,
          diet_preference: dietPreference,
          allergies: Object.keys(allergies).filter(a => allergies[a]),
          instruction_level: instructionLevel,
          show_calories: showCalories,
        }),
      });

      if (response.status === 202) {
        const jobData = await response.json();
        setJob(jobData);
      
        // Update usage status after successful job creation
        setTimeout(() => {
          checkUsageStatus();
      }, 1000);
      } else {
        const error = await response.json();
        alert(`Error: ${error.detail}`);
      }
    } catch (error) {
      alert('An unexpected error occurred.');
    }
  };
  
  const resetAll = () => {
    setVideoUrl('');
    setSearchQuery('recipe');
    setSearchResults([]);
    setSelectedVideoId(null);
    setJob(null);
  };
  
  // Show login screen only if explicitly requested, not by default
  const showLoginScreen = false; // Changed from requiring login to allowing anonymous usage

  return (
    <div className="font-poppins bg-gradient-to-br from-[#d6e5dd] to-[#eaf3ef] min-h-screen">
      <Header currentUser={currentUser} handleLogout={handleLogout} showAuthModal={() => setIsAuthModalOpen(true)} usageStatus={usageStatus} showTestPdfModal={() => setIsTestPdfModalOpen(true)} />
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        handleLogin={handleLogin}
        handleRegister={handleRegister}
        initiateGoogleSignIn={initiateGoogleSignIn}
        authTab={authTab}
        setAuthTab={setAuthTab}
      />
      {isTestPdfModalOpen && (
        <TestPdfModal 
          isOpen={isTestPdfModalOpen}
          onClose={() => setIsTestPdfModalOpen(false)}
          currentUser={currentUser}
        />
      )}
      {showWelcome && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-green-600 text-white px-6 py-3 rounded-xl shadow-lg text-lg font-semibold animate-fade-in-out">
          Welcome, {currentUser?.full_name || currentUser?.email}!
        </div>
      )}
      
      <main className="max-w-xl mx-auto py-10 px-8">
        <div className="relative bg-white shadow-xl rounded-2xl p-10">
          <SparklesIcon className="absolute top-0 right-0 h-32 w-32 text-amber-300/30 -translate-y-1/3 translate-x-1/4" />
          
          {job ? (
             <JobStatus job={job} onReset={resetAll} />
          ) : (
            <>
              <h1 className="text-xl font-bold tracking-tight text-gray-800 text-center">
                Turn cooking videos into step-by-step recipes.
              </h1>

              <div className="mt-8 space-y-8">
                <div>
                   <div className="flex gap-2 bg-gray-100 p-1 rounded-xl shadow-inner justify-center">
                    <button onClick={() => setActiveTab('paste')} className={`w-full text-sm rounded-lg px-4 py-2 flex items-center justify-center gap-2 transition-colors ${activeTab === 'paste' ? 'bg-green-600 text-white font-semibold shadow-sm' : 'bg-transparent text-gray-600 hover:bg-white/50'}`}>
                      <LinkIcon className="h-5 w-5"/>
                      <span>Paste Link</span>
                    </button>
                    <button onClick={() => setActiveTab('search')} className={`w-full text-sm rounded-lg px-4 py-2 flex items-center justify-center gap-2 transition-colors ${activeTab === 'search' ? 'bg-green-600 text-white font-semibold shadow-sm' : 'bg-transparent hover:bg-gray-200/50'}`}>
                      <MagnifyingGlassIcon className="h-5 w-5" />
                      Search Recipes
                    </button>
                  </div>
                  <div className="mt-6">
                    {activeTab === 'paste' && (
                      <div>
                        <input
                          id="video-url"
                          type="text"
                          value={videoUrl}
                          onChange={(e) => { setVideoUrl(e.target.value); setSelectedVideoId(null); }}
                          placeholder="Paste a YouTube or TikTok recipe video…"
                          className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                        />
                      </div>
                    )}
                    {activeTab === 'search' && (
                      <div className="flex gap-2">
                        <select
                          value={videoSource}
                          onChange={e => setVideoSource(e.target.value)}
                          className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-green-500"
                        >
                          <option value="youtube">YouTube</option>
                          <option value="tiktok">TikTok</option>
                        </select>
                        <input
                          id="search-query"
                          type="text"
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && searchYouTube()}
                          placeholder="Search for YouTube or TikTok video..."
                          className="flex-grow px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                        />
                        <button onClick={searchYouTube} disabled={isSearching} className="bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-800 transition-colors disabled:bg-gray-400 flex items-center justify-center w-14">
                          {isSearching ? <Spinner /> : <MagnifyingGlassIcon className="h-5 w-5" />}
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Search Results Section */}
                <div className="mt-8">
                  {isSearching && searchResults.length === 0 && (
                    <div className="flex justify-center items-center p-8">
                      <Spinner size="h-8 w-8" color="text-green-600" />
                    </div>
                  )}

                  {searchAttempted && !isSearching && searchResults.length === 0 && (
                    <div className="text-center py-8">
                      <p className="text-gray-500">No videos found for your search. Please try again.</p>
                    </div>
                  )}

                  {searchResults.length > 0 && (
                    <div className="space-y-4">
                      <h3 className="text-gray-800 text-sm font-bold tracking-tight">Search Results</h3>
                      <div 
                        ref={scrollContainerRef}
                        onScroll={handleScroll}
                        className="max-h-[25rem] overflow-y-auto grid grid-cols-2 gap-4 p-2"
                      >
                        {searchResults.map((video) => (
                          <div
                            key={video.video_id}
                            onClick={() => { setSelectedVideoId(video.video_id); setVideoUrl(`https://www.youtube.com/watch?v=${video.video_id}`); }}
                            className={`cursor-pointer border-2 rounded-xl overflow-hidden transition-all duration-200 ${selectedVideoId === video.video_id ? 'border-green-500 shadow-lg scale-105' : 'border-transparent hover:border-green-400/50'}`}
                          >
                            <img src={video.thumbnail_url} alt={video.title} className="w-full h-28 object-cover" />
                            <div className="p-3">
                              <p className="font-semibold text-xs text-gray-800 line-clamp-2">{video.title}</p>
                              <p className="text-xs text-gray-500 mt-1">{video.channel_title}</p>
                            </div>
                          </div>
                        ))}
                        {isSearching && searchResults.length > 0 && (
                          <div className="col-span-2 flex justify-center items-center p-4">
                            <Spinner size="h-6 w-6" color="text-green-600" />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                <div>
                  <select
                    id="language-select"
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-sm text-gray-700"
                  >
                    {languages.map(lang => <option key={lang.code} value={lang.code}>{lang.name}</option>)}
                  </select>
                </div>
                
                {/* Advanced Settings - Only for logged in users */}
                {currentUser && (
                  <div className="border-t border-gray-200 pt-6">
                    <button
                      onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
                      className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                    >
                      <WrenchScrewdriverIcon className="h-4 w-4" />
                      <span>Advanced Settings</span>
                      <svg
                        className={`h-4 w-4 transition-transform ${showAdvancedSettings ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    
                    {showAdvancedSettings && (
                      <div className="mt-4 space-y-4 p-4 bg-gray-50 rounded-lg">
                        {/* 1. Show images */}
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Show Images</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="showImages" checked={showImages} onChange={() => setShowImages(true)} className="mr-2" />
                              Yes
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="showImages" checked={!showImages} onChange={() => setShowImages(false)} className="mr-2" />
                              No
                            </label>
                          </div>
                        </div>
                        
                        {/* 2. Diet preference */}
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Diet preference</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="dietPreference" value="regular" checked={dietPreference === 'regular'} onChange={() => setDietPreference('regular')} className="mr-2" />
                              Regular (default)
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="dietPreference" value="vegetarian" checked={dietPreference === 'vegetarian'} onChange={() => setDietPreference('vegetarian')} className="mr-2" />
                              Vegetarian
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="dietPreference" value="vegan" checked={dietPreference === 'vegan'} onChange={() => setDietPreference('vegan')} className="mr-2" />
                              Vegan
                            </label>
                          </div>
                        </div>
                        
                        {/* 3. Allergies */}
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Allergies</label>
                          <div className="flex flex-wrap gap-4">
                            <label className="flex items-center">
                              <input type="checkbox" checked={allergies.gluten} onChange={() => setAllergies(a => ({ ...a, gluten: !a.gluten }))} className="mr-2" />
                              Gluten
                            </label>
                            <label className="flex items-center">
                              <input type="checkbox" checked={allergies.nuts} onChange={() => setAllergies(a => ({ ...a, nuts: !a.nuts }))} className="mr-2" />
                              Nuts
                            </label>
                            <label className="flex items-center">
                              <input type="checkbox" checked={allergies.eggs} onChange={() => setAllergies(a => ({ ...a, eggs: !a.eggs }))} className="mr-2" />
                              Eggs
                            </label>
                            <label className="flex items-center">
                              <input type="checkbox" checked={allergies.dairy} onChange={() => setAllergies(a => ({ ...a, dairy: !a.dairy }))} className="mr-2" />
                              Dairy
                            </label>
                            <label className="flex items-center">
                              <input type="checkbox" checked={allergies.shellfish} onChange={() => setAllergies(a => ({ ...a, shellfish: !a.shellfish }))} className="mr-2" />
                              Shellfish
                            </label>
                          </div>
                        </div>
                        
                        {/* 4. Instruction detail level */}
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Instruction detail level</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="instructionLevel" value="beginner" checked={instructionLevel === 'beginner'} onChange={() => setInstructionLevel('beginner')} className="mr-2" />
                              Beginner
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="instructionLevel" value="intermediate" checked={instructionLevel === 'intermediate'} onChange={() => setInstructionLevel('intermediate')} className="mr-2" />
                              Intermediate (default)
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="instructionLevel" value="expert" checked={instructionLevel === 'expert'} onChange={() => setInstructionLevel('expert')} className="mr-2" />
                              Expert
                            </label>
                          </div>
                        </div>
                        
                        {/* 5. Show calories / nutrition info */}
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Show calories / nutrition info</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="showCalories" checked={showCalories} onChange={() => setShowCalories(true)} className="mr-2" />
                              Yes
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="showCalories" checked={!showCalories} onChange={() => setShowCalories(false)} className="mr-2" />
                              No (default)
                            </label>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
                

                
                <div className="pt-6 border-t border-gray-200 flex flex-col items-center gap-6">
                  <button onClick={processVideo} className="flex items-center gap-2 w-full justify-center bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-md px-6 py-3 transition-transform hover:scale-[1.02]">
                    <SparklesIcon className="h-6 w-6 mr-2" />
                    <span>Generate Recipe</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}