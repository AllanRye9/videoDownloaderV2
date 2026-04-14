# Mobile API Documentation

Complete API reference for integrating the Video Downloader backend with iOS and Android native applications.

## Base URL
```
https://your-server.com
```

## Authentication
Currently, no authentication is required. For production, consider adding API keys or JWT tokens.

---

## REST API Endpoints

### 1. Get Video Information

Fetch metadata about a video before downloading.

**Endpoint:** `POST /api/info`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (200 OK):**
```json
{
  "title": "Rick Astley - Never Gonna Give You Up",
  "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
  "duration": 212,
  "uploader": "Rick Astley",
  "description": "The official video for...",
  "formats_available": 20,
  "best_quality": "1080p"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "URL is required"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "Could not fetch video information"
}
```

**Example (iOS - Swift):**
```swift
struct VideoInfoRequest: Codable {
    let url: String
}

struct VideoInfo: Codable {
    let title: String
    let thumbnail: String
    let duration: Int
    let uploader: String
    let description: String
    let formatsAvailable: Int
    let bestQuality: String
    
    enum CodingKeys: String, CodingKey {
        case title, thumbnail, duration, uploader, description
        case formatsAvailable = "formats_available"
        case bestQuality = "best_quality"
    }
}

func fetchVideoInfo(url: String) async throws -> VideoInfo {
    let endpoint = URL(string: "https://your-server.com/api/info")!
    var request = URLRequest(url: endpoint)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let body = VideoInfoRequest(url: url)
    request.httpBody = try JSONEncoder().encode(body)
    
    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode(VideoInfo.self, from: data)
}
```

**Example (Android - Kotlin):**
```kotlin
data class VideoInfoRequest(val url: String)

data class VideoInfo(
    val title: String,
    val thumbnail: String,
    val duration: Int,
    val uploader: String,
    val description: String,
    @SerializedName("formats_available") val formatsAvailable: Int,
    @SerializedName("best_quality") val bestQuality: String
)

suspend fun fetchVideoInfo(url: String): VideoInfo {
    val client = OkHttpClient()
    val json = JSONObject().apply {
        put("url", url)
    }
    
    val requestBody = json.toString().toRequestBody("application/json".toMediaType())
    val request = Request.Builder()
        .url("https://your-server.com/api/info")
        .post(requestBody)
        .build()
    
    val response = client.newCall(request).execute()
    val responseBody = response.body?.string() ?: throw Exception("Empty response")
    
    return Gson().fromJson(responseBody, VideoInfo::class.java)
}
```

---

### 2. Get Available Formats

Retrieve all available download formats and qualities.

**Endpoint:** `POST /api/formats`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (200 OK):**
```json
{
  "formats": [
    {
      "format_id": "137",
      "resolution": "1080p",
      "ext": "mp4",
      "filesize": 131428352,
      "filesize_mb": 125.35,
      "fps": 30,
      "vcodec": "avc1.640028",
      "acodec": "mp4a.40.2"
    },
    {
      "format_id": "136",
      "resolution": "720p",
      "ext": "mp4",
      "filesize": 65714176,
      "filesize_mb": 62.67,
      "fps": 30,
      "vcodec": "avc1.4d401f",
      "acodec": "mp4a.40.2"
    }
  ],
  "audio_only": [
    {
      "format_id": "140",
      "ext": "m4a",
      "abr": 128,
      "filesize_mb": 3.2
    }
  ]
}
```

**Example (iOS):**
```swift
struct VideoFormat: Codable {
    let formatId: String
    let resolution: String
    let ext: String
    let filesize: Int?
    let filesizeMb: Double?
    let fps: Int?
    let vcodec: String?
    let acodec: String?
    
    enum CodingKeys: String, CodingKey {
        case formatId = "format_id"
        case resolution, ext, filesize
        case filesizeMb = "filesize_mb"
        case fps, vcodec, acodec
    }
}

struct FormatsResponse: Codable {
    let formats: [VideoFormat]
    let audioOnly: [AudioFormat]
    
    enum CodingKeys: String, CodingKey {
        case formats
        case audioOnly = "audio_only"
    }
}
```

