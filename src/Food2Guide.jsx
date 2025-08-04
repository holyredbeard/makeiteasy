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
  BookOpenIcon, 
  BookmarkIcon, 
  PlusCircleIcon,
  ArrowLeftIcon,
  ExclamationCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  CogIcon,
  DocumentIcon,
  ArrowUturnLeftIcon,
  BugAntIcon
} from '@heroicons/react/24/outline';
import logger from './Logger';
import LogPanel from './LogPanel';

const API_BASE = 'http://localhost:8001';

const Spinner = ({ size = 'h-5 w-5', color = 'text-white' }) => (
  <svg className={`animate-spin ${size} ${color}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);



// RecipeStreamViewer component to display the recipe and buttons
const RecipeStreamViewer = ({ status, error, data, onReset, currentUser }) => {
  // Visa receptet direkt istället för knappar
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  
  // Handle PDF download
  const handleDownloadPdf = async (recipeData) => {
    try {
      // Debug: Log recipeData to see if thumbnail_path is present
      console.log('Recipe data for PDF generation:', recipeData);
      console.log('Thumbnail path in recipeData:', recipeData.thumbnail_path);
      
      // Convert instructions format if needed
      const formattedInstructions = recipeData.instructions.map((instruction, idx) => {
        if (typeof instruction === 'string') {
          return { step: idx + 1, description: instruction };
        } else if (typeof instruction === 'object') {
          return { 
            step: instruction.step || idx + 1, 
            description: instruction.description || `Step ${idx + 1}`
          };
        }
        return { step: idx + 1, description: `Step ${idx + 1}` };
      });

      // Format ingredients if needed
      const formattedIngredients = recipeData.ingredients.map(ingredient => {
        if (typeof ingredient === 'string') {
          return { name: ingredient, quantity: '' };
        }
        return ingredient;
      });

      // Create properly formatted request
      const formattedRequest = {
        ...recipeData,
        ingredients: formattedIngredients,
        instructions: formattedInstructions,
        template_name: "professional",
        image_orientation: "landscape",
        show_top_image: showTopImage,
        show_step_images: showStepImages
      };

      // Debug: Log formatted request to see if thumbnail_path is included
      console.log('Formatted request for PDF generation:', formattedRequest);
      console.log('Thumbnail path in formatted request:', formattedRequest.thumbnail_path);

      const response = await fetch(`${API_BASE}/api/v1/generate-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formattedRequest),
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      // Create a blob from the PDF stream
      const blob = await response.blob();
      
      // Create a link element and trigger download
      const downloadUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `${formattedRequest.title.replace(/\s+/g, '_')}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Failed to download PDF:', err);
      alert('Failed to download PDF. Please try again.');
    }
  };
  
  // Handle saving recipe (for logged in users)
  const handleSaveRecipe = async (recipeData) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/recipes/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          recipe_content: recipeData,
          source_url: '' // We don't have this in this context
        }),
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      alert('Recipe saved successfully!');
    } catch (err) {
      console.error('Failed to save recipe:', err);
      alert('Failed to save recipe. Please try again.');
    }
  };
  
  // If still streaming or error occurred
  if (Object.keys(data).length === 0) {
    return (
      <div className="text-center">
        {error ? (
          <div className="text-red-500 mb-4">
            <ExclamationCircleIcon className="h-12 w-12 mx-auto mb-2 text-red-500" />
            <h3 className="text-xl font-bold mb-2">Error</h3>
            <p>{error}</p>
            <button
              onClick={onReset}
              className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
            >
              Try Again
            </button>
          </div>
        ) : (
          <div>
            <div className="flex justify-center mb-4">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
            <h3 className="text-xl font-bold mb-2">Processing</h3>
            <p className="text-gray-600">{status}</p>
          </div>
        )}
      </div>
    );
  }
  
  // Recipe is ready, show recipe content directly
  return (
    <div>
      {/* Recipe display view - A4 width optimized */}
      <div className="recipe-display a4-format">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold">{data.title}</h2>
        </div>
        
        {data.thumbnail_path && (
          <div className="mb-6">
            <img 
              src={data.thumbnail_path} 
              alt={data.title} 
              className="w-full h-auto object-cover rounded-lg shadow-md" 
            />
          </div>
        )}
        
        <p className="text-gray-600 mb-6">{data.description}</p>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-50 p-3 rounded-lg">
            <p className="text-sm text-gray-500">Servings</p>
            <p className="font-medium">{data.servings}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded-lg">
            <p className="text-sm text-gray-500">Prep Time</p>
            <p className="font-medium">{data.prep_time}</p>
          </div>
          <div className="bg-gray-50 p-3 rounded-lg">
            <p className="text-sm text-gray-500">Cook Time</p>
            <p className="font-medium">{data.cook_time}</p>
          </div>
        </div>
        
        <div className="flex flex-col md:flex-row gap-8 mb-8">
          <div className="md:w-1/3">
            <h3 className="text-2xl font-semibold mb-4">Ingredients</h3>
            <ul className="list-disc pl-5 space-y-2">
              {data.ingredients && data.ingredients.map((ing, idx) => (
                <li key={idx} className="text-gray-700">
                  {ing.quantity} {ing.name} {ing.notes && <span className="text-gray-500">({ing.notes})</span>}
                </li>
              ))}
            </ul>
          </div>
          
          <div className="md:w-2/3">
            <h3 className="text-2xl font-semibold mb-4">Instructions</h3>
            <ol className="list-decimal pl-5 space-y-4">
              {data.instructions && data.instructions.length > 0 ? (
                data.instructions.map((step, idx) => (
                  <li key={idx} className="text-gray-700">
                    {typeof step === 'string' ? step : step.description || `Steg ${idx + 1}`}
                  </li>
                ))
              ) : (
                <div className="text-red-500 font-medium">Instruktioner saknas</div>
              )}
            </ol>
          </div>
        </div>
        
        {Array.isArray(data.chef_tips) && data.chef_tips.length > 0 && (
          <div className="mb-8 bg-amber-50 p-4 rounded-lg">
            <h3 className="text-xl font-semibold mb-2">Chef Tips</h3>
            <ul className="list-disc pl-5 space-y-2">
              {data.chef_tips.map((tip, idx) => (
                <li key={idx} className="text-gray-700">{tip}</li>
              ))}
            </ul>
          </div>
        )}
        
        {data.nutritional_information && (
          <div className="border-t pt-6 mt-6">
            <h3 className="text-lg font-semibold mb-2">Nutritional Information</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {data.nutritional_information.calories && (
                <div>
                  <p className="text-sm text-gray-500">Calories</p>
                  <p>{data.nutritional_information.calories}</p>
                </div>
              )}
              {data.nutritional_information.protein && (
                <div>
                  <p className="text-sm text-gray-500">Protein</p>
                  <p>{data.nutritional_information.protein}</p>
                </div>
              )}
              {data.nutritional_information.carbohydrates && (
                <div>
                  <p className="text-sm text-gray-500">Carbs</p>
                  <p>{data.nutritional_information.carbohydrates}</p>
                </div>
              )}
              {data.nutritional_information.fat && (
                <div>
                  <p className="text-sm text-gray-500">Fat</p>
                  <p>{data.nutritional_information.fat}</p>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Admin settings */}
        {currentUser?.is_admin && (
          <div className="mb-6 border border-gray-200 rounded-lg p-4 bg-gray-50 mt-8">
            <button 
              onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
              className="flex items-center justify-between w-full text-left text-sm font-medium text-gray-700 mb-2"
            >
              <span className="flex items-center gap-2">
                <CogIcon className="h-5 w-5 text-gray-500" />
                Admin Settings
              </span>
              <ChevronDownIcon className={`h-5 w-5 transition-transform ${showAdvancedSettings ? 'rotate-180' : ''}`} />
            </button>
            
            {showAdvancedSettings && (
              <div className="pt-2 space-y-3 border-t border-gray-200">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Show Images in PDF</label>
                  <div className="flex gap-4">
                    <label className="flex items-center">
                      <input 
                        type="radio" 
                        name="showImages" 
                        checked={showImages} 
                        onChange={() => setShowImages(true)} 
                        className="mr-2" 
                      />
                      Yes
                    </label>
                    <label className="flex items-center">
                      <input 
                        type="radio" 
                        name="showImages" 
                        checked={!showImages} 
                        onChange={() => setShowImages(false)} 
                        className="mr-2" 
                      />
                      No
                    </label>
                  </div>
                </div>
                
                <button
                  onClick={showTestPdfModal}
                  className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <DocumentIcon className="h-5 w-5" />
                  Test PDF Templates
                </button>
              </div>
            )}
          </div>
        )}
        
        {/* Action buttons at the bottom */}
        <div className="flex flex-wrap justify-center gap-4 mt-8 pt-6 border-t border-gray-200">
          <button
            onClick={() => handleDownloadPdf(data)}
            className="flex items-center justify-center gap-2 bg-green-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-green-700 transition-colors"
          >
            <ArrowDownTrayIcon className="h-5 w-5" />
            <span>Download PDF</span>
          </button>
          
          {currentUser && (
            <button
              onClick={() => handleSaveRecipe(data)}
              className="flex items-center justify-center gap-2 bg-purple-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-purple-700 transition-colors"
            >
              <BookmarkIcon className="h-5 w-5" />
              <span>Save to Recipes</span>
            </button>
          )}
          
          <button
            onClick={onReset}
            className="flex items-center justify-center gap-2 bg-amber-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-amber-700 transition-colors"
          >
            <PlusCircleIcon className="h-5 w-5" />
            <span>Create New Recipe</span>
          </button>
        </div>
      </div>
    </div>
  );
};


const MyRecipesViewer = ({ onBack, currentUser }) => {
  const [recipes, setRecipes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchRecipes = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/v1/recipes`, { credentials: 'include' });
        if (!response.ok) {
          throw new Error('Failed to fetch recipes');
        }
        const data = await response.json();
        setRecipes(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRecipes();
  }, []);

  if (isLoading) {
    return (
      <div className="text-center">
        <Spinner size="h-8 w-8" color="text-green-600" />
        <p className="mt-2">Loading your recipes...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-red-500">
        <p>Error: {error}</p>
        <button onClick={onBack} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-md">Back</button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-3xl font-bold">My Saved Recipes</h2>
        <button onClick={onBack} className="flex items-center text-gray-500 hover:text-gray-700 text-sm">
          <ArrowLeftIcon className="h-4 w-4 mr-1" />
          <span>Back to Generator</span>
        </button>
      </div>
      {recipes.length === 0 ? (
        <p>You haven't saved any recipes yet.</p>
      ) : (
        <div className="space-y-4">
          {recipes.map(recipe => (
            <div key={recipe.id} className="bg-white p-4 rounded-lg shadow-md border border-gray-200">
              <h3 className="font-bold text-lg">{recipe.recipe_content.title}</h3>
              <p className="text-sm text-gray-600">Saved on: {new Date(recipe.created_at).toLocaleDateString()}</p>
              <a href={recipe.source_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 text-sm hover:underline">
                {recipe.source_url}
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Header = ({ currentUser, handleLogout, showAuthModal, usageStatus, showTestPdfModal, showMyRecipes }) => (
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
            <button onClick={showMyRecipes} className="flex items-center gap-2 text-sm text-gray-600 hover:text-blue-600 transition-colors">
              <BookOpenIcon className="h-5 w-5" />
              <span className="hidden sm:block">My Recipes</span>
            </button>
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

const AuthModal = ({ isOpen, onClose, initiateGoogleSignIn, authTab, setAuthTab }) => {
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
              <form className="space-y-4">
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
              <form className="space-y-4">
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
  const [selectedTemplate, setSelectedTemplate] = useState('professional');
  const [selectedOrientation, setSelectedOrientation] = useState('landscape');
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Define available templates
  const templates = ['default', 'modern', 'professional'];
  
  // Add CSS template selection to the PDF generation
  const handleTemplateChange = (e) => {
    setSelectedTemplate(e.target.value);
  };
  

  const generateTestPdf = async () => {
    setIsGenerating(true);
    try {
      // Create test recipe data
      const testRecipe = {
        title: "Test Recipe for Template Preview",
        description: "This is a test recipe to preview the selected template style.",
        ingredients: [
          { name: "Ingredient 1", quantity: "100g" },
          { name: "Ingredient 2", quantity: "2 tbsp" },
          { name: "Ingredient 3", quantity: "1 cup" },
        ],
        instructions: [
          { step: 1, description: "Step 1: Do something with the ingredients" },
          { step: 2, description: "Step 2: Mix everything together" },
          { step: 3, description: "Step 3: Cook for 10 minutes" }
        ],
        prep_time: "10 min",
        cook_time: "20 min",
        servings: 4,
        difficulty: "Easy"
      };
      
      // Add template and orientation to the request
      const requestData = {
        ...testRecipe,
        template_name: selectedTemplate,
        image_orientation: selectedOrientation
      };
      
      const response = await fetch(`${API_BASE}/api/v1/generate-pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
        credentials: 'include'
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
                CSS Template
              </label>
              <select 
                value={selectedTemplate}
                onChange={handleTemplateChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                {templates.map(template => (
                  <option key={template} value={template}>{template.charAt(0).toUpperCase() + template.slice(1)}</option>
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
        const response = await fetch(`${API_BASE}/api/v1/status/${job.job_id}`, { credentials: 'include' });
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
  const [showTopImage, setShowTopImage] = useState(true);
  const [showStepImages, setShowStepImages] = useState(true);

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

  const [showMyRecipes, setShowMyRecipes] = useState(false);

  // States for streaming
  const [isStreaming, setIsStreaming] = useState(false);
  const [recipeData, setRecipeData] = useState({});
  const [streamError, setStreamError] = useState(null);
  const [streamStatus, setStreamStatus] = useState('');
    
  // States for logging
  const [showLogPanel, setShowLogPanel] = useState(true); // Visa alltid som standard

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
    logger.info('🚀 Food2Guide-komponenten initialiseras');
    
    // Försök att hämta användarinfo från backend via cookies
    const fetchUser = async () => {
      try {
        logger.info('👤 Hämtar användarinformation...');
        logger.apiCall('GET', '/api/v1/auth/me');
        
        const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
          credentials: 'include' // Viktigt: skicka cookies
        });
        
        logger.apiResponse('GET', '/api/v1/auth/me', response.status);
        
        if (response.ok) {
          const user = await response.json();
          logger.success('✅ Användare inloggad', { user: user.email, admin: user.is_admin });
          setCurrentUser(user);
        } else {
          logger.info('ℹ️ Ingen inloggad användare (förväntat)');
        }
      } catch (error) {
        logger.error('❌ Misslyckades att hämta användare', error);
      }
    };
    
    fetchUser();
    
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
      logger.info('🔗 OAuth-kod hittad i URL, hanterar callback...');
      handleGoogleOAuthCallback(code);
      window.history.replaceState({}, document.title, window.location.pathname);
    } else {
      checkUsageStatus();
    }
  }, []);



  const checkUsageStatus = async () => {
    try {
      logger.info('📊 Kontrollerar användningsstatus...');
      logger.apiCall('GET', '/api/v1/usage-status');
      
      const response = await fetch(`${API_BASE}/api/v1/usage-status`, { credentials: 'include' });
      
      logger.apiResponse('GET', '/api/v1/usage-status', response.status);
      
      if (response.ok) {
        const status = await response.json();
        logger.success('📊 Användningsstatus hämtad', status);
        setUsageStatus(status);
      } else {
        logger.warn('⚠️ Kunde inte hämta användningsstatus');
      }
    } catch (error) {
      logger.error('❌ Fel vid kontroll av användningsstatus', error);
    }
  };


  const handleGoogleOAuthCallback = async (code) => {
    try {
      const authResponse = await fetch(`${API_BASE}/api/v1/auth/google/callback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
        credentials: 'include' // Viktigt: för att cookies ska sättas
      });

      if (authResponse.ok) {
        const data = await authResponse.json();
        if (data.user) {
          setCurrentUser(data.user);
          setIsAuthModalOpen(false);
          setShowWelcome(true);
          setTimeout(() => setShowWelcome(false), 4000);
        } else {
          alert('User data was not found in the response.');
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
      await fetch(`${API_BASE}/api/v1/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (error) {
      console.error("Logout failed", error);
    } finally {
      setCurrentUser(null);
    }
  };

  const initiateGoogleSignIn = async () => {
    try {
      const urlResponse = await fetch(`${API_BASE}/api/v1/auth/google/url`, { credentials: 'include' });
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
        credentials: 'include',
        headers: { 
            'Content-Type': 'application/json'
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
    if (!searchQuery.trim()) {
      logger.warn('⚠️ Tomt sökfält - avbryter sökning');
      return;
    }
    
    logger.info('🔍 STARTAR VIDEOSÖKNING', { query: searchQuery, language, source: videoSource });
    logger.apiCall('POST', '/api/v1/search', { query: searchQuery, language, source: videoSource, page: 1 });
    
    setIsSearching(true);
    setSearchAttempted(true); // Mark that a search has been attempted
    setSearchResults([]); // Clear previous results
    setSearchPage(1);
    setHasMoreResults(true);
    
    try {
      const startTime = Date.now();
      const response = await fetch(`${API_BASE}/api/v1/search`, {
        method: 'POST',
        credentials: 'include',
        headers: { 
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: searchQuery, language, source: videoSource, page: 1 })
      });
      
      const duration = Date.now() - startTime;
      logger.performance('Sökning', duration);
      
      logger.apiResponse('POST', '/api/v1/search', response.status);
      
      if (response.ok) {
        const data = await response.json();
        logger.success(`✅ ${data.results.length} videor hittade`, { count: data.results.length });
        setSearchResults(data.results);
        if (data.results.length < 10) {
          setHasMoreResults(false);
          logger.info('ℹ️ Inga fler resultat att ladda');
        }
      } else {
        logger.error('❌ Sökning misslyckades', null, { status: response.status });
        alert('Search failed.');
        setHasMoreResults(false);
      }
    } catch (error) {
      logger.error('❌ Fel vid sökning', error);
      alert('An error occurred during search.');
      setHasMoreResults(false);
    } finally {
      setIsSearching(false);
      logger.info('🔍 Sökning avslutad');
    }
  };

  const processVideo = async () => {
    if (!videoUrl) {
      alert('Please provide a video URL.');
      return;
    }
    
    setIsStreaming(true);
    setRecipeData({});
    setStreamError(null);
    setStreamStatus('Initializing stream...');

    const url = `${API_BASE}/api/v1/generate-stream?video_url=${encodeURIComponent(videoUrl)}&language=${language}`;
    
    const eventSource = new EventSource(url, { withCredentials: true });

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.status === 'error') {
          setStreamError(data.message);
          setStreamStatus('Error occurred.');
          setIsStreaming(false);
          eventSource.close();
        } else if (data.status === 'done') {
          // This assumes the final recipe is sent with the 'done' status.
          // If not, we might need to adjust the backend.
          setRecipeData(data.recipe || recipeData); // Use final recipe or accumulated one.
          setStreamStatus('Recipe generation complete!');
          setIsStreaming(false); // Stop streaming view
          eventSource.close();
        } else if (data.status) {
          // It's a status update
          setStreamStatus(data.message);
        }
        
        // This handles the recipe data chunk. Since we send the full recipe at the end,
        // we can just update the state with the latest complete recipe object.
        if (data.recipe) {
          // Check if it's a complete recipe object, not a partial string
          if (typeof data.recipe === 'object' && data.recipe.title) {
            setRecipeData(data.recipe);
          }
        }
      } catch (e) {
        console.error('Failed to parse stream data:', e, 'Raw data:', event.data);
      }
    };

    eventSource.onerror = (err) => {
      console.error('EventSource failed:', err);
      setStreamError('Failed to connect to the server. Please check your connection and try again.');
      setStreamStatus('Connection error.');
      setIsStreaming(false);
      eventSource.close();
    };
  };

  const handleStreamResponse = (url) => {
    logger.info('🌊 STARTAR STREAMING-PROCESS', { url, language });
    logger.stream('📡 Initialiserar EventSource-anslutning...');
    
    setIsStreaming(true);
    setStreamStatus('Initializing stream...');
    setStreamError('');
    setRecipeData({});
    logger.stream(`Startar stream för URL: ${url}`);

    
    // Add showImages parameter to the URL if the user is an admin
    let streamUrl = `${API_BASE}/api/v1/generate-stream?video_url=${encodeURIComponent(url)}&language=${language}`;
    if (currentUser?.is_admin) {
      streamUrl += `&show_top_image=${showTopImage}&show_step_images=${showStepImages}`;
      logger.info('👑 Admin-inställningar tillagda', { showTopImage, showStepImages });
    }
    
    logger.info('🔗 EventSource URL skapad', { streamUrl });
    
    const eventSource = new EventSource(streamUrl);
    // EventSource stödjer inte withCredentials som en inställning
    // eventSource.withCredentials = true;
    
    
    
    eventSource.onopen = () => {
      logger.success('✅ EventSource-anslutning öppnad');
    };
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Logga alltid rådata för felsökning
        logger.debug('📨 Mottaget EventSource-meddelande', { eventData: event.data });
        logger.stream('📦 Parsed stream data', data);

        // Skicka vidare backend-loggar till frontend-loggern
        if (data.log) {
            logger.info(`[BACKEND] ${data.log.message}`, data.log.extra);
        }

        if (data.status === 'error') {
          logger.error('❌ Stream-fel mottaget', null, data);
          setStreamError(data.message);
          setStreamStatus('Error occurred.');
          setIsStreaming(false);
          eventSource.close();
        } else if (data.status === 'completed') {
          logger.success('🎉 Stream avslutad!');
          if (data.recipe) {
            logger.success('📄 Recept mottaget', { 
              title: data.recipe.title,
              ingredientCount: data.recipe.ingredients?.length,
              instructionCount: data.recipe.instructions?.length
            });
            setRecipeData(data.recipe);
          }
          setStreamStatus('Recipe generation complete!');
          setIsStreaming(false); 
          eventSource.close();
        } else if (data.status) {
          const statusMessage = data.message || data.status;
          logger.stream(`📡 Status: ${data.status}`, { message: statusMessage, debug: data.debug_info });
          setStreamStatus(statusMessage);
        }
      } catch (err) {
        logger.error('❌ Fel vid parsing av EventSource-data', err, { eventData: event.data });
        setStreamError('Failed to parse server response.');
        setIsStreaming(false);
        eventSource.close();
      }
    };
    
    eventSource.onerror = (err) => {
      logger.error('❌ EventSource-fel', err);
      setStreamError('Connection to server failed. Please try again.');
      setIsStreaming(false);
      
      eventSource.close();
    };
  };
  
  const resetAll = () => {
    logger.info('🔄 Återställer all data...');
    setVideoUrl('');
    setSearchQuery('recipe');
    setSearchResults([]);
    setSelectedVideoId(null);
    setJob(null);
    setIsStreaming(false);
    setRecipeData({});
    setStreamError(null);
    setStreamStatus('');
    logger.success('✅ All data återställd');
  };
  
  // Show login screen only if explicitly requested, not by default
  const showLoginScreen = false; // Changed from requiring login to allowing anonymous usage
  
  // Function to show the Test PDF modal for admin users
  const showTestPdfModal = () => {
    if (currentUser?.is_admin) {
      setIsTestPdfModalOpen(true);
    }
  };

  // Handle generating a recipe from a video URL
  const handleGenerateRecipe = () => {
    if (!videoUrl) {
      logger.warn('⚠️ Ingen video-URL angiven');
      return;
    }
    
    logger.info('🚀 STARTAR RECEPTGENERERING', { 
      videoUrl, 
      language, 
      isAdmin: currentUser?.is_admin,
      showTopImage,
      showStepImages 
    });
    logger.event('GENERATE_RECIPE_STARTED', { videoUrl, language });
    
    // Reset any previous data
    setJob(null);
    setRecipeData({});
    setStreamError('');
    
    logger.debug('🧹 Föregående data rensad');
    
    // Start the streaming process
    handleStreamResponse(videoUrl);
  };
  
  // Handle video selection from search
  const handleVideoSelect = (video) => {
    logger.info('🎥 Video vald från sökresultat', { 
      videoId: video.video_id, 
      title: video.title,
      channel: video.channel_title 
    });
    logger.event('VIDEO_SELECTED', { video });
    
    setSelectedVideoId(video.video_id);
    setVideoUrl(`https://www.youtube.com/watch?v=${video.video_id}`);
    
    logger.success('✅ Video URL satt', { url: `https://www.youtube.com/watch?v=${video.video_id}` });
  };

  return (
    <div className="font-poppins bg-gradient-to-br from-[#d6e5dd] to-[#eaf3ef] min-h-screen">
      <Header currentUser={currentUser} handleLogout={handleLogout} showAuthModal={() => setIsAuthModalOpen(true)} usageStatus={usageStatus} showTestPdfModal={() => setIsTestPdfModalOpen(true)} showMyRecipes={() => setShowMyRecipes(true)} />

      
      {/* LOGGPANEL - Alltid synlig för alla användare */}
      <LogPanel 
        isVisible={showLogPanel} 
        onToggle={() => setShowLogPanel(!showLogPanel)} 
      />
      
      {/* Knapp för att visa/dölja loggar - fast position */}
      <button
        onClick={() => setShowLogPanel(!showLogPanel)}
        className="fixed bottom-4 left-4 bg-gray-800 hover:bg-gray-700 text-white p-3 rounded-full shadow-lg z-40 transition-all duration-300"
        title={showLogPanel ? 'Dölj loggar' : 'Visa loggar'}
      >
        <BugAntIcon className="h-6 w-6" />
      </button>
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
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
      
      <main className="max-w-3xl mx-auto py-10 px-8">
        <div className="relative bg-white shadow-xl rounded-2xl p-10">
          <SparklesIcon className="absolute top-0 right-0 h-32 w-32 text-amber-300/30 -translate-y-1/3 translate-x-1/4" />
          
          {showMyRecipes ? (
            <MyRecipesViewer onBack={() => setShowMyRecipes(false)} currentUser={currentUser} />
          ) : isStreaming || Object.keys(recipeData).length > 0 || streamError ? (
            <RecipeStreamViewer 
              status={streamStatus}
              error={streamError}
              data={recipeData}
              onReset={resetAll}
              currentUser={currentUser}
            />
          ) : job ? (
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
                      <div className="flex justify-between items-center">
                        <h3 className="text-gray-800 text-sm font-bold tracking-tight">Search Results</h3>
                        <button 
                          onClick={() => {
                            setSearchResults([]);
                            setSearchAttempted(false);
                            setActiveTab('paste');
                          }}
                          className="flex items-center text-gray-500 hover:text-gray-700 text-sm"
                        >
                          <ArrowLeftIcon className="h-4 w-4 mr-1" />
                          <span>Back</span>
                        </button>
                      </div>
                      <div 
                        ref={scrollContainerRef}
                        onScroll={handleScroll}
                        className="max-h-[25rem] overflow-y-auto grid grid-cols-2 gap-4 p-2"
                      >
                        {searchResults.map((video) => (
                          <div
                            key={video.video_id}
                            onClick={() => handleVideoSelect(video)}
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
                          <label className="block text-sm font-medium text-gray-700 mb-2">Top image (dish preview under title)</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="showTopImage" checked={showTopImage} onChange={() => setShowTopImage(true)} className="mr-2" />
                              Yes
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="showTopImage" checked={!showTopImage} onChange={() => setShowTopImage(false)} className="mr-2" />
                              No
                            </label>
                          </div>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">Step-by-step images</label>
                          <div className="flex gap-4">
                            <label className="flex items-center">
                              <input type="radio" name="showStepImages" checked={showStepImages} onChange={() => setShowStepImages(true)} className="mr-2" />
                              Yes
                            </label>
                            <label className="flex items-center">
                              <input type="radio" name="showStepImages" checked={!showStepImages} onChange={() => setShowStepImages(false)} className="mr-2" />
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
                  <button onClick={handleGenerateRecipe} className="flex items-center gap-2 w-full justify-center bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-md px-6 py-3 transition-transform hover:scale-[1.02]">
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