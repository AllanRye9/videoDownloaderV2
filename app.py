import asyncio
import os
import re
import subprocess
import threading
import time
import uuid
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import socketio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# =========================
# Configuration
# =========================
DOWNLOAD_FOLDER = os.environ.get('DOWNLOAD_FOLDER', 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

AUTO_DELETE_ENABLED = os.environ.get('AUTO_DELETE_ENABLED', 'false').lower() == 'true'
AUTO_DELETE_SECONDS = int(os.environ.get('AUTO_DELETE_SECONDS', '3600'))
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB

# =========================
# In-memory state
# =========================
downloads: dict = {}
download_lock = threading.Lock()

# Event loop reference – set on startup so background threads can emit events
_main_loop: Optional[asyncio.AbstractEventLoop] = None

# =========================
# Socket.IO (AsyncServer + ASGI)
# =========================
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    ping_timeout=60,
    ping_interval=25,
)


# =========================
# Application lifespan
# =========================
@asynccontextmanager
async def lifespan(application: FastAPI):
    global _main_loop
    _main_loop = asyncio.get_event_loop()

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()

    print("=" * 50)
    print("Video Downloader Server Starting (FastAPI)")
    print("=" * 50)
    print(f"Download folder: {DOWNLOAD_FOLDER}")
    print(f"Auto-delete: {AUTO_DELETE_ENABLED}")
    if AUTO_DELETE_ENABLED:
        print(f"Auto-delete after: {AUTO_DELETE_SECONDS} seconds")
    print("Docs available at: /docs")
    print("=" * 50)

    yield  # application runs here


# =========================
# FastAPI app
# =========================
fastapi_app = FastAPI(
    title="Video Downloader API",
    description="Download videos from YouTube and other platforms. "
                "Use /docs for interactive API documentation.",
    version="2.0.0",
    lifespan=lifespan,
)

_CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get('CORS_ORIGINS', '*').split(',')
    if o.strip()
] or ['*']

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)

templates = Jinja2Templates(directory="templates")

# Mount Socket.IO alongside FastAPI (explicit path so all other routes reach FastAPI)
app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path='/socket.io')


# =========================
# Thread-safe Socket.IO emit
# =========================
def _emit(event: str, data: dict, room: Optional[str] = None):
    """Emit a Socket.IO event from any thread."""
    if _main_loop is None:
        return
    coro = sio.emit(event, data, room=room) if room else sio.emit(event, data)
    asyncio.run_coroutine_threadsafe(coro, _main_loop)


# =========================
# Pydantic request models
import urllib.parse

# =========================
class URLRequest(BaseModel):
    url: str


class StartDownloadRequest(BaseModel):
    url: str
    format: Optional[str] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'


