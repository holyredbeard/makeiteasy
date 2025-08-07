import React, { useState, useEffect } from 'react';
import { 
  LinkIcon, 
  XMarkIcon, 
  ArrowDownTrayIcon, 
  BookmarkIcon,
  ChevronDownIcon
} from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8001/api/v1';
const STATIC_BASE = 'http://localhost:8001';

// --- Reusable Sub-components ---
const InfoCard = ({ label, value }) => (
    <div className="bg-gray-50 p-4 rounded-lg">
        <h4 className="font-semibold text-sm text-gray-500">{label}</h4>
        <p className="font-medium text-gray-800">{value}</p>
    </div>
);

const Section = ({ title, children }) => (
    <div className="mb-8">
        <h3 className="text-2xl font-bold mb-4 text-gray-900">{title}</h3>
        {children}
    </div>
);

const InstructionSection = ({ items }) => (
    <Section title="Instructions">
        <div className="space-y-4">
            {items.map((instruction, index) => {
                const displayText = typeof instruction === 'string' ? instruction : 
                    instruction.description || instruction.step || `Step ${index + 1}`;
                return (
                    <div key={index} className="flex items-start">
                        <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mr-4">{index + 1}</div>
                        <p className="flex-1 text-gray-700 leading-relaxed pt-1">{displayText}</p>
                    </div>
                );
            })}
        </div>
    </Section>
);

const IngredientSection = ({ items }) => (
     <Section title="Ingredients">
        <div className="bg-gray-50 p-6 rounded-lg">
            <ul className="space-y-2">
                {items.map((item, index) => {
                    const displayText = typeof item === 'string' ? item : 
                        item.name ? `${item.quantity || ''} ${item.name} ${item.notes ? `(${item.notes})` : ''}`.trim() : 
                        'Unknown ingredient';
                    return (
                        <li key={index} className="flex items-start">
                            <span className="text-green-600 mr-3 mt-1 flex-shrink-0">•</span>
                            <span className="text-gray-700">{displayText}</span>
                        </li>
                    );
                })}
            </ul>
        </div>
    </Section>
);

const NutritionSection = ({ data }) => {
    const nutritionItems = [
        { label: "Calories", value: data.calories },
        { label: "Protein", value: data.protein },
        { label: "Fat", value: data.fat },
        { label: "Carbs", value: data.carbohydrates }
    ];
    return (
        <Section title="Nutritional Information">
            <div className="bg-gray-50 p-4 rounded-lg grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                {nutritionItems.map(item => (
                    <div key={item.label}>
                        <p className="text-sm text-gray-500">{item.label}</p>
                        <p className="font-medium text-gray-800">{item.value || 'N/A'}</p>
                    </div>
                ))}
            </div>
        </Section>
    );
}

const SourceSection = ({ url }) => (
    <Section title="Source">
        <div className="bg-gray-50 p-4 rounded-lg flex items-center gap-3">
            <LinkIcon className="h-5 w-5 text-gray-400 flex-shrink-0" />
            <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline truncate">
                {url}
            </a>
        </div>
    </Section>
);

// --- Dropdown Components ---
const Dropdown = ({ label, value, options, onChange, isOpen, onToggle }) => (
    <div className="relative">
        <button
            onClick={onToggle}
            className="flex items-center justify-between w-full px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
            <span>{options.find(opt => opt.value === value)?.label || label}</span>
            <ChevronDownIcon className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
        {isOpen && (
            <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg">
                {options.map((option) => (
                    <button
                        key={option.value}
                        onClick={() => {
                            onChange(option.value);
                            onToggle();
                        }}
                        className={`block w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ${
                            value === option.value ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                        }`}
                    >
                        {option.label}
                    </button>
                ))}
            </div>
        )}
    </div>
);

