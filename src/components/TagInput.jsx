import React, { useMemo, useState } from 'react';

const SUGGESTIONS = [
  // Basic dishes
  'pasta','soup','salad','stirfry','baked','grilled','fried','breakfast','lunch','dinner','dessert',
  'pizza','burger','tacos','sushi','curry','stew','sandwich','wrap','casserole','pie','quiche','omelette',
  'pancake','waffle','crepe','dumpling','skewer','flatbread','bowl','onepot','gratin','stewpot',
  
  // Cuisines
  'italian','mexican','indian','thai','japanese','swedish','chinese','french','greek','turkish',
  'mediterranean','vietnamese','korean','moroccan','american','british','german','spanish','middleeastern',
  
  // Dietary
  'vegan','vegetarian','pescatarian','glutenfree','dairyfree','lowcarb','highprotein','keto','paleo','sugarfree',
  
  // Themes
  'quick','easy','healthy','zesty','seafood','fastfood','spicy','sweet','savory','comfortfood',
  'kidfriendly','fingerfood','mealprep','budget','festive','seasonal','holiday','summer','winter','autumn','spring',
  
  // Meals
  'brunch','snack','side','appetizer','main','drink','cocktail','mocktail',
  
  // Cooking methods
  'roasted','boiled','steamed','raw','poached','braised','slowcooked','barbecue','smoked','blanched','seared',
  
  // Proteins
  'chicken','eggs','cheese','beef','pork','lamb','turkey','duck','fish','shrimp','squid','octopus','steak',
  'bacon','sausage','ham','salmon','tuna','cod','halibut','mackerel','sardines','anchovies','crab','lobster',
  'mussel','clam','oyster','scallop','calamari','tilapia','trout','bass','snapper','grouper','swordfish',
  
  // Dairy & Eggs
  'milk','yogurt','butter','cream','sourcream','cottagecheese','ricotta','mozzarella','cheddar','parmesan',
  'feta','gouda','brie','bluecheese','swiss','provolone','havarti','manchego','pecorino','asiago',
  
  // Fruits & Vegetables
  'fruits','apple','banana','orange','lemon','lime','grape','strawberry','blueberry','raspberry','blackberry',
  'peach','pear','plum','apricot','cherry','pineapple','mango','kiwi','avocado','coconut','watermelon',
  'cantaloupe','honeydew','papaya','guava','fig','date','prune','raisin','cranberry','pomegranate',
  'carrot','broccoli','cauliflower','spinach','kale','lettuce','cabbage','brusselsprouts','asparagus',
  'zucchini','eggplant','tomato','potato','sweetpotato','onion','garlic','ginger','mushroom','bellpepper',
  'jalapeno','cucumber','celery','beet','turnip','radish','parsnip','rutabaga','artichoke','leek',
  'shallot','scallion','chive','basil','oregano','thyme','rosemary','sage','mint','cilantro','parsley',
  'dill','bayleaf','tarragon','marjoram','chamomile','lavender','lemongrass','turmeric','cinnamon',
  'nutmeg','clove','cardamom','cumin','coriander','paprika','saffron','vanilla','almond','walnut',
  'pecan','cashew','pistachio','hazelnut','macadamia','peanut','sunflowerseed','pumpkinseed','sesame',
  'chia','flax','quinoa','rice','brownrice','wildrice','basmati','jasmine','arborio','couscous',
  'bulgur','farro','barley','oats','wheat','rye','corn','polenta','grits','millet','sorghum',
  
  // Beverages
  'wine','beer','coffee','tea','juice','smoothie','milkshake','cocktail','mocktail','soda','water',
  'whiskey','vodka','gin','rum','tequila','brandy','cognac','sherry','port','champagne','prosecco',
  'cider','mead','sake','soju','baijiu','absinthe','amaretto','kahlua','baileys','grandmarnier',
  
  // Grains & Breads
  'bread','toast','bagel','croissant','muffin','biscuit','scone','donut','cake','cookie','brownie',
  'pie','tart','pastry','danish','strudel','eclair','cannoli','tiramisu','cheesecake','icecream',
  'gelato','sorbet','pudding','custard','flan','cremebrulee','mousse','souffle','trifle','parfait',
  
  // Legumes & Nuts
  'bean','lentil','chickpea','blackbean','kidneybean','pintobean','navybean','limabean','fava',
  'splitpea','blackeyedpea','soybean','edamame','tofu','tempeh','seitan','quorn','texturedvegetableprotein',
  
  // Oils & Fats
  'oliveoil','coconutoil','avocadooil','sesameoil','walnutoil','almondoil','peanutoil','sunfloweroil',
  'canolaoil','vegetableoil','butter','ghee','lard','tallow','margarine','shortening',
  
  // Sweeteners
  'sugar','honey','maple','agave','stevia','splenda','aspartame','saccharin','xylitol','erythritol',
  'monkfruit','datesugar','coconutsugar','brownsugar','powderedsugar','turbinado','demerara','muscovado',
  
  // Sauces & Condiments
  'ketchup','mustard','mayo','hot sauce','soy sauce','worcestershire','fish sauce','oyster sauce',
  'hoisin','teriyaki','barbecue','ranch','blue cheese','thousand island','caesar','vinaigrette',
  'pesto','hummus','guacamole','salsa','chutney','relish','pickle','olive','caper','anchovy',
  'truffle','miso','tahini','peanut butter','almond butter','cashew butter','sunflower butter',
  
  // Spices & Herbs
  'salt','pepper','paprika','cayenne','chili','cumin','coriander','turmeric','ginger','garlic',
  'onion','basil','oregano','thyme','rosemary','sage','mint','cilantro','parsley','dill',
  'bay leaf','tarragon','marjoram','chamomile','lavender','lemongrass','cardamom','cinnamon',
  'nutmeg','clove','allspice','star anise','fennel','caraway','poppy','sesame','chia','flax',
  
  // Special categories
  'organic','local','seasonal','fresh','frozen','canned','dried','fermented','pickled','smoked',
  'aged','artisan','homemade','traditional','fusion','modern','classic','gourmet','premium','budget',
  'quick','easy','complex','advanced','beginner','intermediate','expert','chef','homecook'
];

