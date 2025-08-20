import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Food2Guide from './Food2Guide';
import MyRecipes from './MyRecipes';
import Profile from './Profile';
import Layout from './Layout';
import Home from './pages/Home.tsx';
import RecipePage from './RecipePage';
import CollectionsPage from './CollectionsPage.jsx';
import CreateRecipe from './CreateRecipe.jsx';
import UserPublicProfile from './pages/UserPublicProfile.jsx';
import NutritionAdmin from './pages/NutritionAdmin.jsx';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="extract" element={<Food2Guide />} />
        <Route path="create" element={<CreateRecipe />} />
        <Route path="my-recipes" element={<MyRecipes />} />
        <Route path="collections" element={<CollectionsPage />} />
        <Route path="collections/:id" element={<CollectionsPage />} />
        <Route path="profile" element={<Profile />} />
        <Route path="users/:username" element={<UserPublicProfile />} />
        <Route path="recipes/:id" element={<RecipePage />} />
        <Route path="admin/nutrition" element={<NutritionAdmin />} />
        <Route path="shopping-list" element={<div>Shop List Page - Coming Soon</div>} />
      </Route>
    </Routes>
  );
}

export default App;