// --- Main Modal Component ---
const RecipeModal = ({ recipe, onClose }) => {
    if (!recipe) return null;
    
    const {
        title, description, ingredients, instructions, image_url,
        prep_time, cook_time, servings, nutritional_information
    } = recipe.recipe_content;
    
    const { source_url } = recipe;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4 transition-opacity duration-300">
            <div className="bg-white rounded-2xl max-w-4xl w-full max-h-[90vh] flex flex-col shadow-2xl">
                {/* Header */}
                <div className="p-5 border-b border-gray-200">
                    <div className="flex justify-between items-start">
                        <h2 className="text-3xl font-bold text-gray-900">{title || 'Untitled Recipe'}</h2>
                        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><XMarkIcon className="h-7 w-7" /></button>
                    </div>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto">
                    <div className="flex flex-col md:flex-row gap-8">
                        {/* Left Column */}
                        <div className="md:w-1/3">
                            {image_url && <img 
                                src={image_url.startsWith('http') ? image_url : STATIC_BASE + image_url}
                                alt={title} 
                                className="w-full h-auto object-cover rounded-lg shadow-md mb-6" 
                                onError={(e) => { 
                                    console.log('Modal image failed to load:', e.target.src);
                                    e.target.style.display = 'none'; 
                                }}
                                onLoad={(e) => {
                                    console.log('Modal image loaded successfully:', e.target.src);
                                }}
                            />}
                            <div className="space-y-4">
                                {servings && <InfoCard label="Servings" value={servings} />}
                                {prep_time && <InfoCard label="Prep Time" value={prep_time} />}
                                {cook_time && <InfoCard label="Cook Time" value={cook_time} />}
                            </div>
                        </div>
                        {/* Right Column */}
                        <div className="md:w-2/3">
                            {description && <Section title="Description"><p className="text-gray-700 leading-relaxed">{description}</p></Section>}
                            {ingredients?.length > 0 && <IngredientSection items={ingredients} />}
                            {instructions?.length > 0 && <InstructionSection items={instructions} />}
                            {nutritional_information && <NutritionSection data={nutritional_information} />}
                            {source_url && <SourceSection url={source_url} />}
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="p-5 border-t border-gray-200 bg-gray-50 rounded-b-2xl mt-auto">
                    <button className="flex items-center gap-2 bg-blue-600 text-white font-semibold py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors">
                        <ArrowDownTrayIcon className="h-5 w-5" /><span>Download PDF</span>
                    </button>
                </div>
            </div>
        </div>
    );
};

// --- Recipe Card Component ---
const RecipeCard = ({ recipe, viewMode, onClick }) => {
    const { title, description, image_url, ingredients } = recipe.recipe_content;
    
    const renderContent = () => {
        switch (viewMode) {
            case 'title_only':
                return (
                    <div className="p-5">
                        <h2 className="font-semibold text-lg text-gray-800">{title}</h2>
                    </div>
                );
            case 'title_image':
                return (
                    <>
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? image_url : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg text-gray-800">{title}</h2>
                        </div>
                    </>
                );
            case 'title_image_description':
                return (
                    <>
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? image_url : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg mb-2 text-gray-800">{title}</h2>
                            <p className="text-sm text-gray-500 line-clamp-2">{description}</p>
                        </div>
                    </>
                );
            case 'title_image_ingredients':
                return (
                    <>
                        <img 
                            src={image_url ? (image_url.startsWith('http') ? image_url : STATIC_BASE + image_url) : 'https://placehold.co/400x300/EEE/31343C?text=No+Image'} 
                            alt={title} 
                            className="w-full h-48 object-cover" 
                            onError={(e) => { e.target.src = 'https://placehold.co/400x300/EEE/31343C?text=No+Image'; }}
                        />
                        <div className="p-5">
                            <h2 className="font-semibold text-lg mb-2 text-gray-800">{title}</h2>
                            {ingredients && ingredients.length > 0 && (
                                <div className="text-sm text-gray-600">
                                    <p className="font-medium mb-1">Ingredients:</p>
                                    <ul className="space-y-1">
                                        {ingredients.slice(0, 3).map((ingredient, index) => (
                                            <li key={index} className="flex items-start">
                                                <span className="text-green-600 mr-2 mt-1 flex-shrink-0">•</span>
                                                <span className="text-gray-700">
                                                    {typeof ingredient === 'string' ? ingredient : 
                                                     ingredient.name ? `${ingredient.quantity || ''} ${ingredient.name}`.trim() : 
                                                     'Unknown ingredient'}
                                                </span>
                                            </li>
                                        ))}
                                        {ingredients.length > 3 && (
                                            <li className="text-gray-500 italic">... and {ingredients.length - 3} more</li>
                                        )}
                                    </ul>
                                </div>
                            )}
                        </div>
                    </>
                );
            default:
                return null;
        }
    };

    return (
        <div 
            className="bg-white rounded-lg shadow-lg overflow-hidden cursor-pointer hover:shadow-2xl transition-shadow duration-300 flex flex-col" 
            onClick={onClick}
        >
            {renderContent()}
            <div className="px-5 pb-5 mt-auto">
                <div className="flex items-center text-xs text-gray-400 pt-4 border-t border-gray-100">
                    <span>Saved on {new Date(recipe.created_at).toLocaleDateString()}</span>
                </div>
            </div>
        </div>
    );
};

