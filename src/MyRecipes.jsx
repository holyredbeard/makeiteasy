import React, { useState, useEffect } from 'react';
import { 
  ViewColumnsIcon,
  Bars3Icon,
  ChevronDownIcon,
  LinkIcon,
  XMarkIcon, 
  ArrowDownTrayIcon, 
  BookmarkIcon,
  CheckIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8000/api/v1';

const MyRecipes = () => {
    const [recipes, setRecipes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    const [showRecipeModal, setShowRecipeModal] = useState(false);
    const [imageOrientation, setImageOrientation] = useState('landscape');
    const [viewMode, setViewMode] = useState('image_title'); // 'image_title', 'image_description', 'image_ingredients', 'title_only'
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [layoutMode, setLayoutMode] = useState('grid-3'); // 'grid-3', 'grid-4', 'list'
    const [isLayoutDropdownOpen, setIsLayoutDropdownOpen] = useState(false);

    const viewOptions = {
        image_title: 'Image + Title',
        image_description: 'Image + Description',
        image_ingredients: 'Image + Ingredients',
        title_only: 'Title Only',
    };

    const layoutOptions = {
        'grid-2': { name: 'Grid (2 cols)', icon: ViewColumnsIcon },
        'grid-3': { name: 'Grid (3 cols)', icon: ViewColumnsIcon },
        'list': { name: 'List', icon: Bars3Icon },
    };

    useEffect(() => {
        if (showRecipeModal && selectedRecipe && selectedRecipe.recipe_content.thumbnail_path) {
            const img = new window.Image();
            img.src = selectedRecipe.recipe_content.thumbnail_path;
            img.onload = () => {
                if (img.height > img.width) {
                    setImageOrientation('portrait');
                } else {
                    setImageOrientation('landscape');
                }
            };
        }
    }, [selectedRecipe, showRecipeModal]);

    useEffect(() => {
        if (layoutMode === 'list') {
            setViewMode('title_only');
        }
    }, [layoutMode]);

    useEffect(() => {
        const fetchRecipes = async () => {
            try {
                const response = await fetch(`${API_BASE}/recipes`, {
                    credentials: 'include'
                });
                if (!response.ok) {
                    throw new Error('Failed to fetch recipes');
                }
                const data = await response.json();
                setRecipes(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchRecipes();
    }, []);

    const handleRecipeClick = (recipe) => {
        setSelectedRecipe(recipe);
        setShowRecipeModal(true);
    };

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
                template_name: "professional",
                image_orientation: "landscape",
                show_top_image: true,
                show_step_images: true
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

    if (loading) {
        return (
            <div className="container mx-auto p-8">
                <div className="flex justify-center items-center h-64">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container mx-auto p-8">
                <div className="text-center">
                    <ExclamationCircleIcon className="h-12 w-12 mx-auto mb-4 text-red-500" />
                    <h3 className="text-xl font-bold mb-2">Error</h3>
                    <p className="text-red-600">{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="container mx-auto p-8">
            <div className="flex justify-between items-center mb-8">
                <h1 className="text-3xl font-bold">My Saved Recipes</h1>
                <div className="flex gap-4">
                    {/* View Mode Dropdown */}
                    <div className="relative">
                        <button 
                            onClick={() => layoutMode !== 'list' && setIsDropdownOpen(!isDropdownOpen)}
                            className={`flex items-center gap-2 bg-gray-100  text-gray-700 font-semibold py-2 px-4 rounded-lg transition-colors ${layoutMode === 'list' ? 'cursor-not-allowed bg-gray-200' : 'hover:bg-gray-200'}`}
                            disabled={layoutMode === 'list'}
                        >
                            <span>View: {viewOptions[viewMode]}</span>
                            <ChevronDownIcon className={`h-5 w-5 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
                        </button>
                        {isDropdownOpen && (
                            <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg z-10">
                                {Object.entries(viewOptions).map(([key, value]) => (
                                    <button 
                                        key={key}
                                        onClick={() => { setViewMode(key); setIsDropdownOpen(false); }}
                                        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                    >
                                        {value}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    {/* Layout Mode Dropdown */}
                    <div className="relative">
                        <button 
                            onClick={() => setIsLayoutDropdownOpen(!isLayoutDropdownOpen)}
                            className="flex items-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-2 px-4 rounded-lg transition-colors"
                        >
                            {React.createElement(layoutOptions[layoutMode].icon, { className: 'h-5 w-5' })}
                            <span>{layoutOptions[layoutMode].name}</span>
                        </button>
                        {isLayoutDropdownOpen && (
                            <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-10">
                                {Object.entries(layoutOptions).map(([key, { name, icon }]) => (
                                    <button 
                                        key={key}
                                        onClick={() => { setLayoutMode(key); setIsLayoutDropdownOpen(false); }}
                                        className="flex items-center gap-3 w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                    >
                                        {React.createElement(icon, { className: 'h-5 w-5' })}
                                        <span>{name}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
            
            {recipes.length === 0 ? (
                <div className="text-center py-12">
                    <BookmarkIcon className="h-16 w-16 mx-auto mb-4 text-gray-400" />
                    <h3 className="text-xl font-semibold mb-2 text-gray-600">No saved recipes yet</h3>
                    <p className="text-gray-500">Start by generating and saving your first recipe!</p>
                </div>
            ) : (
                layoutMode.startsWith('grid') ? (
                    <div className={`grid grid-cols-1 ${layoutMode === 'grid-2' ? 'md:grid-cols-2' : 'md:grid-cols-2 lg:grid-cols-3'} gap-8`}>
                        {recipes.map(recipe => (
                            <div 
                                key={recipe.id} 
                                className="bg-white rounded-lg shadow-md overflow-hidden cursor-pointer hover:shadow-lg transition-shadow duration-200 flex flex-col"
                                onClick={() => handleRecipeClick(recipe)}
                            >
                                {viewMode.startsWith('image') && (
                                    <img 
                                        src={recipe.recipe_content.thumbnail_path} 
                                        alt={recipe.recipe_content.title} 
                                        className="w-full h-48 object-cover" 
                                    />
                                )}
                                <div className="p-4 flex flex-col flex-grow">
                                    <h2 className={`font-semibold ${viewMode === 'title_only' ? 'text-xl' : 'text-lg'} mb-2`}>{recipe.recipe_content.title}</h2>
                                    
                                    {viewMode === 'image_description' && (
                                        <p className="text-gray-600 text-sm flex-grow overflow-hidden line-clamp-4">
                                            {recipe.recipe_content.description}
                                        </p>
                                    )}

                                    {viewMode === 'image_ingredients' && (
                                        <ul className="text-sm text-gray-600 list-disc list-inside flex-grow overflow-hidden line-clamp-4">
                                            {recipe.recipe_content.ingredients.slice(0, 4).map((ing, i) => (
                                                <li key={i}>{ing.name}</li>
                                            ))}
                                        </ul>
                                    )}
                                    
                                    <div className="flex items-center text-xs text-gray-400 mt-auto pt-2">
                                        <span>Saved on {new Date(recipe.created_at).toLocaleDateString()}</span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="space-y-2">
                        {recipes.map(recipe => (
                            <div 
                                key={recipe.id}
                                className="bg-white rounded-lg shadow-md p-4 cursor-pointer hover:shadow-lg transition-shadow duration-200"
                                onClick={() => handleRecipeClick(recipe)}
                            >
                                <h2 className="text-xl font-semibold">{recipe.recipe_content.title}</h2>
                            </div>
                        ))}
                    </div>
                )
            )}

            {/* Recipe Modal */}
            {showRecipeModal && selectedRecipe && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
                        <div className="sticky top-0 bg-white border-b border-gray-200 p-6 rounded-t-2xl">
                            <div className="flex justify-between items-start">
                                <h2 className="text-3xl font-bold text-gray-900">{selectedRecipe.recipe_content.title}</h2>
                                <button
                                    onClick={() => setShowRecipeModal(false)}
                                    className="text-gray-400 hover:text-gray-600 transition-colors"
                                >
                                    <XMarkIcon className="h-6 w-6" />
                                </button>
                            </div>
                        </div>

                        <div className="p-6">
                            <div className={`flex ${imageOrientation === 'portrait' ? 'flex-row items-start gap-8' : 'flex-col'}`}>
                                {/* Recipe Image */}
                                {selectedRecipe.recipe_content.thumbnail_path && (
                                    <div className={`${imageOrientation === 'portrait' ? 'w-1/3' : 'w-full'} mb-6`}>
                                        <img 
                                            src={selectedRecipe.recipe_content.thumbnail_path} 
                                            alt={selectedRecipe.recipe_content.title}
                                            className="w-full h-auto object-contain rounded-lg"
                                        />
                                    </div>
                                )}
                                <div className={`${imageOrientation === 'portrait' ? 'w-2/3' : 'w-full'}`}>
                                    {/* Description */}
                                    {selectedRecipe.recipe_content.description && (
                                        <p className="text-gray-600 mt-2 mb-6">{selectedRecipe.recipe_content.description}</p>
                                    )}
                                    
                                    {/* Recipe Info */}
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                                        {selectedRecipe.recipe_content.prep_time && (
                                            <div className="bg-gray-50 p-4 rounded-lg">
                                                <h4 className="font-semibold text-gray-700">Prep Time</h4>
                                                <p className="text-gray-600">{selectedRecipe.recipe_content.prep_time}</p>
                                            </div>
                                        )}
                                        {selectedRecipe.recipe_content.cook_time && (
                                            <div className="bg-gray-50 p-4 rounded-lg">
                                                <h4 className="font-semibold text-gray-700">Cook Time</h4>
                                                <p className="text-gray-600">{selectedRecipe.recipe_content.cook_time}</p>
                                            </div>
                                        )}
                                        {selectedRecipe.recipe_content.servings && (
                                            <div className="bg-gray-50 p-4 rounded-lg">
                                                <h4 className="font-semibold text-gray-700">Servings</h4>
                                                <p className="text-gray-600">{selectedRecipe.recipe_content.servings}</p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Ingredients */}
                            {selectedRecipe.recipe_content.ingredients && selectedRecipe.recipe_content.ingredients.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-4 text-gray-900">Ingredients</h3>
                                    <div className="bg-gray-50 p-6 rounded-lg">
                                        <ul className="space-y-2">
                                            {selectedRecipe.recipe_content.ingredients.map((ingredient, index) => (
                                                <li key={index} className="flex items-start">
                                                    <span className="text-green-600 mr-2">•</span>
                                                    <span className="text-gray-700">
                                                        {typeof ingredient === 'string' 
                                                            ? ingredient 
                                                            : `${ingredient.quantity ? ingredient.quantity + ' ' : ''}${ingredient.name}${ingredient.notes ? ' (' + ingredient.notes + ')' : ''}`
                                                        }
                                                    </span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}

                            {/* Instructions */}
                            {selectedRecipe.recipe_content.instructions && selectedRecipe.recipe_content.instructions.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-4 text-gray-900">Instructions</h3>
                                    <div className="space-y-4">
                                        {selectedRecipe.recipe_content.instructions.map((instruction, index) => (
                                            <div key={index} className="flex">
                                                <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-semibold mr-4">
                                                    {typeof instruction === 'string' ? index + 1 : instruction.step || index + 1}
                                                </div>
                                                <div className="flex-1">
                                                    <p className="text-gray-700 leading-relaxed">
                                                        {typeof instruction === 'string' ? instruction : instruction.description}
                                                    </p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Chef Tips */}
                            {selectedRecipe.recipe_content.chef_tips && selectedRecipe.recipe_content.chef_tips.length > 0 && (
                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-4 text-gray-900">Chef Tips</h3>
                                    <div className="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg">
                                        <ul className="space-y-2">
                                            {selectedRecipe.recipe_content.chef_tips.map((tip, index) => (
                                                <li key={index} className="flex items-start">
                                                    <CheckIcon className="h-5 w-5 text-amber-600 mr-2 mt-0.5 flex-shrink-0" />
                                                    <span className="text-gray-700">{tip}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            )}

                            {/* Nutritional Information */}
                            {selectedRecipe.recipe_content.nutritional_information && (
                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-4 text-gray-900">Nutritional Information (per serving)</h3>
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        {typeof selectedRecipe.recipe_content.nutritional_information === 'object' ? (
                                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                                                <div>
                                                    <p className="text-sm text-gray-500">Calories</p>
                                                    <p className="font-medium">{selectedRecipe.recipe_content.nutritional_information.calories || 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p className="text-sm text-gray-500">Protein</p>
                                                    <p className="font-medium">{selectedRecipe.recipe_content.nutritional_information.protein || 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p className="text-sm text-gray-500">Fat</p>
                                                    <p className="font-medium">{selectedRecipe.recipe_content.nutritional_information.fat || 'N/A'}</p>
                                                </div>
                                                <div>
                                                    <p className="text-sm text-gray-500">Carbs</p>
                                                    <p className="font-medium">{selectedRecipe.recipe_content.nutritional_information.carbohydrates || 'N/A'}</p>
                                                </div>
                                            </div>
                                        ) : (
                                            <p className="text-gray-700">{selectedRecipe.recipe_content.nutritional_information}</p>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Source URL */}
                            {selectedRecipe.source_url && (
                                <div className="mb-8">
                                    <h3 className="text-2xl font-bold mb-4 text-gray-900">Source Video</h3>
                                    <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
                                        <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
                                        <a href={selectedRecipe.source_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                                            {selectedRecipe.source_url}
                                        </a>
                                    </div>
                                </div>
                            )}

                            {/* Action Buttons */}
                            <div className="flex flex-wrap gap-4 pt-6 border-t border-gray-200">
                                <button
                                    onClick={() => handleDownloadPdf(selectedRecipe.recipe_content)}
                                    className="flex items-center gap-2 bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors"
                                >
                                    <ArrowDownTrayIcon className="h-5 w-5" />
                                    <span>Download PDF</span>
                                </button>
                                <button
                                    onClick={() => setShowRecipeModal(false)}
                                    className="flex items-center gap-2 bg-gray-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-gray-700 transition-colors"
                                >
                                    <span>Close</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MyRecipes;