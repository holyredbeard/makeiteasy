import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Food2Guide from './Food2Guide';
import MyRecipes from './MyRecipes';
import Profile from './Profile';
import Layout from './Layout';
import RecipePage from './RecipePage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Food2Guide />} />
        <Route path="my-recipes" element={<MyRecipes />} />
        <Route path="profile" element={<Profile />} />
        <Route path="recipes/:id" element={<RecipePage />} />
      </Route>
    </Routes>
  );
}

export default App;