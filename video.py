import os
import re
import subprocess
import threading
import time
import uuid

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'thisisjustthestart'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

downloads = {}

AUTO_DELETE_SECONDS = 60


# =========================
# File serving (browser safe)
# =========================
@app.route('/downloads/<path:filename>')
def download_file(filename):
    response = send_from_directory(
        DOWNLOAD_FOLDER,
        filename,
        as_attachment=True
    )
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# =========================
# Helpers
# =========================
def get_video_title(url):
    try:
        result = subprocess.run(
            ['yt-dlp', '--get-title', '--no-playlist', url],
            capture_output=True, text=True, check=True, timeout=30
        )
        return result.stdout.strip()
    except:
        return None


def sanitize_filename(title):
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title.strip()[:150]


# =========================
# Download worker
# =========================
def download_worker(download_id, url, output_path, format_spec, cookies_file):
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '--newline',
        '--progress',
        '--merge-output-format', 'mp4',
        '--user-agent', 'Mozilla/5.0',
        '--referer', 'https://www.youtube.com/',
        '-f', format_spec,
        '-o', output_path,
        url
    ]

    if cookies_file:
        cmd.extend(['--cookies', cookies_file])

    downloads[download_id]['status'] = 'downloading'
    downloads[download_id]['start_time'] = time.time()

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
            socketio.emit('progress', {
                'id': download_id,
                'line': line
            }, room=download_id)

            if '%' in line:
                try:
                    percent = float(line.split('%')[0].split()[-1])
                    downloads[download_id]['percent'] = percent
                except:
                    pass

    process.wait()

    if process.returncode == 0:
        downloads[download_id]['status'] = 'completed'
        downloads[download_id]['end_time'] = time.time()

        # store final file path (mp4)
        final_path = output_path.replace('%(ext)s', 'mp4')
        downloads[download_id]['file_path'] = final_path

        socketio.emit('completed', {'id': download_id}, room=download_id)

        with app.app_context():
            socketio.emit('files_updated', broadcast=True)
    else:
        downloads[download_id]['status'] = 'failed'
        socketio.emit('failed', {'id': download_id}, room=download_id)


# =========================
# Cleanup worker (auto delete)
# =========================
def cleanup_worker():
    while True:
        now = time.time()

        for download_id, data in list(downloads.items()):
            if data.get('status') == 'completed':
                end_time = data.get('end_time')
                file_path = data.get('file_path')

                if end_time and (now - end_time > AUTO_DELETE_SECONDS):
                    try:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                            print(f"Deleted: {file_path}")

                        del downloads[download_id]

                        with app.app_context():
                            socketio.emit('files_updated', broadcast=True)

                    except Exception as e:
                        print(f"Cleanup error: {e}")

        time.sleep(10)


# =========================
# Routes
# =========================
@app.route('/')
def index():
    return render_template('index_simple.html')


@app.route('/start_download', methods=['POST'])
def start_download():
    url = request.form['url']
    format_spec = request.form.get('format', 'bestvideo+bestaudio/best')
    cookies = request.form.get('cookies') or None

    download_id = str(uuid.uuid4())

    title = get_video_title(url)
    if not title:
        title = f"video_{download_id[:8]}"

    safe_title = sanitize_filename(title)
    output_template = os.path.join(DOWNLOAD_FOLDER, f"{safe_title}.%(ext)s")

    downloads[download_id] = {
        'url': url,
        'title': safe_title,
        'status': 'queued',
        'percent': 0,
        'output_template': output_template
    }

    thread = threading.Thread(
        target=download_worker,
        args=(download_id, url, output_template, format_spec, cookies)
    )
    thread.daemon = True
    thread.start()

    return jsonify({'download_id': download_id})


@app.route('/status/<download_id>')
def get_status(download_id):
    return jsonify(downloads.get(download_id, {}))


@app.route('/files')
def list_files():
    files = []

    for f in os.listdir(DOWNLOAD_FOLDER):
        full = os.path.join(DOWNLOAD_FOLDER, f)

        if os.path.isfile(full):
            files.append({
                'name': f,
                'size': os.path.getsize(full),
                'modified': os.path.getmtime(full),
                'path': full
            })

    files.sort(key=lambda x: x['modified'], reverse=True)
    return jsonify(files)


@app.route('/active_downloads')
def active_downloads():
    count = sum(
        1 for d in downloads.values()
        if d.get('status') in ('queued', 'downloading')
    )
    return jsonify({'count': count})


# =========================
# Socket.IO
# =========================
@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('subscribe')
def handle_subscribe(data):
    download_id = data.get('download_id')

    if download_id:
        join_room(download_id)
        emit('subscribed', {'id': download_id})


# =========================
# Start app
# =========================
if __name__ == '__main__':
    # start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_worker)
    cleanup_thread.daemon = True
    cleanup_thread.start()

    socketio.run(app, debug=True)
