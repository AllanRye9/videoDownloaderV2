# 📥 Video Downloader - Mobile Edition

A powerful, mobile-optimized video downloader that works seamlessly on iOS and Android devices. Built with Flask, SocketIO, and yt-dlp.

## ✨ Features

### Core Features
- 📱 **Mobile-First Design**: Optimized UI for iOS and Android
- 🎥 **Multi-Platform Support**: YouTube, TikTok, Instagram, and more
- 🎨 **Quality Selection**: Choose from multiple resolutions
- ⚡ **Real-Time Progress**: Live download updates via WebSocket
- 📊 **Format Options**: Video (MP4) and audio-only downloads
- 🌓 **Dark Mode**: Automatic dark/light theme support
- 📲 **PWA Ready**: Install as an app on mobile devices

### Mobile-Specific Features
- ✅ **Automatic Downloads**: Files download directly to device
- 📱 **iOS Range Requests**: Proper video streaming support
- 🔄 **Background Support**: Continue downloads when app is minimized
- 💾 **Storage Management**: Manual file deletion control
- 🎯 **Responsive Design**: Works perfectly on all screen sizes

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- yt-dlp (automatically installed)
- ffmpeg (for video merging)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd video_downloader
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install ffmpeg** (required for merging video/audio)

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from: https://ffmpeg.org/download.html

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Run the server**
```bash
python app.py
```

The server will start on `http://localhost:5000`

## 📱 Mobile Deployment

### Option 1: Deploy to Cloud (Recommended)

