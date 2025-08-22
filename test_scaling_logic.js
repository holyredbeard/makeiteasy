// Test script to verify the scaling logic from RecipeView.jsx
// Simplified version to test unit preservation

// Mock the scaleQuantity function with simplified logic
const scaleQuantity = (quantity, factor) => {
  if (!quantity || factor === 1) return quantity;
  if (typeof quantity !== 'string') return quantity;
  
  // Simple scaling for numbers only
  const num = parseFloat(quantity.replace(',', '.'));
  if (isNaN(num)) return quantity;
  
  const scaled = num * factor;
  return Math.round(scaled * 100) / 100; // Round to 2 decimal places
};

// Mock splitQuantityFromText function
const splitQuantityFromText = (raw) => {
  const line = String(raw || '').trim();
  if (!line) return { quantity: '', name: '' };
  
  // Simple regex to split quantity and name
  const match = line.match(/^(\d+(?:\.\d+)?)\s*(\w+)?\s*(.*)$/);
  if (!match) return { quantity: '', name: line };
  
  const quantity = match[1];
  const unit = match[2] || '';
  const name = match[3] || '';
  
  return { quantity, name: unit ? `${unit} ${name}`.trim() : name };
};

// Test with pizza recipe ingredients
const testIngredients = [
  '25 gram jäst',
  '4 dl ost'
];

console.log('Testing scaling logic with pizza recipe ingredients:');
console.log('Original servings: 1');
console.log('Scaled servings: 1 (no change)');
console.log('Expected: units should be preserved\n');

testIngredients.forEach(ing => {
  const factor = 1; // No scaling
  const { quantity, name } = splitQuantityFromText(ing);
  const scaledQuantity = scaleQuantity(quantity, factor);
  
  // Preserve units from original quantity
  const parsedOriginal = splitQuantityFromText(ing);
  const originalUnit = parsedOriginal.name.split(' ')[0]; // Get first word as unit
  
  let result;
  if (originalUnit && !name.toLowerCase().includes(originalUnit.toLowerCase())) {
    result = `${scaledQuantity} ${originalUnit} ${name}`.trim();
  } else {
    result = `${scaledQuantity} ${name}`.trim();
  }
  
  console.log(`Input: "${ing}" -> Output: "${result}"`);
});

console.log('\nTesting with scaling factor 2:');
testIngredients.forEach(ing => {
  const factor = 2; // Double the servings
  const { quantity, name } = splitQuantityFromText(ing);
  const scaledQuantity = scaleQuantity(quantity, factor);
  
  const parsedOriginal = splitQuantityFromText(ing);
  const originalUnit = parsedOriginal.name.split(' ')[0];
  
  let result;
  if (originalUnit && !name.toLowerCase().includes(originalUnit.toLowerCase())) {
    result = `${scaledQuantity} ${originalUnit} ${name}`.trim();
  } else {
    result = `${scaledQuantity} ${name}`.trim();
  }
  
  console.log(`Input: "${ing}" -> Output: "${result}"`);
});