---

### 3. Start Download

Initiate a video download with optional format selection.

**Endpoint:** `POST /api/start_download`

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "137+bestaudio/best"
}
```

**Format Options:**
- `"best"` - Best available quality (default)
- `"bestvideo+bestaudio"` - Best video + best audio, merged
- `"137+bestaudio"` - Specific format ID + best audio
- `"worst"` - Lowest quality (for testing)

**Response (200 OK):**
```json
{
  "download_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Rick Astley - Never Gonna Give You Up",
  "status": "queued"
}
```

**Example (iOS):**
```swift
struct DownloadRequest: Codable {
    let url: String
    let format: String
}

struct DownloadResponse: Codable {
    let downloadId: String
    let title: String
    let status: String
    
    enum CodingKeys: String, CodingKey {
        case downloadId = "download_id"
        case title, status
    }
}

func startDownload(url: String, format: String = "best") async throws -> DownloadResponse {
    let endpoint = URL(string: "https://your-server.com/api/start_download")!
    var request = URLRequest(url: endpoint)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    
    let body = DownloadRequest(url: url, format: format)
    request.httpBody = try JSONEncoder().encode(body)
    
    let (data, _) = try await URLSession.shared.data(for: request)
    return try JSONDecoder().decode(DownloadResponse.self, from: data)
}
```

---

### 4. Get Download Status

Poll for download progress and completion.

**Endpoint:** `GET /api/status/{download_id}`

**Response (200 OK) - Downloading:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "url": "https://www.youtube.com/watch?v=...",
  "title": "Rick Astley - Never Gonna Give You Up",
  "status": "downloading",
  "percent": 45.5,
  "speed": "2.5MiB/s",
  "eta": "00:23",
  "created_at": "2024-04-13T10:30:00",
  "format_spec": "137+bestaudio/best"
}
```

**Response (200 OK) - Completed:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Rick Astley - Never Gonna Give You Up",
  "status": "completed",
  "percent": 100,
  "file_path": "downloads/Rick Astley - Never Gonna Give You Up.mp4",
  "file_size": 131428352,
  "download_url": "/download/550e8400-e29b-41d4-a716-446655440000",
  "stream_url": "/stream/550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-04-13T10:30:00",
  "end_time": 1713006045.123
}
```

**Status Values:**
- `queued` - Waiting to start
- `downloading` - In progress
- `completed` - Ready for download
- `failed` - Error occurred

**Example (iOS) - Polling:**
```swift
func pollDownloadStatus(downloadId: String) async throws -> DownloadStatus {
    let endpoint = URL(string: "https://your-server.com/api/status/\(downloadId)")!
    let (data, _) = try await URLSession.shared.data(from: endpoint)
    return try JSONDecoder().decode(DownloadStatus.self, from: data)
}

