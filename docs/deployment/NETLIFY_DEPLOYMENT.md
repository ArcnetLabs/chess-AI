# 🚀 Netlify Deployment Guide

## Overview

Netlify is an excellent choice for deploying the **frontend only** of your Chess AI application. Since Netlify specializes in static sites and serverless functions, you'll need to deploy your backend separately.

## Architecture with Netlify

```
┌─────────────────────────────────────────────────┐
│                Netlify (Frontend)               │
│              Next.js Static Site                │
│             • SPA Routing                       │
│             • Edge Functions                   │
│             • Forms & Analytics                 │
│              URL: https://your-app.netlify.app │
└─────────────────────────────────────────────────┘
                    │ HTTP/REST
                    ▼
┌─────────────────────────────────────────────────┐
│              Backend (Separate)                 │
│              Render.com / Railway                │
│              • FastAPI REST API                 │
│              • PostgreSQL Database              │
│              • Celery Workers                   │
│              • Stockfish Engine                 │
└─────────────────────────────────────────────────┘
```

---

## 🎯 Deployment Strategy

### Option 1: Netlify + Render (Recommended)
- **Frontend:** Netlify (Free tier available)
- **Backend:** Render.com (Free tier available)
- **Total Cost:** $0-20/month

### Option 2: Netlify + Railway
- **Frontend:** Netlify
- **Backend:** Railway.app
- **Total Cost:** $5-25/month

### Option 3: Netlify + AWS
- **Frontend:** Netlify
- **Backend:** AWS ECS/Lambda
- **Total Cost:** $20-100/month

---

## 📋 Prerequisites

### 1. Netlify Account
- Sign up at [netlify.com](https://netlify.com)
- Free tier includes:
  - 100GB bandwidth/month
  - 300 build minutes/month
  - 1 site (unlimited on Pro)

### 2. Backend Deployed Separately
- Backend must be deployed first (Render/Railway/AWS)
- Get the backend API URL
- Configure CORS to allow Netlify domain

### 3. GitHub Repository
- Your code should be on GitHub
- Netlify connects directly to GitHub

---

## 🔧 Frontend Configuration for Netlify

### 1. Update Next.js Configuration

Create/Update `frontend/next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable static exports for Netlify
  output: 'export',
  
  // Disable image optimization (static hosting)
  images: {
    unoptimized: true,
  },
  
  // Base path if deploying to subdirectory
  // basePath: '/app',
  
  // Trailing slash for Netlify routing
  trailingSlash: true,
  
  // Environment variables for build
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  
  // Rewrites for API routes (if using serverless functions)
  async rewrites() {
    return [
      // Proxy API calls to backend
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
```

### 2. Create Netlify Configuration

Create `frontend/netlify.toml`:

```toml
[build]
  # Build command for Next.js
  command = "npm run build"
  
  # Build output directory
  publish = "out"

[build.environment]
  # Node version
  NODE_VERSION = "18"
  
  # Environment variables
  NEXT_PUBLIC_API_URL = "https://your-backend-url.com"

# Handle routing for SPA
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

# API proxy (optional - if you want to proxy through Netlify)
[[redirects]]
  from = "/api/*"
  to = "https://your-backend-url.com/api/:splat"
  status = 200

# Headers for security
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"

# Cache static assets
[[headers]]
  for = "/_next/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/images/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000"

# Environment-specific settings
[context.production.environment]
  NEXT_PUBLIC_API_URL = "https://your-backend-url.com"

[context.deploy-preview.environment]
  NEXT_PUBLIC_API_URL = "https://your-backend-url.com"
```

### 3. Update Package.json Scripts

Ensure `frontend/package.json` has these scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "export": "next build && next export",
    "lint": "next lint",
    "type-check": "tsc --noEmit"
  }
}
```

### 4. Environment Variables

Create `.env.production.local` (don't commit to git):

```env
NEXT_PUBLIC_API_URL=https://your-backend-url.com
```

---

## 🚀 Deployment Steps

### Step 1: Deploy Backend First

#### Using Render.com (Recommended)
1. Go to [render.com](https://render.com)
2. Connect your GitHub repository
3. Create a new "Web Service"
4. Select `backend/Dockerfile` or build command
5. Set environment variables
6. Deploy and get the URL

#### Using Railway.app
1. Go to [railway.app](https://railway.app)
2. Connect GitHub repository
3. Add backend service
4. Configure environment
5. Deploy and get the URL

### Step 2: Configure Backend CORS

Update backend environment to allow Netlify:

```env
# In backend .env
BACKEND_CORS_ORIGINS=https://your-app.netlify.app,https://your-app.netlify.app/*,https://your-custom-domain.com
```

### Step 3: Deploy Frontend to Netlify

#### Method 1: Git-based Deployment (Recommended)

1. **Connect Netlify to GitHub**
   - Go to Netlify dashboard
   - Click "New site from Git"
   - Connect to GitHub
   - Select your repository

2. **Configure Build Settings**
   ```
   Build command: npm run build
   Publish directory: out
   Node version: 18
   ```

3. **Set Environment Variables**
   ```
   NEXT_PUBLIC_API_URL: https://your-backend-url.com
   ```

4. **Deploy**
   - Click "Deploy site"
   - Wait for build (2-5 minutes)

#### Method 2: Drag & Drop (Quick)

1. **Build Locally**
   ```bash
   cd frontend
   npm run build
   # Output will be in 'out' directory
   ```

2. **Deploy to Netlify**
   - Go to Netlify dashboard
   - Drag the `out` folder to the deployment area
   - Wait for deployment

### Step 4: Configure Custom Domain (Optional)

1. **Add Domain**
   - Go to Site settings → Domain management
   - Add your custom domain

2. **Configure DNS**
   ```
   # Netlify DNS (recommended)
   A record: 75.2.60.5
   CNAME: www.netlify.netlify.com
   
   # Or use your own DNS
   CNAME: your-site.netlify.app
   ```

3. **SSL Certificate**
   - Netlify provides free SSL automatically

---

## 🔧 Advanced Configuration

### 1. Serverless Functions (Optional)

If you want to move some backend logic to Netlify:

Create `frontend/netlify/functions/api-proxy.js`:

```javascript
const fetch = require('node-fetch');