def _validate_url(url: str) -> str:
    """Validate that the URL is a safe http/https URL.

    Raises ValueError for anything that is not a plain http/https URL so
    that user-controlled strings cannot inject extra shell arguments when
    passed to yt-dlp via subprocess.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}'. Only http/https URLs are accepted.")
    if not parsed.netloc:
        raise ValueError("Invalid URL: missing host.")
    return url


# =========================
# Helpers
# =========================

# Player clients tried in order – tv_embedded bypasses most bot checks without cookies.
_YT_PLAYER_CLIENTS = [
    'tv_embedded',
    'ios',
    'android',
    'web_embedded',
    'web',
]


def _build_yt_dlp_base_args(player_client: str) -> list:
    """Return common yt-dlp flags for a given YouTube player client."""
    return [
        '--extractor-args', f'youtube:player_client={player_client}',
        '--user-agent',
        'Mozilla/5.0 (ChromiumStylePlatform) Cobalt/Version',
        '--add-header', 'Accept-Language:en-US,en;q=0.9',
        '--sleep-requests', '1',
        '--no-warnings',
    ]


def get_video_info(url: str) -> Optional[dict]:
    """Get comprehensive video information via yt-dlp.

    Tries multiple YouTube player clients in sequence so that if one is
    blocked by bot-detection the next one is attempted automatically.

    Raises ValueError for invalid URLs before any subprocess is launched.
    """
    _validate_url(url)  # raises ValueError on bad input
    last_error = ""
    for client in _YT_PLAYER_CLIENTS:
        try:
            result = subprocess.run(
                ['yt-dlp', '--dump-json', '--no-playlist']
                + _build_yt_dlp_base_args(client)
                + [url],
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout.strip().splitlines()[-1])
            last_error = (result.stderr or result.stdout or "").strip()
            print(f"[yt-dlp info] client={client} rc={result.returncode}: {last_error[:200]}")
        except subprocess.TimeoutExpired:
            last_error = f"Timeout with client={client}"
            print(f"[yt-dlp info] {last_error}")
        except Exception as e:
            last_error = str(e)
            print(f"[yt-dlp info] Exception with client={client}: {last_error}")

    print(f"Error getting video info after all clients: {last_error}")
    return None


def sanitize_filename(title: str) -> str:
    """Sanitize filename for cross-platform compatibility."""
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    title = re.sub(r'[\x00-\x1f\x7f-\x9f]', "", title)
    return title.strip()[:150] or "video"


# =========================
# Download worker (runs in a thread)
# =========================
def _try_download(download_id: str, url: str, output_path: str,
                  format_spec: str, cookies_file: Optional[str],
                  player_client: str) -> subprocess.Popen:
    """Build and launch a yt-dlp download process for a given player client."""
    cmd = (
        ['yt-dlp', '--no-playlist', '--newline', '--progress',
         '--merge-output-format', 'mp4']
        + _build_yt_dlp_base_args(player_client)
        + ['--retries', '10',
           '--fragment-retries', '10',
           '--no-abort-on-unavailable-fragments',
           '--concurrent-fragments', '4',
           '-f', format_spec,
           '-o', output_path,
           url]
    )
    if cookies_file:
        cmd.extend(['--cookies', cookies_file])
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def download_worker(download_id: str, url: str, output_path: str,
                    format_spec: str, cookies_file: Optional[str] = None):
    """Download worker – runs in a daemon thread, emits Socket.IO events.

    Tries multiple YouTube player clients so transient bot-detection errors
    are retried automatically with a different client.
    """

    with download_lock:
        downloads[download_id]['status'] = 'downloading'
        downloads[download_id]['start_time'] = time.time()

    last_error = "Unknown error"
    for client in _YT_PLAYER_CLIENTS:
        try:
            process = _try_download(download_id, url, output_path, format_spec,
                                    cookies_file, client)

            output_lines: list = []
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if not line:
                    continue

                output_lines.append(line)
                _emit('progress', {'id': download_id, 'line': line}, room=download_id)

                if '%' in line:
                    try:
                        percent = float(line.split('%')[0].split()[-1])
                        with download_lock:
                            downloads[download_id]['percent'] = percent
                    except Exception:
                        pass

                if 'ETA' in line:
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if 'iB/s' in part and i > 0:
                                with download_lock:
                                    downloads[download_id]['speed'] = parts[i - 1] + part
                            if part == 'ETA' and i < len(parts) - 1:
                                with download_lock:
                                    downloads[download_id]['eta'] = parts[i + 1]
                    except Exception:
                        pass

            process.wait()

            if process.returncode == 0:
                final_path = output_path.replace('%(ext)s', 'mp4')

                if not os.path.exists(final_path):
                    base_name = os.path.splitext(os.path.basename(output_path))[0]
                    for f in os.listdir(DOWNLOAD_FOLDER):
                        if f.startswith(base_name.replace('%(ext)s', '')):
                            final_path = os.path.join(DOWNLOAD_FOLDER, f)
                            break

                if os.path.exists(final_path):
                    file_size = os.path.getsize(final_path)

                    with download_lock:
                        downloads[download_id].update({
                            'status': 'completed',
                            'end_time': time.time(),
                            'file_path': final_path,
                            'file_size': file_size,
                            'percent': 100,
                        })

                    _emit('completed', {
                        'id': download_id,
                        'file_size': file_size,
                        'download_url': f'/download/{download_id}',
                        'stream_url': f'/stream/{download_id}',
                    }, room=download_id)

                    _emit('files_updated', {})
                    return  # success – exit worker
                else:
                    last_error = "Downloaded file not found on disk"
                    print(f"[download_worker] client={client} file missing after rc=0")
            else:
                last_error = '\n'.join(output_lines[-5:]) or f"rc={process.returncode}"
                print(f"[download_worker] client={client} failed rc={process.returncode}: {last_error[:200]}")

        except Exception as e:
            last_error = str(e)
            print(f"[download_worker] client={client} exception: {last_error}")

    # All clients exhausted
    print(f"Download failed after all clients: {last_error}")
    with download_lock:
        downloads[download_id]['status'] = 'failed'
        downloads[download_id]['error'] = last_error

    _emit('failed', {'id': download_id, 'error': last_error}, room=download_id)


# =========================
# Cleanup worker
# =========================
def cleanup_worker():
    """Auto-delete old files if AUTO_DELETE_ENABLED is set."""
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
                                _emit('files_updated', {})
                            except Exception as e:
                                print(f"Cleanup error: {e}")
        time.sleep(30)


# =========================
# Web UI
# =========================
@fastapi_app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# =========================
# File serving endpoints
# =========================
@fastapi_app.get(
    "/download/{download_id}",
    summary="Download completed video file",
    tags=["Files"],
)
async def download_file_by_id(download_id: str):
    """Download a completed video file by its download ID (mobile-friendly)."""
    with download_lock:
        download = downloads.get(download_id)

    if not download or download.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="Download not found or not completed")

    file_path = download.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(file_path)
    return FileResponse(
        path=file_path,
        media_type='video/mp4',
        filename=filename,
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        },
    )


@fastapi_app.get(
    "/stream/{download_id}",
    summary="Stream video file (supports range requests for iOS/Safari)",
    tags=["Files"],
)
async def stream_file(download_id: str, request: Request):
    """Stream a completed video file with HTTP range request support."""
    with download_lock:
        download = downloads.get(download_id)

    if not download or download.get('status') != 'completed':
        raise HTTPException(status_code=404, detail="Download not found or not completed")

    file_path = download.get('file_path')
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    range_header = request.headers.get('range')
    size = os.path.getsize(file_path)

    if not range_header:
        return FileResponse(file_path, media_type='video/mp4')

    byte_range = range_header.replace('bytes=', '').split('-')
    start = int(byte_range[0]) if byte_range[0] else 0
    end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else size - 1
    length = end - start + 1

    with open(file_path, 'rb') as f:
        f.seek(start)
        data = f.read(length)

    return Response(
        content=data,
        status_code=206,
        media_type='video/mp4',
        headers={
            'Content-Range': f'bytes {start}-{end}/{size}',
            'Accept-Ranges': 'bytes',
            'Content-Length': str(length),
        },
    )


# =========================
# API endpoints
# =========================
@fastapi_app.post(
    "/api/info",
    summary="Get video metadata",
    tags=["API"],
)
async def get_info(body: URLRequest):
    """Fetch title, thumbnail, duration and format count for a video URL."""
    try:
        info = get_video_info(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not info:
        raise HTTPException(status_code=400, detail="Could not fetch video information")

    return {
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'uploader': info.get('uploader'),
        'description': (info.get('description') or '')[:200],
        'formats_available': len(info.get('formats', [])),
        'best_quality': info.get('format'),
    }


@fastapi_app.post(
    "/api/formats",
    summary="List available download formats",
    tags=["API"],
)
async def get_formats(body: URLRequest):
    """Return all video and audio-only formats available for a URL."""
    try:
        info = get_video_info(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if not info:
        raise HTTPException(status_code=400, detail="Could not fetch video information")

    formats = []
    seen: set = set()

    for f in info.get('formats', []):
        if f.get('vcodec') != 'none':
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

    formats.sort(
        key=lambda x: int(re.search(r'\d+', x['resolution']).group())
        if re.search(r'\d+', x['resolution']) else 0,
        reverse=True,
    )

    audio_only = [
        {
            'format_id': f.get('format_id'),
            'ext': f.get('ext', 'mp3'),
            'abr': f.get('abr'),
            'filesize_mb': round(f.get('filesize', 0) / (1024 * 1024), 2) if f.get('filesize') else None,
        }
        for f in info.get('formats', [])
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none'
    ][:5]

    return {'formats': formats, 'audio_only': audio_only}


@fastapi_app.post(
    "/api/start_download",
    summary="Start a video download",
    tags=["API"],
)
async def start_download(body: StartDownloadRequest, background_tasks: BackgroundTasks):
    """Queue a video download and return a download_id to track progress via Socket.IO."""
    try:
        _validate_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    download_id = str(uuid.uuid4())

    info = get_video_info(body.url)
    title = info.get('title', f"video_{download_id[:8]}") if info else f"video_{download_id[:8]}"
    safe_title = sanitize_filename(title)
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}.%(ext)s")

    with download_lock:
        downloads[download_id] = {
            'id': download_id,
            'url': body.url,
            'title': safe_title,
            'status': 'queued',
            'percent': 0,
            'output_template': output_template,
            'created_at': datetime.now().isoformat(),
            'format_spec': body.format,
        }

    thread = threading.Thread(
        target=download_worker,
        args=(download_id, body.url, output_template, body.format, None),
        daemon=True,
    )
    thread.start()

    return {'download_id': download_id, 'title': safe_title, 'status': 'queued'}


@fastapi_app.get(
    "/api/status/{download_id}",
    summary="Get download status",
    tags=["API"],
)
async def get_status(download_id: str):
    """Poll the status of a specific download."""
    with download_lock:
        download = dict(downloads.get(download_id, {}))

    if not download:
        raise HTTPException(status_code=404, detail="Download not found")

    if download.get('status') == 'completed':
        download['download_url'] = f'/download/{download_id}'
        download['stream_url'] = f'/stream/{download_id}'

    return download


@fastapi_app.get(
    "/api/downloads",
    summary="List all downloads",
    tags=["API"],
)
async def list_downloads():
    """Return metadata for all tracked downloads."""
    with download_lock:
        download_list = [dict(d) for d in downloads.values()]

    for download in download_list:
        if download.get('status') == 'completed':
            did = download['id']
            download['download_url'] = f'/download/{did}'
            download['stream_url'] = f'/stream/{did}'

    return download_list


@fastapi_app.delete(
    "/api/delete/{download_id}",
    summary="Delete a download",
    tags=["API"],
)
async def delete_download(download_id: str):
    """Delete a download record and its associated file."""
    with download_lock:
        download = downloads.get(download_id)
        if not download:
            raise HTTPException(status_code=404, detail="Download not found")

        file_path = download.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                raise HTTPException(status_code=500, detail="Failed to delete file")

        del downloads[download_id]

    _emit('files_updated', {})
    return {'success': True}


@fastapi_app.get(
    "/api/config",
    summary="Server configuration",
    tags=["API"],
)
async def get_config():
    """Return current server configuration."""
    return {
        'auto_delete_enabled': AUTO_DELETE_ENABLED,
        'auto_delete_seconds': AUTO_DELETE_SECONDS,
        'max_file_size_gb': MAX_FILE_SIZE_BYTES / (1024 * 1024 * 1024),
    }


@fastapi_app.get(
    "/api/ping",
    summary="Connectivity ping",
    tags=["System"],
)
async def ping():
    """Simple ping endpoint for connectivity checks."""
    return {'pong': True}


@fastapi_app.get(
    "/health",
    summary="Health check",
    tags=["System"],
)
async def health_check():
    """Returns server health and download statistics."""
    return {
        'status': 'healthy',
        'active_downloads': sum(
            1 for d in downloads.values() if d.get('status') in ('queued', 'downloading')
        ),
        'total_downloads': len(downloads),
    }


# =========================
# Socket.IO events
# =========================
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")
    await sio.emit('connected', {'sid': sid}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")


@sio.event
async def subscribe(sid, data):
    """Subscribe to progress events for a specific download_id."""
    download_id = data.get('download_id') if isinstance(data, dict) else None
    if not download_id:
        return

    await sio.enter_room(sid, download_id)
    await sio.emit('subscribed', {'id': download_id}, to=sid)

    with download_lock:
        download = dict(downloads.get(download_id, {}))

    if download:
        await sio.emit('status_update', download, to=sid)


# =========================
# Entry point (direct execution)
# =========================
if __name__ == '__main__':
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get('PORT', 5000)),
        reload=os.environ.get('DEBUG', 'false').lower() == 'true',
    )