// Poll every 2 seconds
func monitorDownload(downloadId: String) async {
    while true {
        if let status = try? await pollDownloadStatus(downloadId: downloadId) {
            if status.status == "completed" {
                // Download file
                break
            } else if status.status == "failed" {
                // Handle error
                break
            }
            // Update UI with progress
            print("Progress: \(status.percent)%")
        }
        try? await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
    }
}
```

---

### 5. Download File

Download the completed file to device.

**Endpoint:** `GET /download/{download_id}`

**Response:** Binary file with headers:
```
Content-Type: video/mp4
Content-Disposition: attachment; filename="video_title.mp4"
Cache-Control: no-cache
```

**Example (iOS) - Download to Files App:**
```swift
func downloadFile(downloadId: String, title: String) async throws -> URL {
    let endpoint = URL(string: "https://your-server.com/download/\(downloadId)")!
    let (localURL, _) = try await URLSession.shared.download(from: endpoint)
    
    // Move to Documents directory
    let documentsPath = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    let destinationURL = documentsPath.appendingPathComponent("\(title).mp4")
    
    try? FileManager.default.removeItem(at: destinationURL)
    try FileManager.default.moveItem(at: localURL, to: destinationURL)
    
    return destinationURL
}
```

**Example (Android) - Download with DownloadManager:**
```kotlin
fun downloadFile(context: Context, downloadId: String, title: String) {
    val downloadManager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
    val uri = Uri.parse("https://your-server.com/download/$downloadId")
    
    val request = DownloadManager.Request(uri).apply {
        setTitle(title)
        setDescription("Downloading video...")
        setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "$title.mp4")
        setMimeType("video/mp4")
    }
    
    downloadManager.enqueue(request)
}
```

---

### 6. Stream File (iOS Optimized)

Stream video with Range request support for iOS video player.

**Endpoint:** `GET /stream/{download_id}`

**Headers:**
```
Range: bytes=0-1024
```

**Response:** Partial content (206) with Range support

**Example (iOS) - Play in AVPlayer:**
```swift
import AVKit

func playVideo(downloadId: String) {
    let url = URL(string: "https://your-server.com/stream/\(downloadId)")!
    let player = AVPlayer(url: url)
    let playerViewController = AVPlayerViewController()
    playerViewController.player = player
    
    // Present player
    present(playerViewController, animated: true) {
        player.play()
    }
}
```

---

### 7. List All Downloads

Get all downloads for the current session.

**Endpoint:** `GET /api/downloads`

**Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Video Title",
    "status": "completed",
    "percent": 100,
    "file_size": 131428352,
    "download_url": "/download/550e8400-e29b-41d4-a716-446655440000",
    "stream_url": "/stream/550e8400-e29b-41d4-a716-446655440000"
  },
  {
    "id": "660f9511-f3ac-52e5-b827-557766551111",
    "title": "Another Video",
    "status": "downloading",
    "percent": 67.3
  }
]
```

---

### 8. Delete Download

Manually delete a completed download.

**Endpoint:** `DELETE /api/delete/{download_id}`

**Response (200 OK):**
```json
{
  "success": true
}
```

**Error Response (404 Not Found):**
```json
{
  "error": "Download not found"
}
```

**Example (iOS):**
```swift
func deleteDownload(downloadId: String) async throws {
    let endpoint = URL(string: "https://your-server.com/api/delete/\(downloadId)")!
    var request = URLRequest(url: endpoint)
    request.httpMethod = "DELETE"
    
    let (data, response) = try await URLSession.shared.data(for: request)
    
    guard let httpResponse = response as? HTTPURLResponse,
          httpResponse.statusCode == 200 else {
        throw URLError(.badServerResponse)
    }
}
```

---

### 9. Get Server Configuration

Retrieve server settings.

**Endpoint:** `GET /api/config`

**Response (200 OK):**
```json
{
  "auto_delete_enabled": false,
  "auto_delete_seconds": 3600,
  "max_file_size_gb": 5
}
```

---

### 10. Health Check

Check server status.

**Endpoint:** `GET /health`

**Response (200 OK):**
```json
{
  "status": "healthy",
  "active_downloads": 2,
  "total_downloads": 15
}
```

---

## WebSocket API (Real-time Updates)

For real-time progress updates, use Socket.IO.

### Connection

**Endpoint:** `wss://your-server.com/socket.io/`

