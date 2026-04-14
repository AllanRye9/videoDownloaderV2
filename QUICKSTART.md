# 🚀 Quick Start Guide

Get your video downloader running in 5 minutes!

## Option 1: Local Development (Fastest)

```bash
# 1. Run setup script
chmod +x setup.sh
./setup.sh

# 2. Activate virtual environment
source venv/bin/activate

# 3. Start server
python app.py
```

Open: http://localhost:5000

## Option 2: Docker (Easiest)

```bash
# Build and run
docker-compose up

# Or use Docker directly
docker build -t video-downloader .
docker run -p 5000:5000 video-downloader
```

Open: http://localhost:5000

## Option 3: Cloud Deployment (Production)

### Railway (Recommended - Free Tier Available)
1. Go to [railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub"
3. Connect your repository
4. Add environment variables:
   ```
   SECRET_KEY=your-random-secret-key
   AUTO_DELETE_ENABLED=false
   ```
5. Deploy!

### Render
1. Go to [render.com](https://render.com)
2. Click "New Web Service"
3. Connect GitHub repository
4. Configure:
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `gunicorn -k eventlet -w 1 app:app`
5. Add environment variables
6. Deploy!

### Heroku
```bash
heroku create your-app-name
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest
git push heroku main
```

## Environment Variables

Create `.env` file:
```env
PORT=5000
DEBUG=false
SECRET_KEY=change-this-to-random-string
AUTO_DELETE_ENABLED=false
AUTO_DELETE_SECONDS=3600
```

## Access from Mobile

### iOS/Android (Same WiFi)
1. Find your computer's IP address:
   ```bash
   # macOS/Linux
   ifconfig | grep "inet "
   
   # Windows
   ipconfig
   ```

2. Start server:
   ```bash
   python app.py
   ```

3. Open on mobile:
   ```
   http://YOUR_IP_ADDRESS:5000
   ```

### Production (Internet)
Deploy to cloud and use the provided URL

## Features You Get

✅ Download from YouTube, TikTok, Instagram, etc.
✅ Quality selection (144p to 8K)
✅ Real-time progress tracking
✅ Mobile-optimized interface
✅ Dark mode support
✅ Direct download to device
✅ Video streaming for preview

## API Endpoints (for Native Apps)

```bash
# Get video info
POST /api/info
Body: {"url": "https://..."}

# Start download
POST /api/start_download
Body: {"url": "https://...", "format": "best"}

# Download file
GET /download/{download_id}

# Stream file
GET /stream/{download_id}
```

See `MOBILE_API.md` for complete API documentation.

## Native App Integration

### iOS (Swift)
See `NATIVE_INTEGRATION.md` for complete code examples.

### Android (Kotlin)
See `NATIVE_INTEGRATION.md` for complete code examples.

## Troubleshooting

### "ffmpeg not found"
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
Download from: https://ffmpeg.org/download.html
```

### "Module not found"
```bash
pip install -r requirements.txt
```

### "Port already in use"
```bash
# Change port in .env
PORT=8000
```

### Videos won't download on mobile
- Make sure you're using `/download/{id}` endpoint
- Check CORS is enabled (it is by default)
- Verify HTTPS if in production

## Next Steps

1. **Deploy to Cloud** - Use Railway or Render for free hosting
2. **Build Native App** - Use NATIVE_INTEGRATION.md guide
3. **Customize UI** - Edit templates/index.html
4. **Add Auth** - Implement user authentication
5. **Scale Up** - Add Redis for session storage

## Support

- 📖 Full documentation: `README.md`
- 🔌 API reference: `MOBILE_API.md`
- 📱 Native apps: `NATIVE_INTEGRATION.md`
- 🐛 Issues: Check GitHub issues or create new one

## Performance Tips

- Enable auto-delete for limited storage
- Use CDN for static files in production
- Add Redis for better session management
- Implement rate limiting for public deployments

---

**That's it! You're ready to download videos! 🎉**
