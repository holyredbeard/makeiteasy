import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { 
  LinkIcon, 
  MagnifyingGlassIcon, 
  SparklesIcon,
  FireIcon,
  XMarkIcon,
  WrenchScrewdriverIcon,
  BookmarkIcon, 
  PlusCircleIcon,
  ArrowLeftIcon,
  ExclamationCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  CogIcon,
  DocumentIcon,
  ArrowDownTrayIcon,
  CheckIcon,
  ClipboardDocumentListIcon,
  ChartPieIcon,
  CloudArrowDownIcon,
  ClockIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';
import logger from './Logger';
import ScrapingStatus from './ScrapingStatus';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

const normalizeUrlPort = (url) => {
  if (!url || typeof url !== 'string') return url;
  return url
    .replace('http://127.0.0.1:8000', 'http://127.0.0.1:8001')
    .replace('http://localhost:8000', 'http://localhost:8001');
};

const Spinner = ({ size = 'h-5 w-5', color = 'text-white' }) => (
  <svg className={`animate-spin ${size} ${color}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
  </svg>
);

// Bold numbers and units in ingredient strings
const renderIngredientEmphasis = (text) => {
  try {
    const UNIT_WORDS = [
      'tsp','teaspoon','teaspoons','tbsp','tablespoon','tablespoons','cup','cups','pinch','pint','pints','quart','quarts','ounce','ounces','oz','lb','lbs',
      'ml','cl','dl','l','g','gram','grams','kg','kilogram','kilograms',
      // Swedish
      'kopp','koppar','tsk','msk','st','pkt'
    ];
    const units = UNIT_WORDS.join('|');
    const combined = new RegExp(`(\\b\\d+[\\d/.,]*\\b|[¼½¾]|\\b(?:${units})\\b)`,`gi`);
    const parts = String(text).split(combined);
    return parts.map((part, idx) => {
      if (!part) return null;
      if (combined.test(part)) {
        combined.lastIndex = 0;
        return <strong key={idx} className="font-semibold text-gray-900">{part}</strong>;
      }
      return <span key={idx}>{part}</span>;
    });
  } catch {
    return text;
  }
};

const InfoCard = ({ label, value }) => {
    const isTime = /prep|cook/i.test(label);
    const normalizedValue = (() => {
        if (!isTime) return value;
        const str = String(value || '').trim();
        if (/min/i.test(str)) return str;
        const num = parseInt(str, 10);
        return Number.isFinite(num) ? `${num} min` : str;
    })();
    const icon = (() => {
        if (/prep/i.test(label)) return { type: 'clock', cls: 'bg-amber-100 text-amber-600' };
        if (/cook/i.test(label)) return { type: 'clock', cls: 'bg-red-100 text-red-600' };
        return { type: 'users', cls: 'bg-blue-100 text-blue-600' };
    })();
    return (
      <div className="bg-white border border-gray-100 p-4 rounded-xl shadow-sm flex items-center gap-3">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center ${icon.cls}`}>
          {icon.type === 'clock' && (<ClockIcon className="w-5 h-5" />)}
          {icon.type === 'users' && (<UserGroupIcon className="w-5 h-5" />)}
        </div>
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-lg font-semibold text-gray-900">{normalizedValue}</p>
        </div>
      </div>
    );
};