**Example (iOS) - Using SocketIO-Client-Swift:**
```swift
import SocketIO

class DownloadManager {
    let manager = SocketManager(socketURL: URL(string: "https://your-server.com")!)
    var socket: SocketIOClient!
    
    init() {
        socket = manager.defaultSocket
        
        socket.on(clientEvent: .connect) { data, ack in
            print("Socket connected")
        }
        
        socket.on("progress") { data, ack in
            if let progressData = data[0] as? [String: Any],
               let downloadId = progressData["id"] as? String,
               let line = progressData["line"] as? String {
                print("Progress for \(downloadId): \(line)")
            }
        }
        
        socket.on("completed") { data, ack in
            if let completedData = data[0] as? [String: Any],
               let downloadId = completedData["id"] as? String {
                print("Download completed: \(downloadId)")
            }
        }
        
        socket.on("failed") { data, ack in
            if let failedData = data[0] as? [String: Any],
               let downloadId = failedData["id"] as? String,
               let error = failedData["error"] as? String {
                print("Download failed: \(downloadId) - \(error)")
            }
        }
        
        socket.connect()
    }
    
    func subscribe(to downloadId: String) {
        socket.emit("subscribe", ["download_id": downloadId])
    }
}
```

**Example (Android) - Using Socket.IO-client Java:**
```kotlin
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject

class DownloadManager {
    private lateinit var socket: Socket
    
    fun connect() {
        socket = IO.socket("https://your-server.com")
        
        socket.on(Socket.EVENT_CONNECT) {
            println("Socket connected")
        }
        
        socket.on("progress") { args ->
            val data = args[0] as JSONObject
            val downloadId = data.getString("id")
            val line = data.getString("line")
            println("Progress for $downloadId: $line")
        }
        
        socket.on("completed") { args ->
            val data = args[0] as JSONObject
            val downloadId = data.getString("id")
            println("Download completed: $downloadId")
        }
        
        socket.on("failed") { args ->
            val data = args[0] as JSONObject
            val downloadId = data.getString("id")
            val error = data.getString("error")
            println("Download failed: $downloadId - $error")
        }
        
        socket.connect()
    }
    
    fun subscribe(downloadId: String) {
        val data = JSONObject().apply {
            put("download_id", downloadId)
        }
        socket.emit("subscribe", data)
    }
}
```

### Events

**Client → Server:**

- `subscribe` - Subscribe to download updates
  ```json
  {
    "download_id": "550e8400-e29b-41d4-a716-446655440000"
  }
  ```

**Server → Client:**

- `connected` - Connection established
  ```json
  {
    "sid": "socket_session_id"
  }
  ```

- `subscribed` - Subscription confirmed
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000"
  }
  ```

- `progress` - Download progress update
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "line": "[download]  45.5% of 125.35MiB at 2.5MiB/s ETA 00:23"
  }
  ```

- `completed` - Download finished
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "file_size": 131428352,
    "download_url": "/download/550e8400-e29b-41d4-a716-446655440000",
    "stream_url": "/stream/550e8400-e29b-41d4-a716-446655440000"
  }
  ```

- `failed` - Download error
  ```json
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "error": "Video unavailable"
  }
  ```

- `files_updated` - Download list changed (broadcast to all clients)

---

## Complete iOS Example

```swift
import Foundation
import SocketIO

class VideoDownloaderService {
    static let shared = VideoDownloaderService()
    
    private let baseURL = "https://your-server.com"
    private let manager: SocketManager
    private let socket: SocketIOClient
    
    var onProgress: ((String, String) -> Void)?
    var onCompleted: ((String) -> Void)?
    var onFailed: ((String, String) -> Void)?
    
    private init() {
        manager = SocketManager(socketURL: URL(string: baseURL)!)
        socket = manager.defaultSocket
        setupSocketHandlers()
        socket.connect()
    }
    
    private func setupSocketHandlers() {
        socket.on("progress") { [weak self] data, ack in
            guard let progressData = data[0] as? [String: Any],
                  let id = progressData["id"] as? String,
                  let line = progressData["line"] as? String else { return }
            self?.onProgress?(id, line)
        }
        
        socket.on("completed") { [weak self] data, ack in
            guard let completedData = data[0] as? [String: Any],
                  let id = completedData["id"] as? String else { return }
            self?.onCompleted?(id)
        }
        
        socket.on("failed") { [weak self] data, ack in
            guard let failedData = data[0] as? [String: Any],
                  let id = failedData["id"] as? String,
                  let error = failedData["error"] as? String else { return }
            self?.onFailed?(id, error)
        }
    }
    