exports.handler = async (event, context) => {
  const { path, httpMethod } = event;
  
  // Proxy to your backend
  const backendUrl = `${process.env.BACKEND_URL}${path}`;
  
  try {
    const response = await fetch(backendUrl, {
      method: httpMethod,
      headers: {
        'Content-Type': 'application/json',
        ...event.headers,
      },
      body: event.body,
    });
    
    const data = await response.json();
    
    return {
      statusCode: response.status,
      body: JSON.stringify(data),
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};
```

### 2. Form Handling

Netlify can handle forms automatically:

```jsx
// In your React component
<form
  name="contact"
  method="POST"
  data-netlify="true"
  netlify-honeypot="bot-field"
>
  <input type="hidden" name="form-name" value="contact" />
  <div hidden>
    <label>
      Don't fill this out if you're human: <input name="bot-field" />
    </label>
  </div>
  {/* Your form fields */}
</form>
```

### 3. Edge Functions

For performance, use Netlify Edge Functions:

Create `frontend/netlify/edge-functions/geo-location.js`:

```javascript
export default async (request, context) => {
  const country = context.geo.country;
  const city = context.geo.city;
  
  return new Response(
    JSON.stringify({ country, city }),
    {
      headers: {
        'Content-Type': 'application/json',
      },
    }
  );
};
```

---

## 🔍 Testing Your Deployment

### 1. Verify Frontend
```bash
# Visit your Netlify URL
curl https://your-app.netlify.app

# Should return your React app HTML
```

### 2. Test API Connection
```bash
# Test API proxy
curl https://your-app.netlify.app/api/v1/health

# Should proxy to your backend
```

### 3. Check Browser Console
- Open browser dev tools
- Check for any API errors
- Verify all requests work

### 4. Test Functionality
- Create a user
- Fetch games
- Analyze games
- View results

---

## 🐛 Troubleshooting

### Issue: Build Fails
```bash
# Common errors and fixes

# 1. Node version mismatch
# Set NODE_VERSION in netlify.toml
NODE_VERSION = "18"

# 2. Missing dependencies
# Ensure all dependencies are in package.json
npm install

# 3. Build command error
# Use correct command for static export
npm run build
```

### Issue: API Calls Fail
```bash
# 1. CORS error
# Add Netlify domain to backend CORS
BACKEND_CORS_ORIGINS=https://your-app.netlify.app

# 2. Wrong API URL
# Check NEXT_PUBLIC_API_URL
echo $NEXT_PUBLIC_API_URL

# 3. Environment variables not set
# Set in Netlify dashboard
Site settings → Build & deploy → Environment
```

### Issue: Routing Problems
```bash
# 1. 404 on refresh
# Add redirect in netlify.toml
[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

# 2. API routes not working
# Check proxy configuration
[[redirects]]
  from = "/api/*"
  to = "https://backend.com/api/:splat"
  status = 200
```

### Issue: Performance Slow
```bash
# 1. Enable caching
# Add cache headers in netlify.toml
[[headers]]
  for = "/_next/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000"

# 2. Optimize images
# Use next/image with unoptimized: true
```

---

## 📊 Cost Analysis

### Netlify Frontend Only
| Plan | Cost | Features |
|------|------|----------|
| **Starter** | Free | 100GB bandwidth, 300 build min |
| **Pro** | $19/mo | 400GB bandwidth, 1000 build min |
| **Business** | $99/mo | 1TB bandwidth, 3000 build min |

### Backend (Render.com)
| Plan | Cost | Features |
|------|------|----------|
| **Free** | $0 | 750h/month, sleeps after inactivity |
| **Starter** | $7/mo | Always on, 1GB RAM |
| **Standard** | $25/mo | 2GB RAM, 2 CPUs |

### Total Monthly Cost
- **Free Tier:** $0 (with limitations)
- **Basic Setup:** $7-25/month
- **Production Setup:** $25-50/month

---

## 🔒 Security Best Practices

### 1. Environment Variables
```bash
# Never expose secrets in frontend
# Only use NEXT_PUBLIC_ variables
# Backend handles all sensitive data
```

### 2. CORS Configuration
```env
# Be specific with allowed origins
BACKEND_CORS_ORIGINS=https://your-app.netlify.app
# Avoid wildcard in production
```

### 3. Security Headers
```toml
# In netlify.toml
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
```

### 4. Rate Limiting
```bash
# Implement rate limiting on backend
# Netlify doesn't provide API rate limiting
# Use backend middleware for this
```

---

## 📈 Performance Optimization

### 1. Static Optimization
```javascript
// next.config.js
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
};
```

### 2. Caching Strategy
```toml
# Cache static assets
[[headers]]
  for = "/_next/static/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

### 3. CDN Optimization
- Netlify provides global CDN automatically
- Edge caching enabled by default
- Images served from CDN

### 4. Bundle Optimization
```bash
# Analyze bundle size
npm run build
npx @next/bundle-analyzer

# Optimize imports
# Use dynamic imports for large components
```

---

## 🔄 Continuous Deployment

### Automatic Deployments
1. **Push to GitHub** → Auto-deploy to Netlify
2. **Pull Requests** → Deploy preview URLs
3. **Branch Deploys** → Different environments

### Deployment Hooks
```bash
# Trigger deploy from backend
curl -X POST -d '{}' https://api.netlify.com/build_hooks/YOUR_HOOK_ID
```

### Build Notifications
- Slack integration
- Email notifications
- Discord webhooks

---

## 📚 Additional Resources

### Documentation
- [Netlify Docs](https://docs.netlify.com/)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [Render.com Docs](https://render.com/docs)

### Tools
- [Netlify CLI](https://cli.netlify.com/)
- [Next.js Bundle Analyzer](https://www.npmjs.com/package/@next/bundle-analyzer)

### Examples
- [Next.js on Netlify](https://github.com/netlify-templates/next-netlify-starter)
- [React Static Site](https://github.com/netlify-templates/react-starter)

---

## 🎯 Summary

### ✅ What Netlify Handles Well
- ✅ Static site deployment
- ✅ Global CDN
- ✅ Automatic HTTPS
- ✅ Form handling
- ✅ Edge functions
- ✅ CI/CD integration

### ⚠️ What Netlify Doesn't Handle
- ❌ Backend API (deploy separately)
- ❌ Database hosting
- ❌ Background tasks (Celery)
- ❌ Stockfish engine

### 🚀 Recommended Setup
1. **Frontend:** Netlify (static Next.js)
2. **Backend:** Render.com (FastAPI + PostgreSQL)
3. **Total Cost:** $7-25/month
4. **Setup Time:** 30-60 minutes

### 📋 Final Checklist
- [ ] Backend deployed and accessible
- [ ] CORS configured for Netlify domain
- [ ] Next.js configured for static export
- [ ] Netlify.toml configured
- [ ] Environment variables set
- [ ] Custom domain configured (optional)
- [ ] HTTPS working (automatic)
- [ ] API calls working
- [ ] Forms working (if used)
- [ ] Performance optimized

---

**Ready to deploy?** Start with Step 1 and follow the guide! 🚀

**Need help?** Check the troubleshooting section or open an issue.