#### Deploy to Railway
1. Sign up at [Railway.app](https://railway.app)
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository
4. Railway will auto-detect Flask and deploy
5. Add environment variables in Railway dashboard
6. Get your public URL (e.g., `your-app.railway.app`)

#### Deploy to Render
1. Sign up at [Render.com](https://render.com)
2. Click "New Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k eventlet -w 1 app:app`
5. Add environment variables
6. Deploy and get your URL

#### Deploy to Heroku
```bash
# Install Heroku CLI
heroku login
heroku create your-app-name

# Add buildpacks
heroku buildpacks:add --index 1 heroku/python
heroku buildpacks:add --index 2 https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest

# Deploy
git push heroku main
```

### Option 2: VPS Deployment

```bash
# On your VPS (Ubuntu)
sudo apt update
sudo apt install python3 python3-pip ffmpeg nginx

# Clone and setup
git clone <repository-url>
cd video_downloader
pip3 install -r requirements.txt

# Run with gunicorn
gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 app:app
```

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 3: Docker Deployment

```bash
# Build image
docker build -t video-downloader .

# Run container
docker run -d -p 5000:5000 \
  -v $(pwd)/downloads:/app/downloads \
  -e AUTO_DELETE_ENABLED=false \
  video-downloader
```

## 📱 Mobile App Integration

### For Native iOS/Android Apps

The backend provides REST API endpoints that can be consumed by native mobile apps:

#### API Endpoints

**1. Get Video Information**
```bash
POST /api/info
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=..."
}

Response:
{
  "title": "Video Title",
  "thumbnail": "https://...",
  "duration": 300,
  "uploader": "Channel Name",
  "description": "...",
  "formats_available": 20
}
```

**2. Get Available Formats**
```bash
POST /api/formats
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=..."
}

Response:
{
  "formats": [
    {
      "format_id": "137",
      "resolution": "1080p",
      "ext": "mp4",
      "filesize_mb": 125.5
    }
  ],
  "audio_only": [...]
}
```

**3. Start Download**
```bash
POST /api/start_download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=...",
  "format": "137+bestaudio/best"
}

Response:
{
  "download_id": "uuid-here",
  "title": "Video Title",
  "status": "queued"
}
```

**4. Get Download Status**
```bash
GET /api/status/{download_id}

Response:
{
  "id": "uuid",
  "title": "Video Title",
  "status": "completed",
  "percent": 100,
  "file_size": 131428352,
  "download_url": "/download/uuid",
  "stream_url": "/stream/uuid"
}
```

**5. Download File**
```bash
GET /download/{download_id}

Response: File download with proper headers for mobile
```

**6. Stream File (iOS Compatible)**
```bash
GET /stream/{download_id}

Response: Video stream with Range request support
```

### WebSocket Events (Real-time Updates)

```javascript
// Connect to WebSocket
const socket = io('https://your-server.com');

// Subscribe to download updates
socket.emit('subscribe', { download_id: 'uuid' });

// Listen for progress
socket.on('progress', (data) => {
  console.log(data.line); // Progress information
});

// Listen for completion
socket.on('completed', (data) => {
  console.log('Download complete:', data.download_url);
});

// Listen for failures
socket.on('failed', (data) => {
  console.log('Download failed:', data.error);
});
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 5000 | Server port |
| `DEBUG` | false | Debug mode |
| `SECRET_KEY` | (required) | Flask secret key |
| `DOWNLOAD_FOLDER` | downloads | Download directory |
| `AUTO_DELETE_ENABLED` | false | Enable auto-deletion |
| `AUTO_DELETE_SECONDS` | 3600 | Auto-delete delay (1 hour) |

### Auto-Delete Feature

For production use with limited storage:

```bash
# Enable auto-delete after 1 hour
AUTO_DELETE_ENABLED=true
AUTO_DELETE_SECONDS=3600
```

For mobile development/testing:

```bash
# Disable auto-delete
AUTO_DELETE_ENABLED=false
```

## 📱 iOS Specific Features

### Range Request Support
The `/stream/{download_id}` endpoint supports HTTP Range requests, which is required for:
- Video scrubbing in iOS Safari
- Background audio playback
- Proper video player controls

### PWA Installation
Users can add the app to their iOS home screen:
1. Open in Safari
2. Tap Share button
3. Select "Add to Home Screen"

## 🤖 Android Specific Features

### Download Manager Integration
Downloads trigger the browser's download manager, saving files to:
- `/storage/emulated/0/Download/`

### Chrome Custom Tabs
The app works perfectly in Chrome Custom Tabs for in-app browsers.

## 🛠️ Development

### Project Structure
```
video_downloader/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html        # Mobile-optimized frontend
├── downloads/            # Downloaded files (gitignored)
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
└── README.md            # This file
```

### Running in Development
```bash
# With auto-reload
DEBUG=true python app.py

# With custom port
PORT=8000 python app.py
```

### Testing Mobile Features
```bash
# Test on local network
# Find your local IP: ifconfig (macOS/Linux) or ipconfig (Windows)
python app.py

# Access from mobile device
# http://192.168.x.x:5000
```

## 🔒 Security Considerations

1. **CORS**: Currently set to `*` for development. In production, restrict to your domain:
   ```python
   CORS(app, resources={r"/*": {"origins": "https://yourdomain.com"}})
   ```

2. **Rate Limiting**: Consider adding rate limiting for production:
   ```bash
   pip install flask-limiter
   ```

3. **HTTPS**: Always use HTTPS in production for:
   - Secure file downloads
   - WebSocket connections
   - Cookie security

4. **File Size Limits**: Configured to 5GB max (adjust in `app.py`)

## 📊 Monitoring

### Health Check Endpoint
```bash
GET /health

Response:
{
  "status": "healthy",
  "active_downloads": 2,
  "total_downloads": 15
}
```

### Logs
```bash
# View logs in production
tail -f /var/log/video-downloader/app.log
```

## 🐛 Troubleshooting

### Issue: Videos won't download on iOS
**Solution**: Make sure you're using the `/download/{id}` endpoint, not `/downloads/{filename}`

### Issue: "File not found" errors
**Solution**: Check that the downloads folder has proper permissions
```bash
chmod 755 downloads/
```

### Issue: WebSocket disconnections on mobile
**Solution**: Increase ping timeout in `app.py`:
```python
socketio = SocketIO(app, ping_timeout=120, ping_interval=30)
```

### Issue: Large files fail to download
**Solution**: Increase max file size in `app.py`:
```python
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024  # 10GB
```

## 📝 License

MIT License - feel free to use for personal or commercial projects

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test on both iOS and Android
5. Submit a pull request

## 📞 Support

For issues or questions:
- Open a GitHub issue
- Check existing issues for solutions
- Review the API documentation above

## 🎯 Roadmap

- [ ] Playlist download support
- [ ] Subtitle download
- [ ] Background download on iOS
- [ ] Android app (native)
- [ ] iOS app (native)
- [ ] User authentication
- [ ] Download history/favorites
- [ ] Custom output formats
- [ ] Video trimming before download

## 📚 Additional Resources

- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [Flask-SocketIO Documentation](https://flask-socketio.readthedocs.io/)
- [PWA Documentation](https://web.dev/progressive-web-apps/)

---

Made with ❤️ for mobile users