    func downloadVideo(url: String, quality: String = "best") async throws -> String {
        // Start download
        let downloadResponse = try await startDownload(url: url, format: quality)
        
        // Subscribe to updates
        socket.emit("subscribe", ["download_id": downloadResponse.downloadId])
        
        return downloadResponse.downloadId
    }
    
    private func startDownload(url: String, format: String) async throws -> DownloadResponse {
        let endpoint = URL(string: "\(baseURL)/api/start_download")!
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["url": url, "format": format]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(DownloadResponse.self, from: data)
    }
    
    func getVideoInfo(url: String) async throws -> VideoInfo {
        let endpoint = URL(string: "\(baseURL)/api/info")!
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["url": url]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        
        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(VideoInfo.self, from: data)
    }
}
```

---

## Complete Android Example

```kotlin
import okhttp3.*
import com.google.gson.Gson
import io.socket.client.IO
import io.socket.client.Socket

class VideoDownloaderService(private val baseUrl: String = "https://your-server.com") {
    private val client = OkHttpClient()
    private val gson = Gson()
    private val socket: Socket = IO.socket(baseUrl)
    
    var onProgress: ((String, String) -> Unit)? = null
    var onCompleted: ((String) -> Unit)? = null
    var onFailed: ((String, String) -> Unit)? = null
    
    init {
        setupSocketHandlers()
        socket.connect()
    }
    
    private fun setupSocketHandlers() {
        socket.on("progress") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            val line = data.getString("line")
            onProgress?.invoke(id, line)
        }
        
        socket.on("completed") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            onCompleted?.invoke(id)
        }
        
        socket.on("failed") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            val error = data.getString("error")
            onFailed?.invoke(id, error)
        }
    }
    
    suspend fun downloadVideo(url: String, quality: String = "best"): String {
        val json = JSONObject().apply {
            put("url", url)
            put("format", quality)
        }
        
        val requestBody = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("$baseUrl/api/start_download")
            .post(requestBody)
            .build()
        
        val response = client.newCall(request).execute()
        val downloadResponse = gson.fromJson(response.body?.string(), DownloadResponse::class.java)
        
        // Subscribe to updates
        socket.emit("subscribe", JSONObject().apply {
            put("download_id", downloadResponse.downloadId)
        })
        
        return downloadResponse.downloadId
    }
    
    suspend fun getVideoInfo(url: String): VideoInfo {
        val json = JSONObject().apply {
            put("url", url)
        }
        
        val requestBody = json.toString().toRequestBody("application/json".toMediaType())
        val request = Request.Builder()
            .url("$baseUrl/api/info")
            .post(requestBody)
            .build()
        
        val response = client.newCall(request).execute()
        return gson.fromJson(response.body?.string(), VideoInfo::class.java)
    }
}
```

---

## Rate Limiting

Currently no rate limiting is implemented. For production, consider:

- Max 10 concurrent downloads per IP
- Max 100 requests per hour per IP
- Max 5 GB total downloads per day per IP

---

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid URL, missing parameters) |
| 404 | Download not found |
| 500 | Server error (download failed, yt-dlp error) |

---

## Best Practices

1. **Always check video info before downloading** to show file size to users
2. **Use WebSocket for progress updates** instead of polling
3. **Handle errors gracefully** with user-friendly messages
4. **Implement retry logic** for failed downloads
5. **Cache video info** to avoid repeated API calls
6. **Show file size** before download to prevent surprises
7. **Use /stream endpoint** for iOS video preview
8. **Implement background downloads** for better UX

---

## Support

For issues or questions:
- Check the main README.md
- Review code examples above
- Test with Postman or curl first
- Check server logs for errors

---

Last Updated: 2024-04-13
