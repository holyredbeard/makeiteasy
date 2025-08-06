import React, { useState, useEffect } from 'react';
import { 
  LinkIcon, 
  XMarkIcon, 
  ArrowDownTrayIcon, 
  BookmarkIcon
} from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8001/api/v1';

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
            {items.map((instruction, index) => (
                <div key={index} className="flex items-start">
                    <div className="flex-shrink-0 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold mr-4">{index + 1}</div>
                    <p className="flex-1 text-gray-700 leading-relaxed pt-1">{instruction}</p>
                </div>
            ))}
        </div>
    </Section>
);

const IngredientSection = ({ items }) => (
     <Section title="Ingredients">
        <div className="bg-gray-50 p-6 rounded-lg">
            <ul className="space-y-2">
                {items.map((item, index) => (
                    <li key={index} className="flex items-start">
                        <span className="text-green-600 mr-3 mt-1 flex-shrink-0">•</span>
                        <span className="text-gray-700">{item}</span>
                    </li>
                ))}
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
                            {image_url && <img src={API_BASE + image_url} alt={title} className="w-full h-auto object-cover rounded-lg shadow-md mb-6" />}
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

// --- Main Page Component ---
const MyRecipes = () => {
    const [recipes, setRecipes] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedRecipe, setSelectedRecipe] = useState(null);

    useEffect(() => {
        const fetchRecipes = async () => {
            try {
                const response = await fetch(`${API_BASE}/recipes`, { credentials: 'include' });
                if (!response.ok) throw new Error('Failed to fetch recipes from the server.');
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

    if (loading) return <div className="text-center p-8">Loading recipes...</div>;
    if (error) return <div className="text-center p-8 text-red-500">Error: {error}</div>;

    return (
        <div className="container mx-auto p-8">
            <h1 className="text-4xl font-bold mb-8 text-gray-800">My Saved Recipes</h1>
            {recipes.length === 0 ? (
                <div className="text-center py-16">
                     <BookmarkIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                     <h3 className="text-xl font-semibold mb-2 text-gray-600">No Saved Recipes Yet</h3>
                     <p className="text-gray-500">Start by generating and saving your first recipe!</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {recipes.map(recipe => (
                        <div key={recipe.id} className="bg-white rounded-lg shadow-lg overflow-hidden cursor-pointer hover:shadow-2xl transition-shadow duration-300 flex flex-col" onClick={() => setSelectedRecipe(recipe)}>
                           <img src={recipe.recipe_content.image_url ? API_BASE + recipe.recipe_content.image_url : 'https://via.placeholder.com/400x300.png?text=No+Image+Found'} alt={recipe.recipe_content.title} className="w-full h-48 object-cover" />
                            <div className="p-5 flex flex-col flex-grow">
                                <h2 className="font-semibold text-lg mb-2 text-gray-800">{recipe.recipe_content.title}</h2>
                                <p className="text-sm text-gray-500 line-clamp-2 flex-grow">{recipe.recipe_content.description}</p>
                                <div className="flex items-center text-xs text-gray-400 mt-4 pt-4 border-t border-gray-100">
                                    <span>Saved on {new Date(recipe.created_at).toLocaleDateString()}</span>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
            <RecipeModal recipe={selectedRecipe} onClose={() => setSelectedRecipe(null)} />
        </div>
    );
};

export default MyRecipes;