// --- Main Page Component ---
const MyRecipes = () => {
    const [recipes, setRecipes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedRecipe, setSelectedRecipe] = useState(null);
    
    // Dropdown states
    const [viewMode, setViewMode] = useState('title_image_description');
    const [layoutMode, setLayoutMode] = useState('grid_2');
    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [isLayoutDropdownOpen, setIsLayoutDropdownOpen] = useState(false);

    // Dropdown options
    const viewOptions = [
        { value: 'title_only', label: 'Bara titel' },
        { value: 'title_image', label: 'Titel + bild' },
        { value: 'title_image_description', label: 'Titel + bild + description' },
        { value: 'title_image_ingredients', label: 'Titel + bild + ingredients' }
    ];

    const layoutOptions = [
        { value: 'grid_2', label: 'Cols (2 bilder per col)' },
        { value: 'grid_3', label: 'Cols (3 bilder per col)' },
        { value: 'list', label: 'Lista (bara titel)' }
    ];

    useEffect(() => {
        const fetchRecipes = async () => {
            try {
                const response = await fetch(`${API_BASE}/recipes`, { credentials: 'include' });
                if (!response.ok) throw new Error('Failed to fetch recipes from the server.');
                const data = await response.json();
                console.log('Fetched recipes:', data);
                setRecipes(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchRecipes();
    }, []);

    const getGridClasses = () => {
        switch (layoutMode) {
            case 'grid_2':
                return 'grid-cols-1 md:grid-cols-2';
            case 'grid_3':
                return 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3';
            case 'list':
                return 'grid-cols-1';
            default:
                return 'grid-cols-1 md:grid-cols-2';
        }
    };

    if (loading) return <div className="text-center p-8">Loading recipes...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Error: {error}</div>;

    return (
        <div className="container mx-auto p-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8 gap-4">
                <h1 className="text-4xl font-bold text-gray-800">My Saved Recipes</h1>
                
                {/* Dropdown Controls */}
                <div className="flex flex-col sm:flex-row gap-4">
                    {/* View Mode Dropdown */}
                    <div className="w-full sm:w-64">
                        <label className="block text-sm font-medium text-gray-700 mb-2">View Mode</label>
                        <Dropdown
                            label="Select view mode"
                            value={viewMode}
                            options={viewOptions}
                            onChange={setViewMode}
                            isOpen={isDropdownOpen}
                            onToggle={() => setIsDropdownOpen(!isDropdownOpen)}
                        />
                    </div>
                    
                    {/* Layout Mode Dropdown */}
                    <div className="w-full sm:w-64">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Layout Mode</label>
                        <Dropdown
                            label="Select layout mode"
                            value={layoutMode}
                            options={layoutOptions}
                            onChange={setLayoutMode}
                            isOpen={isLayoutDropdownOpen}
                            onToggle={() => setIsLayoutDropdownOpen(!isLayoutDropdownOpen)}
                        />
                    </div>
                </div>
            </div>

            {recipes.length === 0 ? (
                <div className="text-center py-16">
                     <BookmarkIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                     <h3 className="text-xl font-semibold mb-2 text-gray-600">No Saved Recipes Yet</h3>
                     <p className="text-gray-500">Start by generating and saving your first recipe!</p>
                </div>
            ) : (
                <div className={`grid ${getGridClasses()} gap-8`}>
                    {recipes.map(recipe => (
                        <RecipeCard
                            key={recipe.id}
                            recipe={recipe}
                            viewMode={viewMode}
                            onClick={() => setSelectedRecipe(recipe)}
                        />
                    ))}
                </div>
            )}
            <RecipeModal recipe={selectedRecipe} onClose={() => setSelectedRecipe(null)} />
        </div>
    );
};

export default MyRecipes;