const RecipeStreamViewer = ({ status, error, data, onReset, currentUser, videoUrl, isScraping }) => {
  const navigate = useNavigate();
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [showTopImage, setShowTopImage] = useState(true);
  const [showStepImages, setShowStepImages] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [imageOrientation, setImageOrientation] = useState('landscape');

  useEffect(() => {
    if (data.thumbnail_path || data.image_url || data.img) {
      const img = new window.Image();
      const rawSrc = data.thumbnail_path || data.image_url || data.img;
      img.src = normalizeUrlPort(rawSrc);
      img.onload = () => {
        if (img.height > img.width) {
          setImageOrientation('portrait');
        } else {
          setImageOrientation('landscape');
        }
      };
    }
  }, [data.thumbnail_path, data.image_url, data.img]);

  const handleDownloadPdf = async (recipeData) => {
    try {
      const formattedInstructions = recipeData.instructions.map((instruction, idx) => {
        if (typeof instruction === 'string') {
          return { step: idx + 1, description: instruction };
        }
        return { 
          step: instruction.step || idx + 1, 
          description: instruction.description || `Step ${idx + 1}`
        };
      });

      const formattedIngredients = recipeData.ingredients.map(ingredient => {
        if (typeof ingredient === 'string') {
          return { name: ingredient, quantity: '' };
        }
        return ingredient;
      });

      const formattedRequest = {
        ...recipeData,
        ingredients: formattedIngredients,
        instructions: formattedInstructions,
        prep_time: String(recipeData.prep_time_minutes || recipeData.prep_time || ''),
        cook_time: String(recipeData.cook_time_minutes || recipeData.cook_time || ''),
        nutritional_information: recipeData.nutrition || recipeData.nutritional_information,
        image_url: recipeData.img || recipeData.image_url || recipeData.thumbnail_path,
        template_name: "professional",
        image_orientation: "landscape",
        show_top_image: showTopImage,
        show_step_images: showStepImages
      };

      const response = await fetch(`${API_BASE}/generate-pdf`, {
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
      
      const blob = await response.blob();
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
  
  const handleSaveRecipe = async (recipeData) => {
    try {
      console.log('Original recipeData:', recipeData);
      
      // Ensure instructions and ingredients are correctly formatted
      const formattedInstructions = (recipeData.instructions || []).map((inst, idx) => {
        if (typeof inst === 'string') {
          return { step: idx + 1, description: inst, image_path: null };
        }
        return { ...inst, step: inst.step || idx + 1 };
      });

      const formattedIngredients = (recipeData.ingredients || []).map(ing => {
        if (typeof ing === 'string') {
          return { name: ing, quantity: '', notes: null };
        }
        return ing;
      });

                        // Format nutritional_information to be a dictionary if it's a string
                  let formattedNutritionalInfo = null;
                  if (recipeData.nutritional_information) {
                    if (typeof recipeData.nutritional_information === 'string') {
                      // Parse the string into a dictionary format
                      const nutritionText = recipeData.nutritional_information;
                      formattedNutritionalInfo = {
                        summary: nutritionText,
                        calories: null,
                        protein: null,
                        carbohydrates: null,
                        fat: null,
                        fiber: null,
                        sugar: null
                      };
                    } else {
                      formattedNutritionalInfo = recipeData.nutritional_information;
                    }
                  }

                  const formattedRecipeContent = {
                    ...recipeData,
                    servings: String(recipeData.servings),
                    prep_time: String(recipeData.prep_time_minutes || recipeData.prep_time || ''),
                    cook_time: String(recipeData.cook_time_minutes || recipeData.cook_time || ''),
                    instructions: formattedInstructions,
                    ingredients: formattedIngredients,
                    chef_tips: Array.isArray(recipeData.chef_tips) ? recipeData.chef_tips : recipeData.chef_tips ? [recipeData.chef_tips] : [],
                    nutritional_information: recipeData.nutrition || formattedNutritionalInfo,
                    image_url: recipeData.img || recipeData.image_url || recipeData.thumbnail_path,
                  };

      const payload = {
        source_url: videoUrl,
        recipe_content: formattedRecipeContent
      };

      console.log('Sending payload:', JSON.stringify(payload, null, 2));

      const response = await fetch(`${API_BASE}/recipes/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      console.log('Response status:', response.status);
      console.log('Response headers:', response.headers);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Error response body:', errorText);
        let errorBody;
        try {
          errorBody = JSON.parse(errorText);
        } catch (e) {
          errorBody = { detail: errorText };
        }
        console.error("Save recipe error response:", errorBody);
        throw new Error(errorBody.detail || 'Failed to save recipe');
      }

      const savedRecipe = await response.json();
      console.log('Recipe saved successfully:', savedRecipe);
      setShowSuccessModal(true);
      // Navigate after a short delay to show the success modal
      setTimeout(() => {
        navigate('/my-recipes');
      }, 2000); 
    } catch (error) {
      console.error('Save recipe error:', error);
      alert(error.message || 'Failed to save recipe. Please try again.');
    }
  };

  // Normalize various possible nutrition key shapes into a single view model
  const normalizeNutritionForView = (nutrition) => {
    if (!nutrition || typeof nutrition !== 'object') return null;
    const calories = nutrition.calories || nutrition.kcal || nutrition.Calories || null;
    const protein = nutrition.protein || nutrition.protein_g || nutrition.proteinContent || null;
    const fat = nutrition.fat || nutrition.fat_g || nutrition.fatContent || null;
    const carbs = nutrition.carbohydrates || nutrition.carbs || nutrition.carbs_g || nutrition.carbohydrateContent || null;
    return { calories, protein, fat, carbs, summary: nutrition.summary };
  };

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
        ) : isScraping ? (
          <ScrapingStatus isActive={isScraping} />
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
  
  return (
    <div>
      <div className="recipe-display a4-format">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-3xl font-bold">{data.title}</h2>
        </div>
        
        {/* Top section: Image and Description */}
        <div className="flex flex-col md:flex-row gap-8 mb-6">
            <div className="md:w-1/3">
                {(data.thumbnail_path || data.image_url || data.img) && (
                    <img 
                        src={(() => {
                          const raw = (data.thumbnail_path || data.image_url || data.img);
                          const absolute = raw.startsWith('http');
                          const url = absolute ? raw : (STATIC_BASE + raw);
                          return normalizeUrlPort(url);
                        })()} 
                        alt={data.title} 
                        className="w-full h-auto object-cover rounded-lg shadow-md"
                        onError={(e) => { 
                            console.log('Image failed to load:', e.target.src);
                            e.target.style.display = 'none'; 
                        }}
                        onLoad={(e) => {
                            console.log('Image loaded successfully:', e.target.src);
                        }}
                    />
                )}
            </div>
            <div className="md:w-2/3">
                <p className="text-gray-600">{data.description}</p>
            </div>
        </div>

        {/* Info Cards Section */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            {data.servings && <InfoCard label="Servings" value={data.servings} />}
            {data.prep_time_minutes && <InfoCard label="Prep Time" value={`${data.prep_time_minutes} min`} />}
            {data.cook_time_minutes && <InfoCard label="Cook Time" value={`${data.cook_time_minutes} min`} />}
        </div>
        
        {/* Main Content: Ingredients and Instructions */}
        <div className="flex flex-col md:flex-row gap-8">
            <div className="md:w-1/3">
                <h3 className="text-2xl font-semibold mb-4">Ingredients</h3>
                <ul className="list-disc pl-5 space-y-2">
                    {data.ingredients && data.ingredients.map((ing, idx) => (
                        <li key={idx} className="text-gray-700">
                            {typeof ing === 'string'
                              ? renderIngredientEmphasis(ing)
                              : renderIngredientEmphasis(`${ing.quantity || ''} ${ing.name || ing} ${ing.notes ? `(${ing.notes})` : ''}`)}
                        </li>
                    ))}
                </ul>
            </div>
            <div className="md:w-2/3">
                <h3 className="text-2xl font-semibold mb-4">Instructions</h3>
                <ol className="list-decimal pl-5 space-y-4">
                    {data.instructions && data.instructions.map((step, idx) => (
                        <li key={idx} className="text-gray-700">
                            {typeof step === 'string' ? step : step.description || `Step ${idx + 1}`}
                        </li>
                    ))}
                </ol>
            </div>
        </div>
        
        {data.chef_tips && data.chef_tips.length > 0 && (
          <div className="mt-8">
            <h3 className="text-2xl font-semibold mb-4">Chef's Tips</h3>
            <ul className="list-disc pl-5 space-y-2">
              {data.chef_tips.map((tip, idx) => (
                <li key={idx} className="text-gray-700">{tip}</li>
              ))}
            </ul>
          </div>
        )}

        { (data.nutrition || data.nutritional_information) && (
          <div className="mt-8">
            <h3 className="text-2xl font-semibold mb-4">Nutritional Information (per serving)</h3>
            <div className="bg-gray-50 p-4 rounded-lg">
              {(() => {
                const nutritionRaw = data.nutrition || data.nutritional_information;
                if (nutritionRaw && typeof nutritionRaw === 'object') {
                  const n = normalizeNutritionForView(nutritionRaw) || {};
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                      <div>
                        <p className="text-sm text-gray-500">Calories</p>
                        <p className="font-medium">{n.calories || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Protein</p>
                        <p className="font-medium">{n.protein ? (String(n.protein).endsWith('g') ? n.protein : `${n.protein}g`) : 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Fat</p>
                        <p className="font-medium">{n.fat ? (String(n.fat).endsWith('g') ? n.fat : `${n.fat}g`) : 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-500">Carbs</p>
                        <p className="font-medium">{n.carbs ? (String(n.carbs).endsWith('g') ? n.carbs : `${n.carbs}g`) : 'N/A'}</p>
                      </div>
                    </div>
                  );
                }
                return <p className="text-gray-700">{nutritionRaw}</p>;
              })()}
            </div>
          </div>
        )}

        {videoUrl && (
          <div className="mt-8">
            <h3 className="text-2xl font-semibold mb-4">Source</h3>
            <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
              <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
              <a href={videoUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                {videoUrl}
              </a>
            </div>
          </div>
        )}
        
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
      
      {/* Success Modal */}
      {showSuccessModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl transform transition-all">
            <div className="text-center">
              <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-6">
                <CheckIcon className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                Recipe Saved!
              </h3>
              <p className="text-gray-600 mb-6">
                Your recipe has been successfully saved to your collection. You'll be redirected to your recipes page shortly.
              </p>
              <div className="flex justify-center">
                <button
                  onClick={() => {
                    setShowSuccessModal(false);
                    navigate('/my-recipes');
                  }}
                  className="bg-green-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-green-700 transition-colors"
                >
                  Go to My Recipes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default function Food2Guide() {
  const { currentUser } = useOutletContext();
  const [activeTab, setActiveTab] = useState('paste');
  const [videoUrl, setVideoUrl] = useState('');
  const [searchQuery, setSearchQuery] = useState("");
  const [language, setLanguage] = useState('en');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedVideoId, setSelectedVideoId] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [searchPage, setSearchPage] = useState(1);
  const [hasMoreResults, setHasMoreResults] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [recipeData, setRecipeData] = useState({});
  const [streamError, setStreamError] = useState(null);
  const [streamStatus, setStreamStatus] = useState('');
  const scrollContainerRef = useRef(null);

  // Advanced Settings state
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);
  const [showTopImage, setShowTopImage] = useState(true);
  const [showStepImages, setShowStepImages] = useState(false);
  const [dietPreference, setDietPreference] = useState('regular');
  const [allergies, setAllergies] = useState({ gluten: false, nuts: false, eggs: false, dairy: false, shellfish: false });
  const [instructionLevel, setInstructionLevel] = useState('intermediate');
  const [showCalories, setShowCalories] = useState(true);

  const searchYouTube = async () => {
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    setSearchResults([]);
    setSearchPage(1);
    setHasMoreResults(true);
    
    try {
      const response = await fetch(`${API_BASE}/search`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery, language, source: 'youtube', page: 1 })
      });
      
      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.results);
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

  const handleStreamResponse = (url) => {
    setIsStreaming(true);
    setStreamStatus('Initializing stream...');
    setStreamError('');
    setRecipeData({});
    
    const streamUrl = `${API_BASE}/generate-stream?video_url=${encodeURIComponent(url)}&language=${language}`;
    
    const eventSource = new EventSource(streamUrl);
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.status === 'error') {
          setStreamError(data.message);
          setIsStreaming(false);
          eventSource.close();
        } else if (data.status === 'completed') {
          if (data.recipe) {
            setRecipeData(data.recipe);
          }
          setIsStreaming(false); 
          eventSource.close();
        } else if (data.status) {
          setStreamStatus(data.message || data.status);
        }
      } catch (err) {
        setStreamError('Failed to parse server response.');
        setIsStreaming(false);
        eventSource.close();
      }
    };
    
    eventSource.onerror = (err) => {
      setStreamError('Connection to server failed. Please try again.');
      setIsStreaming(false);
      eventSource.close();
    };
  };
  
  const resetAll = () => {
    setVideoUrl('');
    setSearchQuery('');
    setSearchResults([]);
    setSelectedVideoId(null);
    setIsStreaming(false);
    setIsScraping(false);
    setRecipeData({});
    setStreamError(null);
    setStreamStatus('');
  };

  const handleGenerateRecipe = async () => {
    if (!videoUrl) return;

    const isVideo = /youtube\.com|youtu\.be|tiktok\.com/.test(videoUrl);

    setIsStreaming(true);
    setStreamStatus('Initializing...');
    setStreamError(null);
    setRecipeData({});

    if (isVideo) {
      handleStreamResponse(videoUrl);
    } else {
      // It's a website URL, so scrape it
      setIsScraping(true);
      setStreamStatus('Scraping recipe from website...');
      try {
        const response = await fetch(`${API_BASE}/scrape-recipe`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
          body: JSON.stringify({ url: videoUrl })
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'An unknown error occurred during scraping.' }));
          throw new Error(errorData.detail || 'Failed to scrape recipe. The website might be using anti-scraping technologies.');
        }

        const result = await response.json();
        if (result && result.recipe) {
          setRecipeData(result.recipe);
        } else {
          throw new Error('Scraper returned no recipe data. The website structure might not be supported.');
        }
      } catch (err) {
        setStreamError(err.message);
      } finally {
        setIsStreaming(false);
        setIsScraping(false);
      }
    }
  };
  
  const handleVideoSelect = (video) => {
    setSelectedVideoId(video.video_id);
    setVideoUrl(`https://www.youtube.com/watch?v=${video.video_id}`);
  };

  return (
    <div className="space-y-8">
      {/* Main Input Card */}
      <div className="relative bg-white shadow-xl rounded-2xl p-10">
        <SparklesIcon className="absolute top-0 right-0 h-32 w-32 text-amber-300/30 -translate-y-1/3 translate-x-1/4" />
        
        {isStreaming || Object.keys(recipeData).length > 0 || streamError ? (
          <RecipeStreamViewer 
            status={streamStatus}
            error={streamError}
            data={recipeData}
            onReset={resetAll}
            currentUser={currentUser}
            videoUrl={videoUrl}
            isScraping={isScraping}
          />
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
                      placeholder="Paste a recipe link from YouTube, TikTok, or any website..."
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                    />
                  </div>
                )}
                {activeTab === 'search' && (
                  <div className="flex gap-2">
                    <input
                      id="search-query"
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && searchYouTube()}
                      placeholder="Search for YouTube video..."
                      className="flex-grow px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                    />
                    <button onClick={searchYouTube} disabled={isSearching} className="bg-gray-700 text-white px-4 py-2 rounded-lg hover:bg-gray-800 transition-colors disabled:bg-gray-400 flex items-center justify-center w-14">
                      {isSearching ? <Spinner /> : <MagnifyingGlassIcon className="h-5 w-5" />}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {searchResults.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-gray-800 text-sm font-bold tracking-tight">Search Results</h3>
                <div 
                  ref={scrollContainerRef}
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
                </div>
              </div>
            )}
            
            <div className="pt-6 border-t border-gray-200 flex flex-col items-center gap-6">
              {currentUser && (
                <div className="w-full">
                  <button
                    onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
                    className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                  >
                    <WrenchScrewdriverIcon className="h-4 w-4" />
                    <span>Customize Recipe</span>
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
                    <div className="mt-4 max-w-2xl mx-auto rounded-xl bg-gray-50 p-6 shadow-sm">
                      <h3 className="text-base font-semibold mb-4">Customize your recipe</h3>
                      
                      {/* 1. Show images */}
                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Top image (dish preview under title)</label>
                        <div className="flex flex-col space-y-1 mt-2">
                          <label className="flex items-center">
                            <input type="radio" name="showTopImage" checked={showTopImage} onChange={() => setShowTopImage(true)} className="mr-2" />
                            <span className="ml-2">Yes</span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="showTopImage" checked={!showTopImage} onChange={() => setShowTopImage(false)} className="mr-2" />
                            <span className="ml-2">No</span>
                          </label>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Step-by-step images</label>
                        <div className="flex flex-col space-y-1 mt-2">
                          <label className="flex items-center">
                            <input type="radio" name="showStepImages" checked={showStepImages} onChange={() => setShowStepImages(true)} className="mr-2" />
                            <span className="ml-2">Yes</span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="showStepImages" checked={!showStepImages} onChange={() => setShowStepImages(false)} className="mr-2" />
                            <span className="ml-2">No</span>
                          </label>
                        </div>
                      </div>
                      
                      <hr className="border-t border-gray-200 my-5" />
                      
                      {/* 2. Diet preference */}
                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Diet preference</label>
                        <div className="flex flex-col space-y-1 mt-2">
                          <label className="flex items-center">
                            <input type="radio" name="dietPreference" value="regular" checked={dietPreference === 'regular'} onChange={() => setDietPreference('regular')} className="mr-2" />
                            <span className="ml-2">
                              Regular
                              <span className="text-xs text-gray-400 ml-1">(default)</span>
                            </span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="dietPreference" value="vegetarian" checked={dietPreference === 'vegetarian'} onChange={() => setDietPreference('vegetarian')} className="mr-2" />
                            <span className="ml-2">Vegetarian</span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="dietPreference" value="vegan" checked={dietPreference === 'vegan'} onChange={() => setDietPreference('vegan')} className="mr-2" />
                            <span className="ml-2">Vegan</span>
                          </label>
                        </div>
                      </div>
                      
                      {/* 3. Allergies */}
                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Allergies</label>
                        <div className="flex flex-wrap gap-x-4 gap-y-2 mt-2">
                          <label className="flex items-center">
                            <input type="checkbox" checked={allergies.gluten} onChange={() => setAllergies(a => ({ ...a, gluten: !a.gluten }))} className="mr-2" />
                            <span className="ml-2">Gluten</span>
                          </label>
                          <label className="flex items-center">
                            <input type="checkbox" checked={allergies.nuts} onChange={() => setAllergies(a => ({ ...a, nuts: !a.nuts }))} className="mr-2" />
                            <span className="ml-2">Nuts</span>
                          </label>
                          <label className="flex items-center">
                            <input type="checkbox" checked={allergies.eggs} onChange={() => setAllergies(a => ({ ...a, eggs: !a.eggs }))} className="mr-2" />
                            <span className="ml-2">Eggs</span>
                          </label>
                          <label className="flex items-center">
                            <input type="checkbox" checked={allergies.dairy} onChange={() => setAllergies(a => ({ ...a, dairy: !a.dairy }))} className="mr-2" />
                            <span className="ml-2">Dairy</span>
                          </label>
                          <label className="flex items-center">
                            <input type="checkbox" checked={allergies.shellfish} onChange={() => setAllergies(a => ({ ...a, shellfish: !a.shellfish }))} className="mr-2" />
                            <span className="ml-2">Shellfish</span>
                          </label>
                        </div>
                      </div>
                      
                      <hr className="border-t border-gray-200 my-5" />
                      
                      {/* 4. Instruction detail level */}
                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Instruction detail level</label>
                        <div className="flex flex-col space-y-1 mt-2">
                          <label className="flex items-center">
                            <input type="radio" name="instructionLevel" value="beginner" checked={instructionLevel === 'beginner'} onChange={() => setInstructionLevel('beginner')} className="mr-2" />
                            <span className="ml-2">Beginner</span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="instructionLevel" value="intermediate" checked={instructionLevel === 'intermediate'} onChange={() => setInstructionLevel('intermediate')} className="mr-2" />
                            <span className="ml-2">
                              Intermediate
                              <span className="text-xs text-gray-400 ml-1">(default)</span>
                            </span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="instructionLevel" value="expert" checked={instructionLevel === 'expert'} onChange={() => setInstructionLevel('expert')} className="mr-2" />
                            <span className="ml-2">Expert</span>
                          </label>
                        </div>
                      </div>
                      
                      {/* 5. Show calories / nutrition info */}
                      <div>
                        <label className="block text-xs uppercase font-medium text-gray-500 tracking-wide mb-1 mt-5">Show calories / nutrition info</label>
                        <div className="flex flex-col space-y-1 mt-2">
                          <label className="flex items-center">
                            <input type="radio" name="showCalories" checked={showCalories} onChange={() => setShowCalories(true)} className="mr-2" />
                            <span className="ml-2">Yes</span>
                          </label>
                          <label className="flex items-center">
                            <input type="radio" name="showCalories" checked={!showCalories} onChange={() => setShowCalories(false)} className="mr-2" />
                            <span className="ml-2">
                              No
                              <span className="text-xs text-gray-400 ml-1">(default)</span>
                            </span>
                          </label>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <button onClick={handleGenerateRecipe} className="flex items-center gap-2 w-full justify-center bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-md px-6 py-3 transition-transform hover:scale-[1.02]">
                <SparklesIcon className="h-6 w-6 mr-2" />
                <span>Generate Recipe</span>
              </button>
            </div>
          </div>
        </>
      )}
      </div>

      {/* Information Section - Freestanding Cards */}
      {!isStreaming && Object.keys(recipeData).length === 0 && !streamError && (
        <div className="animate-fade-in mt-10">
          <div className="max-w-[900px] mx-auto px-4 mt-10 flex flex-col md:flex-row gap-6 justify-between">
            {/* Structured Recipes Card */}
            <div className="bg-white p-6 rounded-xl shadow-sm w-full min-h-[220px] text-left">
              <div className="flex flex-col">
                <div className="w-5 h-5 text-green-600 mb-2">
                  <ClipboardDocumentListIcon className="w-full h-full" />
                </div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">Structured Recipes</h3>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Get clean recipes with ingredients and steps from videos and blogs.
                </p>
              </div>
            </div>

            {/* Nutrition Info Card */}
            <div className="bg-white p-6 rounded-xl shadow-sm w-full min-h-[220px] text-left">
              <div className="flex flex-col">
                <div className="w-5 h-5 text-green-600 mb-2">
                  <ChartPieIcon className="w-full h-full" />
                </div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">Nutrition Info</h3>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Automatic nutrition facts including calories, protein, fat, and carbs for each recipe.
                </p>
              </div>
            </div>

            {/* Save & Export Card */}
            <div className="bg-white p-6 rounded-xl shadow-sm w-full min-h-[220px] text-left">
              <div className="flex flex-col">
                <div className="w-5 h-5 text-green-600 mb-2">
                  <CloudArrowDownIcon className="w-full h-full" />
                </div>
                <h3 className="text-base font-semibold text-gray-900 mb-2">Save & Export</h3>
                <p className="text-sm text-gray-600 leading-relaxed">
                  Save your favorite recipes or export them as PDF for easy access anytime.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}