# Google OAuth Setup Guide

This guide will help you set up Google OAuth authentication for your Make It Easy application.

## Prerequisites

- Google Cloud Platform account
- Your application running on a known domain (localhost for development)

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google+ API (for user profile information)

## Step 2: Configure OAuth Consent Screen

1. In the Google Cloud Console, go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type (unless you have a Google Workspace account)
3. Fill in the required information:
   - App name: "Make It Easy"
   - User support email: Your email
   - Developer contact information: Your email
4. Add scopes:
   - `../auth/userinfo.email`
   - `../auth/userinfo.profile`
5. Add test users (for development)

## Step 3: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Choose **Web application**
4. Configure:
   - Name: "Make It Easy Web Client"
   - Authorized JavaScript origins: `http://localhost:8000`
   - Authorized redirect URIs: `http://localhost:8000`
   
   **Important:** Do NOT include paths like `/api/v1/auth/google/callback` - just the base URL!
5. Save the **Client ID** and **Client Secret**

## Step 4: Configure Environment Variables

Create a `.env` file in your project root:

```bash
# Google OAuth Configuration
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000

# JWT Configuration (generate a secure random key)
JWT_SECRET_KEY=your_jwt_secret_key_here
```

## Step 5: Install Dependencies

Make sure you have the required dependencies:

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 requests
```

## Step 6: Test the Integration

1. Start your application
2. Navigate to the authentication page
3. Click "Continue with Google" or "Sign up with Google"
4. You should be redirected to Google's OAuth consent screen
5. After authorization, you'll be redirected back to your application

## Production Configuration

For production deployment:

1. Update the authorized origins and redirect URIs in Google Cloud Console
2. Set the environment variables on your production server
3. Ensure your domain is verified in Google Cloud Console

## Troubleshooting

**Error: "redirect_uri_mismatch"**
- Check that your redirect URI exactly matches what's configured in Google Cloud Console
- Ensure there are no trailing slashes or extra characters

**Error: "invalid_client"**
- Verify your Client ID and Client Secret are correct
- Check that the OAuth consent screen is properly configured

**Error: "access_denied"**
- User declined the authorization request
- Check that required scopes are properly configured

## Security Notes

- Never commit your `.env` file to version control
- Use environment variables for all sensitive configuration
- Regularly rotate your client secrets
- Monitor OAuth usage in Google Cloud Console 