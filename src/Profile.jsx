import React, { useEffect, useRef, useState } from 'react';
import { useOutletContext, useNavigate, Link } from 'react-router-dom';
import { CameraIcon, PlayCircleIcon, GlobeAltIcon, MusicalNoteIcon, LinkIcon as LinkIconHero, MapPinIcon } from '@heroicons/react/24/outline';

const API_BASE = 'http://localhost:8000/api/v1';
const API_ROOT = API_BASE.replace(/\/api\/v1$/, '');

function normalizeBackendUrl(pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  return `${API_ROOT}${pathOrUrl.startsWith('/') ? pathOrUrl : '/' + pathOrUrl}`;
}

export default function Profile() {
  const { currentUser, refreshCurrentUser, setCurrentUser } = useOutletContext();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [location, setLocation] = useState('');
  const [instagram, setInstagram] = useState('');
  const [youtube, setYoutube] = useState('');
  const [facebook, setFacebook] = useState('');
  const [tiktok, setTiktok] = useState('');
  const [website, setWebsite] = useState('');
  const [avatar, setAvatar] = useState(null);
  const [avatarPreview, setAvatarPreview] = useState('');
  const [avatarDirty, setAvatarDirty] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState('');
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  useEffect(() => {
    if (!currentUser) return;
    setName(currentUser.full_name || '');
    setEmail(currentUser.email || '');
    if (currentUser.avatar_url) setAvatarPreview(normalizeBackendUrl(currentUser.avatar_url));
    setUsername(currentUser.username || '');
    setLocation(currentUser.location || '');
    setInstagram(currentUser.instagram_url || '');
    setYoutube(currentUser.youtube_url || '');
    setFacebook(currentUser.facebook_url || '');
    setTiktok(currentUser.tiktok_url || '');
    setWebsite(currentUser.website_url || '');
    setAvatarDirty(false);
  }, [currentUser]);

  const onPickFile = () => fileRef.current?.click();
  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAvatar(file);
    const url = URL.createObjectURL(file);
    setAvatarPreview(url);
    setAvatarDirty(true);
  };
  const removeAvatar = () => {
    setAvatar(null);
    setAvatarPreview('');
    if (fileRef.current) fileRef.current.value = '';
    setAvatarDirty(true);
  };

  const saveAvatarOnly = async () => {
    try {
      setLoading(true);
      setSuccess('');
      setError('');
      const form = new FormData();
      if (avatar) form.append('avatar', avatar);
      form.append('remove_avatar', avatarPreview === '' ? 'true' : 'false');
      const res = await fetch(`${API_BASE}/auth/profile`, {
        method: 'POST',
        credentials: 'include',
        body: form
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail || 'Failed to update avatar');
      setSuccess('Avatar saved.');
      setAvatarDirty(false);
      await refreshCurrentUser?.();
    } catch (err) {
      setError(err.message || 'Avatar save failed');
    } finally {
      setLoading(false);
    }
  };

  const validate = () => {
    setError('');
    if (!name.trim()) return setError('Name is required'), false;
    if (!email.trim()) return setError('Email is required'), false;
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return setError('Invalid email format'), false;
    const uname = username.trim();
    if (!uname) return setError('Username is required'), false;
    if (!/^[a-z0-9_]{3,20}$/.test(uname)) return setError('Username must be 3-20 chars: a-z, 0-9, _'), false;
    // Only validate password when BOTH fields are filled; otherwise ignore password change
    if (password && confirmPassword) {
      if (password.length < 6) return setError('Password must be at least 6 characters'), false;
      if (password !== confirmPassword) return setError('Passwords do not match'), false;
    }
    return true;
  };

  const onSave = async (e) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setSuccess('');
    setError('');
    try {
      const form = new FormData();
      form.append('full_name', name.trim());
      form.append('username', username.trim());
      form.append('email', email.trim());
      form.append('location', location.trim());
      form.append('instagram_url', instagram.trim());
      form.append('youtube_url', youtube.trim());
      form.append('facebook_url', facebook.trim());
      form.append('tiktok_url', tiktok.trim());
      form.append('website_url', website.trim());
      // Only send password if user filled both fields correctly
      if (password && confirmPassword && password === confirmPassword && password.length >= 6) {
        form.append('password', password);
      }
      if (avatar) form.append('avatar', avatar);
      form.append('remove_avatar', avatarPreview === '' ? 'true' : 'false');

      const res = await fetch(`${API_BASE}/auth/profile`, {
        method: 'POST',
        credentials: 'include',
        body: form
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json.detail || 'Failed to update profile');
      setSuccess('Profile updated successfully.');
      // Refresh header user info
      await refreshCurrentUser?.();
    } catch (err) {
      setError(err.message || 'Update failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-10 px-6">
      <div className="flex items-baseline justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Profile</h1>
        {username && (
          <Link to={`/users/${encodeURIComponent(username)}`} className="text-sm text-[#e87b35] hover:underline">
            View public profile
          </Link>
        )}
      </div>

      {success && (
        <div className="mb-4 bg-green-50 text-green-800 border border-green-200 px-4 py-3 rounded-lg">{success}</div>
      )}
      {error && (
        <div className="mb-4 bg-red-50 text-red-800 border border-red-200 px-4 py-3 rounded-lg">{error}</div>
      )}

      <form onSubmit={onSave} className="space-y-6 bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        <div className="flex items-center gap-4">
          <div className="w-20 h-20 rounded-full bg-gray-100 overflow-hidden flex items-center justify-center">
            {avatarPreview ? (
              <img src={avatarPreview} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <span className="text-gray-400 text-sm">No image</span>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={avatarDirty ? saveAvatarOnly : onPickFile}
              className={`px-3 py-2 rounded-lg text-sm text-white ${avatarDirty ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-800 hover:bg-gray-900'}`}
            >
              {avatarDirty ? 'Save' : 'Upload'}
            </button>
            {avatarPreview && (
              <button type="button" onClick={removeAvatar} className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">Remove</button>
            )}
            <input ref={fileRef} type="file" accept="image/*" onChange={onFileChange} className="hidden" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Your name" required />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="username" pattern="^[a-z0-9_]{3,20}$" title="3-20 chars; lowercase letters, numbers and underscore only" required />
          <p className="text-xs text-gray-500 mt-1">3-20 characters, lowercase letters, numbers and underscore.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="you@example.com" required />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
          <div className="relative">
            <MapPinIcon className="h-5 w-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input type="text" value={location} onChange={(e)=>setLocation(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="City, Country" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Social</label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="relative">
              <CameraIcon className="h-5 w-5 text-pink-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="url" value={instagram} onChange={(e)=>setInstagram(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Instagram URL" />
            </div>
            <div className="relative">
              <PlayCircleIcon className="h-5 w-5 text-red-600 absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="url" value={youtube} onChange={(e)=>setYoutube(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="YouTube URL" />
            </div>
            <div className="relative">
              <GlobeAltIcon className="h-5 w-5 text-blue-600 absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="url" value={facebook} onChange={(e)=>setFacebook(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Facebook URL" />
            </div>
            <div className="relative">
              <MusicalNoteIcon className="h-5 w-5 text-black absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="url" value={tiktok} onChange={(e)=>setTiktok(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="TikTok URL" />
            </div>
            <div className="relative md:col-span-2">
              <LinkIconHero className="h-5 w-5 text-gray-700 absolute left-3 top-1/2 -translate-y-1/2" />
              <input type="url" value={website} onChange={(e)=>setWebsite(e.target.value)} className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Website URL" />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Leave blank to keep current" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent" placeholder="Confirm new password" />
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => navigate(-1)} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
          <button type="submit" disabled={loading} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300">{loading ? 'Saving…' : 'Save'}</button>
        </div>
      </form>
    </div>
  );
}

