import os
import re
import subprocess
import threading
import time
import uuid
import json
from datetime import datetime, timedelta

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'thisisjustthestart')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 * 1024  # 5GB max file size

# Enable CORS for mobile apps
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', ping_timeout=60, ping_interval=25)

DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Store download metadata
downloads = {}
download_lock = threading.Lock()

# Configuration
AUTO_DELETE_ENABLED = os.environ.get('AUTO_DELETE_ENABLED', 'false').lower() == 'true'
AUTO_DELETE_SECONDS = int(os.environ.get('AUTO_DELETE_SECONDS', '3600'))  # Default 1 hour


# =========================
# Mobile-optimized file serving
# =========================
@app.route('/download/<download_id>')
def download_file_by_id(download_id):
    """Download file by download ID - optimized for mobile browsers"""
    with download_lock:
        download = downloads.get(download_id)
    
    if not download or download.get('status') != 'completed':
        return jsonify({'error': 'Download not found or not completed'}), 404
    
    file_path = download.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    filename = os.path.basename(file_path)
    
    # Mobile-friendly download headers
    response = send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='video/mp4'
    )
    
    # Additional headers for better mobile compatibility
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.headers['Content-Type'] = 'video/mp4'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response


@app.route('/stream/<download_id>')
def stream_file(download_id):
    """Stream file for in-app preview - works better on iOS"""
    with download_lock:
        download = downloads.get(download_id)
    
    if not download or download.get('status') != 'completed':
        return jsonify({'error': 'Download not found'}), 404
    
    file_path = download.get('file_path')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Support range requests for iOS/Safari
    range_header = request.headers.get('Range', None)
    
    if not range_header:
        return send_file(file_path, mimetype='video/mp4')
    
    # Parse range header
    size = os.path.getsize(file_path)
    byte_range = range_header.replace('bytes=', '').split('-')
    start = int(byte_range[0]) if byte_range[0] else 0
    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else size - 1
    
    length = end - start + 1
    
    with open(file_path, 'rb') as f:
        f.seek(start)
        data = f.read(length)
    
    response = Response(data, 206, mimetype='video/mp4', direct_passthrough=True)
    response.headers.add('Content-Range', f'bytes {start}-{end}/{size}')
    response.headers.add('Accept-Ranges', 'bytes')
    response.headers.add('Content-Length', str(length))
    
    return response


# =========================
# Helpers
# =========================
def get_video_info(url):
    """Get comprehensive video information"""
    try:
        result = subprocess.run(
            ['yt-dlp', '--dump-json', '--no-playlist', url],
            capture_output=True, text=True, check=True, timeout=30
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Error getting video info: {e}")
        return None


def get_available_formats(url):
    """Get all available download formats"""
    try:
        result = subprocess.run(
            ['yt-dlp', '-F', '--no-playlist', url],
            capture_output=True, text=True, check=True, timeout=30
        )
        return result.stdout
    except:
        return None


def sanitize_filename(title):
    """Sanitize filename for cross-platform compatibility"""
    # Remove invalid characters for both Windows and Unix
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    # Remove control characters
    title = re.sub(r'[\x00-\x1f\x7f-\x9f]', "", title)
    # Limit length
    return title.strip()[:150] or "video"


# =========================
# Download worker
# =========================
def download_worker(download_id, url, output_path, format_spec, cookies_file=None):
    """Enhanced download worker with better error handling"""
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '--newline',
        '--progress',
        '--merge-output-format', 'mp4',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        '--referer', 'https://www.youtube.com/',
        '-f', format_spec,
        '-o', output_path,
        url
    ]

    if cookies_file:
        cmd.extend(['--cookies', cookies_file])

    with download_lock:
        downloads[download_id]['status'] = 'downloading'
        downloads[download_id]['start_time'] = time.time()

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            line = line.strip()

            if line:
                # Emit progress to subscribed clients
                socketio.emit('progress', {
                    'id': download_id,
                    'line': line
                }, room=download_id)

                # Parse percentage
                if '%' in line:
                    try:
                        percent = float(line.split('%')[0].split()[-1])
                        with download_lock:
                            downloads[download_id]['percent'] = percent
                    except:
                        pass
                
                # Parse speed and ETA
                if 'ETA' in line:
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if 'iB/s' in part and i > 0:
                                with download_lock:
                                    downloads[download_id]['speed'] = parts[i-1] + part
                            if part == 'ETA' and i < len(parts) - 1:
                                with download_lock:
                                    downloads[download_id]['eta'] = parts[i+1]
                    except:
                        pass

        process.wait()

        if process.returncode == 0:
            # Determine final file path
            final_path = output_path.replace('%(ext)s', 'mp4')
            
            # Handle cases where yt-dlp might have renamed the file
            if not os.path.exists(final_path):
                # Look for the file in the download folder
                base_name = os.path.splitext(os.path.basename(output_path))[0]
                for f in os.listdir(DOWNLOAD_FOLDER):
                    if f.startswith(base_name.replace('%(ext)s', '')):
                        final_path = os.path.join(DOWNLOAD_FOLDER, f)
                        break
            
            if os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                
                with download_lock:
                    downloads[download_id]['status'] = 'completed'
                    downloads[download_id]['end_time'] = time.time()
                    downloads[download_id]['file_path'] = final_path
                    downloads[download_id]['file_size'] = file_size
                    downloads[download_id]['percent'] = 100

                socketio.emit('completed', {
                    'id': download_id,
                    'file_size': file_size,
                    'download_url': f'/download/{download_id}',
                    'stream_url': f'/stream/{download_id}'
                }, room=download_id)

                socketio.emit('files_updated', broadcast=True)
            else:
                raise Exception("Downloaded file not found")
        else:
            raise Exception(f"Download failed with return code {process.returncode}")

    except Exception as e:
        print(f"Download error: {e}")
        with download_lock:
            downloads[download_id]['status'] = 'failed'
            downloads[download_id]['error'] = str(e)
        
        socketio.emit('failed', {
            'id': download_id,
            'error': str(e)
        }, room=download_id)


