import React, { useEffect, useState } from 'react';

const API_BASE = 'http://localhost:8000';

function OAuthCallback() {
  const [status, setStatus] = useState('Processing...');

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Get code and state from URL
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        
        if (!code) {
          setStatus('Error: No authorization code received');
          return;
        }

        // Send code to backend
        const response = await fetch(`${API_BASE}/api/v1/auth/google/callback`, {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ code, state })
        });

        if (response.ok) {
          // Redirect to main page
          window.location.href = '/';
        } else {
          const error = await response.json();
          setStatus(`Error: ${error.detail || 'Authentication failed'}`);
        }
      } catch (error) {
        console.error('OAuth callback error:', error);
        setStatus('Error processing authentication');
      }
    };

    handleCallback();
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="bg-white p-8 rounded-xl shadow-md max-w-md w-full">
        <h2 className="text-2xl font-bold text-center mb-6">Google Sign In</h2>
        <p className="text-center text-gray-600">{status}</p>
      </div>
    </div>
  );
}

export default OAuthCallback;