export default function TagInput({ tags, setTags, placeholder = 'Type to add a tag...', required = false, onValidityChange }) {
  const [input, setInput] = useState('');
  const [open, setOpen] = useState(false);
  const normalized = useMemo(()=>String(input).trim().toLowerCase(), [input]);
  const matches = useMemo(()=>{
    if (!normalized) return [];
    return SUGGESTIONS.filter(s => s.startsWith(normalized) && !(tags||[]).some(t => (t.label||t)===s)).slice(0,8);
  }, [normalized, tags]);

  const add = (raw) => {
    const t = String(raw || '').trim().toLowerCase().replace(/\s+/g,'');
    if (!t) return;
    if (!tags.find(x => (x.label||x) === t)) {
      const newTags = [...(tags||[]), { label: t }];
      setTags(newTags);
    }
    setInput('');
  };

  const remove = (val) => setTags((tags||[]).filter(x => (x.label||x) !== val));

  const isValid = (tags || []).length > 0 || !required;
  if (typeof onValidityChange === 'function') {
    try { onValidityChange(isValid); } catch {}
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        {(tags||[]).map((t, idx) => {
          const label = t.label || t;
          const labelLower = label.toLowerCase();
          let tagClass = 'bg-amber-50 text-amber-800 border-amber-200';
          
          // Apply specific styling for known tags
          if (labelLower === 'vegan') tagClass = 'bg-emerald-600 text-white border-emerald-600';
          else if (labelLower === 'vegetarian') tagClass = 'bg-lime-600 text-white border-lime-600';
          else if (labelLower === 'pescatarian') tagClass = 'bg-sky-600 text-white border-sky-600';
          else if (labelLower === 'zesty') tagClass = 'bg-yellow-500 text-white border-yellow-500';
          else if (labelLower === 'seafood') tagClass = 'bg-blue-600 text-white border-blue-600';
          else if (labelLower === 'fastfood') tagClass = 'bg-orange-500 text-white border-orange-500';
          else if (labelLower === 'spicy') tagClass = 'bg-red-600 text-white border-red-600';
          else if (labelLower === 'chicken') tagClass = 'bg-amber-600 text-white border-amber-600';
          else if (labelLower === 'eggs') tagClass = 'bg-yellow-400 text-white border-yellow-400';
          else if (labelLower === 'cheese') tagClass = 'bg-yellow-300 text-gray-800 border-yellow-300';
          else if (labelLower === 'fruits') tagClass = 'bg-pink-500 text-white border-pink-500';
          else if (labelLower === 'wine') tagClass = 'bg-purple-600 text-white border-purple-600';
          else if (labelLower === 'pasta') tagClass = 'bg-orange-600 text-white border-orange-600';
          else if (labelLower === 'beef' || labelLower === 'steak') tagClass = 'bg-red-700 text-white border-red-700';
          else if (labelLower === 'pork' || labelLower === 'bacon' || labelLower === 'ham') tagClass = 'bg-pink-600 text-white border-pink-600';
          else if (labelLower === 'fish' || labelLower === 'salmon' || labelLower === 'tuna') tagClass = 'bg-blue-500 text-white border-blue-500';
          else if (labelLower === 'shrimp' || labelLower === 'crab' || labelLower === 'lobster') tagClass = 'bg-orange-400 text-white border-orange-400';
          else if (labelLower === 'squid' || labelLower === 'octopus' || labelLower === 'calamari') tagClass = 'bg-purple-500 text-white border-purple-500';
          else if (labelLower === 'apple' || labelLower === 'banana' || labelLower === 'orange') tagClass = 'bg-green-500 text-white border-green-500';
          else if (labelLower === 'carrot' || labelLower === 'broccoli' || labelLower === 'spinach') tagClass = 'bg-green-600 text-white border-green-600';
          else if (labelLower === 'tomato' || labelLower === 'bellpepper' || labelLower === 'jalapeno') tagClass = 'bg-red-500 text-white border-red-500';
          else if (labelLower === 'potato' || labelLower === 'sweetpotato') tagClass = 'bg-amber-700 text-white border-amber-700';
          else if (labelLower === 'onion' || labelLower === 'garlic') tagClass = 'bg-purple-600 text-white border-purple-600';
          else if (labelLower === 'bread' || labelLower === 'toast' || labelLower === 'bagel') tagClass = 'bg-amber-500 text-white border-amber-500';
          else if (labelLower === 'cake' || labelLower === 'cookie' || labelLower === 'dessert') tagClass = 'bg-pink-400 text-white border-pink-400';
          else if (labelLower === 'coffee' || labelLower === 'tea') tagClass = 'bg-amber-800 text-white border-amber-800';
          else if (labelLower === 'beer' || labelLower === 'whiskey' || labelLower === 'vodka') tagClass = 'bg-amber-800 text-white border-amber-800';
          
          return (
            <span key={idx} className={`inline-flex items-center px-2 py-1 rounded-full text-xs border ${tagClass}`}>
              {labelLower === 'vegan' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'vegetarian' && <i className="fa-solid fa-carrot mr-1"></i>}
              {labelLower === 'zesty' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'pescatarian' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'seafood' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'fastfood' && <i className="fa-solid fa-burger mr-1"></i>}
              {labelLower === 'spicy' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'eggs' && <i className="fa-solid fa-egg mr-1"></i>}
              {labelLower === 'cheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'fruits' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'wine' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'pasta' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'beef' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'steak' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'pork' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'bacon' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'ham' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'fish' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'salmon' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'tuna' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'shrimp' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'crab' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'lobster' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'squid' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'octopus' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'calamari' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'apple' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'banana' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'orange' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'carrot' && <i className="fa-solid fa-carrot mr-1"></i>}
              {labelLower === 'broccoli' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'spinach' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'tomato' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'bellpepper' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'jalapeno' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'potato' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'sweetpotato' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'onion' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'garlic' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'bread' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'toast' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'bagel' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'cake' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'cookie' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'dessert' && <i className="fa-solid fa-ice-cream mr-1"></i>}
              {labelLower === 'coffee' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'tea' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'beer' && <i className="fa-solid fa-beer mr-1"></i>}
              {labelLower === 'whiskey' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'vodka' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'lamb' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'turkey' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'duck' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'cod' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'halibut' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'mackerel' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'sardines' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'anchovies' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'mussel' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'clam' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'oyster' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'scallop' && <i className="fa-solid fa-shrimp mr-1"></i>}
              {labelLower === 'tilapia' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'trout' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'bass' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'snapper' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'grouper' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'swordfish' && <i className="fa-solid fa-fish mr-1"></i>}
              {labelLower === 'milk' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'yogurt' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'butter' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'cream' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'sourcream' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'cottagecheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'ricotta' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'mozzarella' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'cheddar' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'parmesan' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'feta' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'gouda' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'brie' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'bluecheese' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'swiss' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'provolone' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'havarti' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'manchego' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'pecorino' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'asiago' && <i className="fa-solid fa-cheese mr-1"></i>}
              {labelLower === 'lemon' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'lime' && <i className="fa-solid fa-lemon mr-1"></i>}
              {labelLower === 'grape' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'strawberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'blueberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'raspberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'blackberry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'peach' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'pear' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'plum' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'apricot' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'cherry' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'pineapple' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'mango' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'kiwi' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'avocado' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'coconut' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'watermelon' && <i className="fa-solid fa-apple-whole mr-1"></i>}
              {labelLower === 'lettuce' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'kale' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cabbage' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cauliflower' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'zucchini' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'cucumber' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'eggplant' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'mushroom' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'corn' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'peas' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'beans' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'lentils' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'chickpeas' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'quinoa' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'rice' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'pasta' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'noodle' && <i className="fa-solid fa-bacon mr-1"></i>}
              {labelLower === 'flour' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'sugar' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'honey' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'maple' && <i className="fa-solid fa-cookie mr-1"></i>}
              {labelLower === 'oliveoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'vegetableoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'coconutoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'sesameoil' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'soysauce' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'vinegar' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'mustard' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'ketchup' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'mayonnaise' && <i className="fa-solid fa-bottle-water mr-1"></i>}
              {labelLower === 'hot sauce' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'sriracha' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'salt' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'pepper' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'basil' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'oregano' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'thyme' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'rosemary' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'sage' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'parsley' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cilantro' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'dill' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'mint' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'cumin' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'coriander' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'turmeric' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'ginger' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'cinnamon' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'nutmeg' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'paprika' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'chili' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'cayenne' && <i className="fa-solid fa-pepper-hot mr-1"></i>}
              {labelLower === 'italian' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'mexican' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'indian' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'thai' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'japanese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'swedish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'chinese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'french' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'greek' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'turkish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'mediterranean' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'vietnamese' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'korean' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'moroccan' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'american' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'british' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'german' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'spanish' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'middleeastern' && <i className="fa-solid fa-flag mr-1"></i>}
              {labelLower === 'glutenfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'dairyfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'lowcarb' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'highprotein' && <i className="fa-solid fa-drumstick-bite mr-1"></i>}
              {labelLower === 'keto' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'paleo' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'sugarfree' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'quick' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'easy' && <i className="fa-solid fa-thumbs-up mr-1"></i>}
              {labelLower === 'healthy' && <i className="fa-solid fa-heart mr-1"></i>}
              {labelLower === 'savory' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'comfortfood' && <i className="fa-solid fa-heart mr-1"></i>}
              {labelLower === 'kidfriendly' && <i className="fa-solid fa-child mr-1"></i>}
              {labelLower === 'fingerfood' && <i className="fa-solid fa-hand mr-1"></i>}
              {labelLower === 'mealprep' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'budget' && <i className="fa-solid fa-dollar-sign mr-1"></i>}
              {labelLower === 'festive' && <i className="fa-solid fa-star mr-1"></i>}
              {labelLower === 'seasonal' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'holiday' && <i className="fa-solid fa-calendar mr-1"></i>}
              {labelLower === 'summer' && <i className="fa-solid fa-sun mr-1"></i>}
              {labelLower === 'winter' && <i className="fa-solid fa-snowflake mr-1"></i>}
              {labelLower === 'autumn' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'spring' && <i className="fa-solid fa-seedling mr-1"></i>}
              {labelLower === 'brunch' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'snack' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'side' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'appetizer' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'main' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'drink' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'cocktail' && <i className="fa-solid fa-wine-bottle mr-1"></i>}
              {labelLower === 'mocktail' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'roasted' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'boiled' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'steamed' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'raw' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'poached' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'braised' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'slowcooked' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'barbecue' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'smoked' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'blanched' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'seared' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'soup' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'salad' && <i className="fa-solid fa-leaf mr-1"></i>}
              {labelLower === 'stirfry' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'baked' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'grilled' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'fried' && <i className="fa-solid fa-fire mr-1"></i>}
              {labelLower === 'breakfast' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'lunch' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'dinner' && <i className="fa-solid fa-clock mr-1"></i>}
              {labelLower === 'pizza' && <i className="fa-solid fa-pizza-slice mr-1"></i>}
              {labelLower === 'burger' && <i className="fa-solid fa-burger mr-1"></i>}
              {labelLower === 'tacos' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'sushi' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'curry' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'stew' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'sandwich' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'wrap' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'casserole' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'pie' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'quiche' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'omelette' && <i className="fa-solid fa-egg mr-1"></i>}
              {labelLower === 'pancake' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'waffle' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'crepe' && <i className="fa-solid fa-birthday-cake mr-1"></i>}
              {labelLower === 'dumpling' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'skewer' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'flatbread' && <i className="fa-solid fa-bread-slice mr-1"></i>}
              {labelLower === 'bowl' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'onepot' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              {labelLower === 'gratin' && <i className="fa-solid fa-utensils mr-1"></i>}
              {labelLower === 'stewpot' && <i className="fa-solid fa-mug-hot mr-1"></i>}
              <span className="font-medium">{label.charAt(0).toUpperCase() + label.slice(1)}</span>
              <button onClick={() => remove(label)} className="ml-1 opacity-70 hover:opacity-100">×</button>
            </span>
          );
        })}
      </div>
      <input
        value={input}
        onChange={(e)=>{ setInput(e.target.value); setOpen(true); }}
        onKeyDown={(e)=>{ if (e.key==='Enter'){ e.preventDefault(); add(input); }}}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />
      {open && matches.length > 0 && (
        <div className="mt-1 border border-gray-200 rounded-2xl bg-white/90 backdrop-blur shadow-[4px_4px_0_rgba(0,0,0,0.06)] hover:shadow-[6px_6px_0_rgba(0,0,0,0.08)] hover:-translate-y-0.5 transition-transform transition-shadow duration-200 ease-out divide-y">
          {matches.map(m => (
            <button key={m} type="button" onClick={()=>{ add(m); setOpen(false); }} className="w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center">
              {m.toLowerCase() === 'vegan' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'vegetarian' && <i className="fa-solid fa-carrot mr-2 text-lime-600"></i>}
              {m.toLowerCase() === 'zesty' && <i className="fa-solid fa-lemon mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'pescatarian' && <i className="fa-solid fa-fish mr-2 text-sky-600"></i>}
              {m.toLowerCase() === 'seafood' && <i className="fa-solid fa-shrimp mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'fastfood' && <i className="fa-solid fa-burger mr-2 text-orange-500"></i>}
              {m.toLowerCase() === 'spicy' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'chicken' && <i className="fa-solid fa-drumstick-bite mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'eggs' && <i className="fa-solid fa-egg mr-2 text-yellow-400"></i>}
              {m.toLowerCase() === 'cheese' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'fruits' && <i className="fa-solid fa-apple-whole mr-2 text-pink-500"></i>}
              {m.toLowerCase() === 'wine' && <i className="fa-solid fa-wine-bottle mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'pasta' && <i className="fa-solid fa-bacon mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'beef' && <i className="fa-solid fa-drumstick-bite mr-2 text-red-700"></i>}
              {m.toLowerCase() === 'steak' && <i className="fa-solid fa-drumstick-bite mr-2 text-red-700"></i>}
              {m.toLowerCase() === 'pork' && <i className="fa-solid fa-bacon mr-2 text-pink-600"></i>}
              {m.toLowerCase() === 'bacon' && <i className="fa-solid fa-bacon mr-2 text-pink-600"></i>}
              {m.toLowerCase() === 'ham' && <i className="fa-solid fa-bacon mr-2 text-pink-600"></i>}
              {m.toLowerCase() === 'fish' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'salmon' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'tuna' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'shrimp' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'crab' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'lobster' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'squid' && <i className="fa-solid fa-fish mr-2 text-purple-500"></i>}
              {m.toLowerCase() === 'octopus' && <i className="fa-solid fa-fish mr-2 text-purple-500"></i>}
              {m.toLowerCase() === 'calamari' && <i className="fa-solid fa-fish mr-2 text-purple-500"></i>}
              {m.toLowerCase() === 'apple' && <i className="fa-solid fa-apple-whole mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'banana' && <i className="fa-solid fa-apple-whole mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'orange' && <i className="fa-solid fa-apple-whole mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'carrot' && <i className="fa-solid fa-carrot mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'broccoli' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'spinach' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'tomato' && <i className="fa-solid fa-apple-whole mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'bellpepper' && <i className="fa-solid fa-pepper-hot mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'jalapeno' && <i className="fa-solid fa-pepper-hot mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'potato' && <i className="fa-solid fa-seedling mr-2 text-amber-700"></i>}
              {m.toLowerCase() === 'sweetpotato' && <i className="fa-solid fa-seedling mr-2 text-amber-700"></i>}
              {m.toLowerCase() === 'onion' && <i className="fa-solid fa-seedling mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'garlic' && <i className="fa-solid fa-seedling mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'bread' && <i className="fa-solid fa-bread-slice mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'toast' && <i className="fa-solid fa-bread-slice mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'bagel' && <i className="fa-solid fa-bread-slice mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'cake' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'cookie' && <i className="fa-solid fa-cookie mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'dessert' && <i className="fa-solid fa-ice-cream mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'coffee' && <i className="fa-solid fa-mug-hot mr-2 text-amber-800"></i>}
              {m.toLowerCase() === 'tea' && <i className="fa-solid fa-mug-hot mr-2 text-amber-800"></i>}
              {m.toLowerCase() === 'beer' && <i className="fa-solid fa-beer mr-2 text-amber-800"></i>}
              {m.toLowerCase() === 'whiskey' && <i className="fa-solid fa-wine-bottle mr-2 text-amber-800"></i>}
              {m.toLowerCase() === 'vodka' && <i className="fa-solid fa-wine-bottle mr-2 text-amber-800"></i>}
              {m.toLowerCase() === 'lamb' && <i className="fa-solid fa-drumstick-bite mr-2 text-red-700"></i>}
              {m.toLowerCase() === 'turkey' && <i className="fa-solid fa-drumstick-bite mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'duck' && <i className="fa-solid fa-drumstick-bite mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'cod' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'halibut' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'mackerel' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'sardines' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'anchovies' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'mussel' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'clam' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'oyster' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'scallop' && <i className="fa-solid fa-shrimp mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'tilapia' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'trout' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'bass' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'snapper' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'grouper' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'swordfish' && <i className="fa-solid fa-fish mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'milk' && <i className="fa-solid fa-mug-hot mr-2 text-blue-400"></i>}
              {m.toLowerCase() === 'yogurt' && <i className="fa-solid fa-mug-hot mr-2 text-blue-400"></i>}
              {m.toLowerCase() === 'butter' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'cream' && <i className="fa-solid fa-mug-hot mr-2 text-blue-400"></i>}
              {m.toLowerCase() === 'sourcream' && <i className="fa-solid fa-mug-hot mr-2 text-blue-400"></i>}
              {m.toLowerCase() === 'cottagecheese' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'ricotta' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'mozzarella' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'cheddar' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'parmesan' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'feta' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'gouda' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'brie' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'bluecheese' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'swiss' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'provolone' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'havarti' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'manchego' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'pecorino' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'asiago' && <i className="fa-solid fa-cheese mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'lemon' && <i className="fa-solid fa-lemon mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'lime' && <i className="fa-solid fa-lemon mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'grape' && <i className="fa-solid fa-apple-whole mr-2 text-purple-500"></i>}
              {m.toLowerCase() === 'strawberry' && <i className="fa-solid fa-apple-whole mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'blueberry' && <i className="fa-solid fa-apple-whole mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'raspberry' && <i className="fa-solid fa-apple-whole mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'blackberry' && <i className="fa-solid fa-apple-whole mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'peach' && <i className="fa-solid fa-apple-whole mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'pear' && <i className="fa-solid fa-apple-whole mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'plum' && <i className="fa-solid fa-apple-whole mr-2 text-purple-500"></i>}
              {m.toLowerCase() === 'apricot' && <i className="fa-solid fa-apple-whole mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'cherry' && <i className="fa-solid fa-apple-whole mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'pineapple' && <i className="fa-solid fa-apple-whole mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'mango' && <i className="fa-solid fa-apple-whole mr-2 text-orange-400"></i>}
              {m.toLowerCase() === 'kiwi' && <i className="fa-solid fa-apple-whole mr-2 text-green-500"></i>}
              {m.toLowerCase() === 'avocado' && <i className="fa-solid fa-apple-whole mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'coconut' && <i className="fa-solid fa-apple-whole mr-2 text-brown-500"></i>}
              {m.toLowerCase() === 'watermelon' && <i className="fa-solid fa-apple-whole mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'lettuce' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'kale' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'cabbage' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'cauliflower' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'zucchini' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'cucumber' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'eggplant' && <i className="fa-solid fa-seedling mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'mushroom' && <i className="fa-solid fa-seedling mr-2 text-brown-600"></i>}
              {m.toLowerCase() === 'corn' && <i className="fa-solid fa-seedling mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'peas' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'beans' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'lentils' && <i className="fa-solid fa-seedling mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'chickpeas' && <i className="fa-solid fa-seedling mr-2 text-yellow-600"></i>}
              {m.toLowerCase() === 'quinoa' && <i className="fa-solid fa-seedling mr-2 text-yellow-600"></i>}
              {m.toLowerCase() === 'rice' && <i className="fa-solid fa-seedling mr-2 text-white-600"></i>}
              {m.toLowerCase() === 'pasta' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'noodle' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'flour' && <i className="fa-solid fa-bread-slice mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'sugar' && <i className="fa-solid fa-cookie mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'honey' && <i className="fa-solid fa-cookie mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'maple' && <i className="fa-solid fa-cookie mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'oliveoil' && <i className="fa-solid fa-bottle-water mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'vegetableoil' && <i className="fa-solid fa-bottle-water mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'coconutoil' && <i className="fa-solid fa-bottle-water mr-2 text-white-500"></i>}
              {m.toLowerCase() === 'sesameoil' && <i className="fa-solid fa-bottle-water mr-2 text-amber-600"></i>}
              {m.toLowerCase() === 'soysauce' && <i className="fa-solid fa-bottle-water mr-2 text-brown-600"></i>}
              {m.toLowerCase() === 'vinegar' && <i className="fa-solid fa-bottle-water mr-2 text-gray-500"></i>}
              {m.toLowerCase() === 'mustard' && <i className="fa-solid fa-bottle-water mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'ketchup' && <i className="fa-solid fa-bottle-water mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'mayonnaise' && <i className="fa-solid fa-bottle-water mr-2 text-yellow-300"></i>}
              {m.toLowerCase() === 'hot sauce' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'sriracha' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'salt' && <i className="fa-solid fa-pepper-hot mr-2 text-gray-500"></i>}
              {m.toLowerCase() === 'pepper' && <i className="fa-solid fa-pepper-hot mr-2 text-black-500"></i>}
              {m.toLowerCase() === 'basil' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'oregano' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'thyme' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'rosemary' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'sage' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'parsley' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'cilantro' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'dill' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'mint' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'cumin' && <i className="fa-solid fa-seedling mr-2 text-brown-600"></i>}
              {m.toLowerCase() === 'coriander' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'turmeric' && <i className="fa-solid fa-seedling mr-2 text-yellow-600"></i>}
              {m.toLowerCase() === 'ginger' && <i className="fa-solid fa-seedling mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'cinnamon' && <i className="fa-solid fa-seedling mr-2 text-brown-600"></i>}
              {m.toLowerCase() === 'nutmeg' && <i className="fa-solid fa-seedling mr-2 text-brown-600"></i>}
              {m.toLowerCase() === 'paprika' && <i className="fa-solid fa-pepper-hot mr-2 text-red-500"></i>}
              {m.toLowerCase() === 'chili' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'cayenne' && <i className="fa-solid fa-pepper-hot mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'italian' && <i className="fa-solid fa-flag mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'mexican' && <i className="fa-solid fa-flag mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'indian' && <i className="fa-solid fa-flag mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'thai' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'japanese' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'swedish' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'chinese' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'french' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'greek' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'turkish' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'mediterranean' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'vietnamese' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'korean' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'moroccan' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'american' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'british' && <i className="fa-solid fa-flag mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'german' && <i className="fa-solid fa-flag mr-2 text-black-600"></i>}
              {m.toLowerCase() === 'spanish' && <i className="fa-solid fa-flag mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'middleeastern' && <i className="fa-solid fa-flag mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'glutenfree' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'dairyfree' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'lowcarb' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'highprotein' && <i className="fa-solid fa-drumstick-bite mr-2 text-red-700"></i>}
              {m.toLowerCase() === 'keto' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'paleo' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'sugarfree' && <i className="fa-solid fa-leaf mr-2 text-emerald-600"></i>}
              {m.toLowerCase() === 'quick' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'easy' && <i className="fa-solid fa-thumbs-up mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'healthy' && <i className="fa-solid fa-heart mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'savory' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'comfortfood' && <i className="fa-solid fa-heart mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'kidfriendly' && <i className="fa-solid fa-child mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'fingerfood' && <i className="fa-solid fa-hand mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'mealprep' && <i className="fa-solid fa-calendar mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'budget' && <i className="fa-solid fa-dollar-sign mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'festive' && <i className="fa-solid fa-star mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'seasonal' && <i className="fa-solid fa-calendar mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'holiday' && <i className="fa-solid fa-calendar mr-2 text-red-600"></i>}
              {m.toLowerCase() === 'summer' && <i className="fa-solid fa-sun mr-2 text-yellow-500"></i>}
              {m.toLowerCase() === 'winter' && <i className="fa-solid fa-snowflake mr-2 text-blue-500"></i>}
              {m.toLowerCase() === 'autumn' && <i className="fa-solid fa-leaf mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'spring' && <i className="fa-solid fa-seedling mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'brunch' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'snack' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'side' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'appetizer' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'main' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'drink' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'cocktail' && <i className="fa-solid fa-wine-bottle mr-2 text-purple-600"></i>}
              {m.toLowerCase() === 'mocktail' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'roasted' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'boiled' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'steamed' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'raw' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'poached' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'braised' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'slowcooked' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'barbecue' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'smoked' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'blanched' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'seared' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'soup' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'salad' && <i className="fa-solid fa-leaf mr-2 text-green-600"></i>}
              {m.toLowerCase() === 'stirfry' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'baked' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'grilled' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'fried' && <i className="fa-solid fa-fire mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'breakfast' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'lunch' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'dinner' && <i className="fa-solid fa-clock mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'pizza' && <i className="fa-solid fa-pizza-slice mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'burger' && <i className="fa-solid fa-burger mr-2 text-orange-500"></i>}
              {m.toLowerCase() === 'tacos' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'sushi' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'curry' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'stew' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'sandwich' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'wrap' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'casserole' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'pie' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'quiche' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'omelette' && <i className="fa-solid fa-egg mr-2 text-yellow-400"></i>}
              {m.toLowerCase() === 'pancake' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'waffle' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'crepe' && <i className="fa-solid fa-birthday-cake mr-2 text-pink-400"></i>}
              {m.toLowerCase() === 'dumpling' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'skewer' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'flatbread' && <i className="fa-solid fa-bread-slice mr-2 text-amber-500"></i>}
              {m.toLowerCase() === 'bowl' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'onepot' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.toLowerCase() === 'gratin' && <i className="fa-solid fa-utensils mr-2 text-orange-600"></i>}
              {m.toLowerCase() === 'stewpot' && <i className="fa-solid fa-mug-hot mr-2 text-blue-600"></i>}
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      )}
      {required && !isValid && (
        <div className="mt-2">
          <span className="text-xs text-red-600">At least one tag is required</span>
        </div>
      )}
    </div>
  );
}