# =========================
# Cleanup worker
# =========================
def cleanup_worker():
    """Auto-delete old files if enabled"""
    while True:
        if AUTO_DELETE_ENABLED:
            now = time.time()

            with download_lock:
                for download_id, data in list(downloads.items()):
                    if data.get('status') == 'completed':
                        end_time = data.get('end_time')
                        file_path = data.get('file_path')

                        if end_time and (now - end_time > AUTO_DELETE_SECONDS):
                            try:
                                if file_path and os.path.exists(file_path):
                                    os.remove(file_path)
                                    print(f"Auto-deleted: {file_path}")

                                del downloads[download_id]

                                with app.app_context():
                                    socketio.emit('files_updated', broadcast=True)

                            except Exception as e:
                                print(f"Cleanup error: {e}")

        time.sleep(30)


# =========================
# API Routes
# =========================
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/info', methods=['POST'])
def get_info():
    """Get video information without downloading"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    info = get_video_info(url)
    
    if not info:
        return jsonify({'error': 'Could not fetch video information'}), 400
    
    # Extract relevant information
    return jsonify({
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'uploader': info.get('uploader'),
        'description': info.get('description', '')[:200],
        'formats_available': len(info.get('formats', [])),
        'best_quality': info.get('format'),
    })


@app.route('/api/formats', methods=['POST'])
def get_formats():
    """Get available formats for a video"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    info = get_video_info(url)
    
    if not info:
        return jsonify({'error': 'Could not fetch video information'}), 400
    
    formats = []
    seen = set()
    
    for f in info.get('formats', []):
        if f.get('vcodec') != 'none':  # Has video
            resolution = f.get('resolution') or f.get('format_note', 'unknown')
            ext = f.get('ext', 'mp4')
            filesize = f.get('filesize') or f.get('filesize_approx', 0)
            
            key = f"{resolution}_{ext}"
            if key not in seen:
                seen.add(key)
                formats.append({
                    'format_id': f.get('format_id'),
                    'resolution': resolution,
                    'ext': ext,
                    'filesize': filesize,
                    'filesize_mb': round(filesize / (1024 * 1024), 2) if filesize else None,
                    'fps': f.get('fps'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec'),
                })
    
    # Sort by quality (height)
    formats.sort(key=lambda x: int(re.search(r'\d+', x['resolution']).group()) if re.search(r'\d+', x['resolution']) else 0, reverse=True)
    
    return jsonify({
        'formats': formats,
        'audio_only': [
            {
                'format_id': f.get('format_id'),
                'ext': f.get('ext', 'mp3'),
                'abr': f.get('abr'),
                'filesize_mb': round(f.get('filesize', 0) / (1024 * 1024), 2) if f.get('filesize') else None,
            }
            for f in info.get('formats', [])
            if f.get('vcodec') == 'none' and f.get('acodec') != 'none'
        ][:5]  # Top 5 audio formats
    })


@app.route('/api/start_download', methods=['POST'])
def start_download():
    """Start a download with format selection"""
    data = request.get_json()
    url = data.get('url')
    format_spec = data.get('format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    download_id = str(uuid.uuid4())

    # Get video title
    info = get_video_info(url)
    if info:
        title = info.get('title', f"video_{download_id[:8]}")
    else:
        title = f"video_{download_id[:8]}"

    safe_title = sanitize_filename(title)
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}.%(ext)s")

    with download_lock:
        downloads[download_id] = {
            'id': download_id,
            'url': url,
            'title': safe_title,
            'status': 'queued',
            'percent': 0,
            'output_template': output_template,
            'created_at': datetime.now().isoformat(),
            'format_spec': format_spec
        }

    thread = threading.Thread(
        target=download_worker,
        args=(download_id, url, output_template, format_spec, None)
    )
    thread.daemon = True
    thread.start()

    return jsonify({
        'download_id': download_id,
        'title': safe_title,
        'status': 'queued'
    })


@app.route('/api/status/<download_id>')
def get_status(download_id):
    """Get download status"""
    with download_lock:
        download = downloads.get(download_id, {})
    
    if not download:
        return jsonify({'error': 'Download not found'}), 404
    
    # Add URLs if completed
    if download.get('status') == 'completed':
        download['download_url'] = f'/download/{download_id}'
        download['stream_url'] = f'/stream/{download_id}'
    
    return jsonify(download)


@app.route('/api/downloads')
def list_downloads():
    """List all downloads"""
    with download_lock:
        download_list = list(downloads.values())
    
    # Add URLs for completed downloads
    for download in download_list:
        if download.get('status') == 'completed':
            download['download_url'] = f'/download/{download["id"]}'
            download['stream_url'] = f'/stream/{download["id"]}'
    
    return jsonify(download_list)


@app.route('/api/delete/<download_id>', methods=['DELETE'])
def delete_download(download_id):
    """Manually delete a download"""
    with download_lock:
        download = downloads.get(download_id)
        
        if not download:
            return jsonify({'error': 'Download not found'}), 404
        
        file_path = download.get('file_path')
        
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                return jsonify({'error': f'Failed to delete file: {str(e)}'}), 500
        
        del downloads[download_id]
    
    socketio.emit('files_updated', broadcast=True)
    
    return jsonify({'success': True})


@app.route('/api/config')
def get_config():
    """Get server configuration"""
    return jsonify({
        'auto_delete_enabled': AUTO_DELETE_ENABLED,
        'auto_delete_seconds': AUTO_DELETE_SECONDS,
        'max_file_size_gb': app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024 * 1024)
    })


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_downloads': sum(1 for d in downloads.values() if d.get('status') in ('queued', 'downloading')),
        'total_downloads': len(downloads)
    })


# =========================
# Socket.IO Events
# =========================
@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')
    emit('connected', {'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')


@socketio.on('subscribe')
def handle_subscribe(data):
    """Subscribe to download updates"""
    download_id = data.get('download_id')
    
    if download_id:
        join_room(download_id)
        emit('subscribed', {'id': download_id})
        
        # Send current status
        with download_lock:
            download = downloads.get(download_id, {})
        
        if download:
            emit('status_update', download)


# =========================
# Start app
# =========================
if __name__ == '__main__':
    print("=" * 50)
    print("Video Downloader Server Starting")
    print("=" * 50)
    print(f"Download folder: {DOWNLOAD_FOLDER}")
    print(f"Auto-delete: {AUTO_DELETE_ENABLED}")
    if AUTO_DELETE_ENABLED:
        print(f"Auto-delete after: {AUTO_DELETE_SECONDS} seconds")
    print("=" * 50)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_worker)
    cleanup_thread.daemon = True
    cleanup_thread.start()

    # Run server
    socketio.run(
        app,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000)),
        debug=os.environ.get('DEBUG', 'false').lower() == 'true',
        allow_unsafe_werkzeug=True
    )
