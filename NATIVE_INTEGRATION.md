# Native Mobile App Integration Guide

Complete guide for integrating the Video Downloader backend with native iOS and Android applications.

## 📱 iOS Integration (Swift)

### Step 1: Install Dependencies

Add to your `Podfile`:
```ruby
pod 'SocketIO', '~> 16.0'
pod 'Alamofire', '~> 5.8'
```

Then run:
```bash
pod install
```

### Step 2: Create Download Service

Create a new Swift file `VideoDownloaderService.swift`:

```swift
import Foundation
import SocketIO
import Alamofire

class VideoDownloaderService: ObservableObject {
    static let shared = VideoDownloaderService()
    
    private let baseURL = "https://your-server.com"
    private let manager: SocketManager
    private let socket: SocketIOClient
    
    @Published var downloads: [Download] = []
    @Published var activeDownloadId: String?
    @Published var progress: Double = 0
    @Published var downloadSpeed: String = ""
    
    private init() {
        manager = SocketManager(
            socketURL: URL(string: baseURL)!,
            config: [.log(true), .compress]
        )
        socket = manager.defaultSocket
        setupSocketHandlers()
        socket.connect()
    }
    
    private func setupSocketHandlers() {
        socket.on(clientEvent: .connect) { [weak self] data, ack in
            print("✅ Socket connected")
        }
        
        socket.on("progress") { [weak self] data, ack in
            guard let progressData = data[0] as? [String: Any],
                  let id = progressData["id"] as? String,
                  let line = progressData["line"] as? String else { return }
            
            self?.parseProgress(id: id, line: line)
        }
        
        socket.on("completed") { [weak self] data, ack in
            guard let completedData = data[0] as? [String: Any],
                  let id = completedData["id"] as? String else { return }
            
            self?.handleCompleted(id: id)
        }
        
        socket.on("failed") { [weak self] data, ack in
            guard let failedData = data[0] as? [String: Any],
                  let id = failedData["id"] as? String,
                  let error = failedData["error"] as? String else { return }
            
            self?.handleFailed(id: id, error: error)
        }
    }
    
    private func parseProgress(id: String, line: String) {
        // Parse percentage
        if let percentMatch = line.range(of: #"\d+\.\d+%"#, options: .regularExpression) {
            let percentString = String(line[percentMatch]).replacingOccurrences(of: "%", with: "")
            if let percent = Double(percentString) {
                DispatchQueue.main.async {
                    self.progress = percent / 100.0
                }
            }
        }
        
        // Parse speed
        if let speedMatch = line.range(of: #"\d+\.\d+[KMG]iB/s"#, options: .regularExpression) {
            let speed = String(line[speedMatch])
            DispatchQueue.main.async {
                self.downloadSpeed = speed
            }
        }
    }
    
    private func handleCompleted(id: String) {
        DispatchQueue.main.async {
            self.progress = 1.0
            self.activeDownloadId = nil
            // Trigger download to device
            self.downloadFileToDevice(id: id)
        }
    }
    
    private func handleFailed(id: String, error: String) {
        DispatchQueue.main.async {
            self.activeDownloadId = nil
            // Show error to user
            print("❌ Download failed: \(error)")
        }
    }
    
    // MARK: - Public Methods
    
    func getVideoInfo(url: String) async throws -> VideoInfo {
        let parameters: [String: Any] = ["url": url]
        
        let response = try await AF.request(
            "\(baseURL)/api/info",
            method: .post,
            parameters: parameters,
            encoding: JSONEncoding.default
        ).serializingDecodable(VideoInfo.self).value
        
        return response
    }
    
    func getFormats(url: String) async throws -> FormatsResponse {
        let parameters: [String: Any] = ["url": url]
        
        let response = try await AF.request(
            "\(baseURL)/api/formats",
            method: .post,
            parameters: parameters,
            encoding: JSONEncoding.default
        ).serializingDecodable(FormatsResponse.self).value
        
        return response
    }
    
    func startDownload(url: String, format: String = "best") async throws -> String {
        let parameters: [String: Any] = [
            "url": url,
            "format": format
        ]
        
        let response = try await AF.request(
            "\(baseURL)/api/start_download",
            method: .post,
            parameters: parameters,
            encoding: JSONEncoding.default
        ).serializingDecodable(DownloadResponse.self).value
        
        // Subscribe to updates
        socket.emit("subscribe", ["download_id": response.downloadId])
        
        DispatchQueue.main.async {
            self.activeDownloadId = response.downloadId
            self.progress = 0
        }
        
        return response.downloadId
    }
    
    func downloadFileToDevice(id: String) {
        let destination: DownloadRequest.Destination = { _, _ in
            let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            let fileURL = documentsURL.appendingPathComponent("\(id).mp4")
            return (fileURL, [.removePreviousFile, .createIntermediateDirectories])
        }
        
        AF.download("\(baseURL)/download/\(id)", to: destination)
            .downloadProgress { progress in
                print("Download Progress: \(progress.fractionCompleted)")
            }
            .response { response in
                if response.error == nil, let filePath = response.fileURL?.path {
                    print("✅ File downloaded to: \(filePath)")
                    // Save to Photos library if it's a video
                    self.saveToPhotos(url: response.fileURL!)
                }
            }
    }
    
    private func saveToPhotos(url: URL) {
        UISaveVideoAtPathToSavedPhotosAlbum(
            url.path,
            self,
            #selector(videoSaved(_:didFinishSavingWithError:contextInfo:)),
            nil
        )
    }
    
    @objc private func videoSaved(_ video: String, didFinishSavingWithError error: Error?, contextInfo: UnsafeRawPointer) {
        if let error = error {
            print("❌ Error saving video: \(error.localizedDescription)")
        } else {
            print("✅ Video saved to Photos")
        }
    }
}

// MARK: - Models

struct VideoInfo: Codable {
    let title: String
    let thumbnail: String
    let duration: Int
    let uploader: String
    let description: String
    let formatsAvailable: Int
    
    enum CodingKeys: String, CodingKey {
        case title, thumbnail, duration, uploader, description
        case formatsAvailable = "formats_available"
    }
}

struct VideoFormat: Codable {
    let formatId: String
    let resolution: String
    let ext: String
    let filesizeMb: Double?
    
    enum CodingKeys: String, CodingKey {
        case formatId = "format_id"
        case resolution, ext
        case filesizeMb = "filesize_mb"
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

struct AudioFormat: Codable {
    let formatId: String
    let ext: String
    let abr: Int?
    
    enum CodingKeys: String, CodingKey {
        case formatId = "format_id"
        case ext, abr
    }
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

struct Download: Identifiable {
    let id: String
    let title: String
    var status: String
    var progress: Double
}
```

### Step 3: Create SwiftUI View

Create `DownloadView.swift`:

```swift
import SwiftUI

struct DownloadView: View {
    @StateObject private var service = VideoDownloaderService.shared
    @State private var url: String = ""
    @State private var videoInfo: VideoInfo?
    @State private var isLoading = false
    @State private var showError = false
    @State private var errorMessage = ""
    
    var body: some View {
        NavigationView {
            VStack(spacing: 20) {
                // URL Input
                VStack(alignment: .leading) {
                    Text("Video URL")
                        .font(.headline)
                    
                    TextField("Paste video URL here...", text: $url)
                        .textFieldStyle(RoundedBorderTextFieldStyle())
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                    
                    Button(action: fetchInfo) {
                        if isLoading {
                            ProgressView()
                        } else {
                            Text("Get Video Info")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(url.isEmpty || isLoading)
                }
                .padding()
                
                // Video Info Card
                if let info = videoInfo {
                    VStack(alignment: .leading, spacing: 12) {
                        AsyncImage(url: URL(string: info.thumbnail)) { image in
                            image.resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            ProgressView()
                        }
                        .frame(height: 200)
                        .clipped()
                        .cornerRadius(12)
                        
                        Text(info.title)
                            .font(.headline)
                        
                        HStack {
                            Label(info.uploader, systemImage: "person.fill")
                            Spacer()
                            Label(formatDuration(info.duration), systemImage: "clock")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                        
                        Button(action: startDownload) {
                            Label("Download Video", systemImage: "arrow.down.circle.fill")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.large)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(16)
                    .padding(.horizontal)
                }
                
                // Download Progress
                if service.activeDownloadId != nil {
                    VStack(spacing: 12) {
                        Text("Downloading...")
                            .font(.headline)
                        
                        ProgressView(value: service.progress)
                            .progressViewStyle(.linear)
                        
                        HStack {
                            Text("\(Int(service.progress * 100))%")
                            Spacer()
                            Text(service.downloadSpeed)
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(16)
                    .padding(.horizontal)
                }
                
                Spacer()
            }
            .navigationTitle("Video Downloader")
            .alert("Error", isPresented: $showError) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(errorMessage)
            }
        }
    }
    
    private func fetchInfo() {
        isLoading = true
        Task {
            do {
                let info = try await service.getVideoInfo(url: url)
                await MainActor.run {
                    self.videoInfo = info
                    self.isLoading = false
                }
            } catch {
                await MainActor.run {
                    self.errorMessage = error.localizedDescription
                    self.showError = true
                    self.isLoading = false
                }
            }
        }
    }
    
    private func startDownload() {
        Task {
            do {
                _ = try await service.startDownload(url: url)
            } catch {
                await MainActor.run {
                    self.errorMessage = error.localizedDescription
                    self.showError = true
                }
            }
        }
    }
    
    private func formatDuration(_ seconds: Int) -> String {
        let hours = seconds / 3600
        let minutes = (seconds % 3600) / 60
        let secs = seconds % 60
        
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        }
        return String(format: "%d:%02d", minutes, secs)
    }
}
```

### Step 4: Configure Info.plist

Add these permissions:

```xml
<key>NSPhotoLibraryAddUsageDescription</key>
<string>We need access to save downloaded videos to your Photos library</string>

<key>NSPhotoLibraryUsageDescription</key>
<string>We need access to your Photos library to save videos</string>

<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

**Note:** For production, remove `NSAllowsArbitraryLoads` and use HTTPS only.

---

## 🤖 Android Integration (Kotlin)

### Step 1: Add Dependencies

Add to your `build.gradle (app)`:

```gradle
dependencies {
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'
    implementation 'com.squareup.retrofit2:retrofit:2.9.0'
    implementation 'com.squareup.retrofit2:converter-gson:2.9.0'
    implementation 'io.socket:socket.io-client:2.1.0'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
}
```

### Step 2: Create API Service

Create `VideoDownloaderApi.kt`:

```kotlin
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*

interface VideoDownloaderApi {
    @POST("api/info")
    suspend fun getVideoInfo(@Body request: VideoInfoRequest): VideoInfo
    
    @POST("api/formats")
    suspend fun getFormats(@Body request: VideoInfoRequest): FormatsResponse
    
    @POST("api/start_download")
    suspend fun startDownload(@Body request: DownloadRequest): DownloadResponse
    
    @GET("api/status/{id}")
    suspend fun getStatus(@Path("id") downloadId: String): DownloadStatus
    
    companion object {
        private const val BASE_URL = "https://your-server.com/"
        
        fun create(): VideoDownloaderApi {
            return Retrofit.Builder()
                .baseUrl(BASE_URL)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(VideoDownloaderApi::class.java)
        }
    }
}

// Data classes
data class VideoInfoRequest(val url: String)

data class VideoInfo(
    val title: String,
    val thumbnail: String,
    val duration: Int,
    val uploader: String,
    val description: String,
    @SerializedName("formats_available") val formatsAvailable: Int
)

data class DownloadRequest(
    val url: String,
    val format: String = "best"
)

data class DownloadResponse(
    @SerializedName("download_id") val downloadId: String,
    val title: String,
    val status: String
)

data class VideoFormat(
    @SerializedName("format_id") val formatId: String,
    val resolution: String,
    val ext: String,
    @SerializedName("filesize_mb") val filesizeMb: Double?
)

data class FormatsResponse(
    val formats: List<VideoFormat>,
    @SerializedName("audio_only") val audioOnly: List<AudioFormat>
)

data class AudioFormat(
    @SerializedName("format_id") val formatId: String,
    val ext: String,
    val abr: Int?
)

data class DownloadStatus(
    val id: String,
    val title: String,
    val status: String,
    val percent: Double,
    @SerializedName("file_size") val fileSize: Long?,
    @SerializedName("download_url") val downloadUrl: String?
)
```

### Step 3: Create Download Service

Create `VideoDownloaderService.kt`:

```kotlin
import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import io.socket.client.IO
import io.socket.client.Socket
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject

class VideoDownloaderService(private val context: Context) {
    private val api = VideoDownloaderApi.create()
    private val socket: Socket = IO.socket("https://your-server.com")
    
    private val _progress = MutableStateFlow(0.0)
    val progress: StateFlow<Double> = _progress
    
    private val _downloadSpeed = MutableStateFlow("")
    val downloadSpeed: StateFlow<String> = _downloadSpeed
    
    private val _activeDownloadId = MutableStateFlow<String?>(null)
    val activeDownloadId: StateFlow<String?> = _activeDownloadId
    
    init {
        setupSocketHandlers()
        socket.connect()
    }
    
    private fun setupSocketHandlers() {
        socket.on(Socket.EVENT_CONNECT) {
            println("✅ Socket connected")
        }
        
        socket.on("progress") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            val line = data.getString("line")
            parseProgress(line)
        }
        
        socket.on("completed") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            handleCompleted(id)
        }
        
        socket.on("failed") { args ->
            val data = args[0] as JSONObject
            val id = data.getString("id")
            val error = data.getString("error")
            handleFailed(id, error)
        }
    }
    
    private fun parseProgress(line: String) {
        // Parse percentage
        Regex("(\\d+\\.\\d+)%").find(line)?.let {
            val percent = it.groupValues[1].toDoubleOrNull()
            percent?.let { _progress.value = it }
        }
        
        // Parse speed
        Regex("(\\d+\\.\\d+[KMG]iB/s)").find(line)?.let {
            _downloadSpeed.value = it.groupValues[1]
        }
    }
    
    private fun handleCompleted(id: String) {
        _progress.value = 100.0
        _activeDownloadId.value = null
        downloadFileToDevice(id)
    }
    
    private fun handleFailed(id: String, error: String) {
        _activeDownloadId.value = null
        println("❌ Download failed: $error")
    }
    
    suspend fun getVideoInfo(url: String): VideoInfo {
        return api.getVideoInfo(VideoInfoRequest(url))
    }
    
    suspend fun getFormats(url: String): FormatsResponse {
        return api.getFormats(VideoInfoRequest(url))
    }
    
    suspend fun startDownload(url: String, format: String = "best"): String {
        val response = api.startDownload(DownloadRequest(url, format))
        
        // Subscribe to updates
        val subscribeData = JSONObject().apply {
            put("download_id", response.downloadId)
        }
        socket.emit("subscribe", subscribeData)
        
        _activeDownloadId.value = response.downloadId
        _progress.value = 0.0
        
        return response.downloadId
    }
    
    private fun downloadFileToDevice(downloadId: String) {
        val downloadManager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val uri = Uri.parse("https://your-server.com/download/$downloadId")
        
        val request = DownloadManager.Request(uri).apply {
            setTitle("Video Download")
            setDescription("Downloading video...")
            setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS,
                "$downloadId.mp4"
            )
            setMimeType("video/mp4")
        }
        
        downloadManager.enqueue(request)
    }
    
    fun disconnect() {
        socket.disconnect()
    }
}
```

### Step 4: Create Jetpack Compose UI

Create `DownloadScreen.kt`:

```kotlin
@Composable
fun DownloadScreen(
    viewModel: DownloadViewModel = viewModel()
) {
    val progress by viewModel.progress.collectAsState()
    val downloadSpeed by viewModel.downloadSpeed.collectAsState()
    val videoInfo by viewModel.videoInfo.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val activeDownloadId by viewModel.activeDownloadId.collectAsState()
    
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
    ) {
        // URL Input
        OutlinedTextField(
            value = viewModel.url,
            onValueChange = { viewModel.url = it },
            label = { Text("Video URL") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Button(
            onClick = { viewModel.fetchVideoInfo() },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading
        ) {
            if (isLoading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    color = Color.White
                )
            } else {
                Text("Get Video Info")
            }
        }
        
        // Video Info Card
        videoInfo?.let { info ->
            Spacer(modifier = Modifier.height(24.dp))
            
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    AsyncImage(
                        model = info.thumbnail,
                        contentDescription = "Video thumbnail",
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .clip(RoundedCornerShape(8.dp))
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    Text(
                        text = info.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = info.uploader,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.secondary
                        )
                        Text(
                            text = formatDuration(info.duration),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.secondary
                        )
                    }
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Button(
                        onClick = { viewModel.startDownload() },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Download, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Download Video")
                    }
                }
            }
        }
        
        // Download Progress
        if (activeDownloadId != null) {
            Spacer(modifier = Modifier.height(24.dp))
            
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "Downloading...",
                        style = MaterialTheme.typography.titleMedium
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    LinearProgressIndicator(
                        progress = progress.toFloat() / 100f,
                        modifier = Modifier.fillMaxWidth()
                    )
                    
                    Spacer(modifier = Modifier.height(8.dp))
                    
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "${progress.toInt()}%",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = downloadSpeed,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}

private fun formatDuration(seconds: Int): String {
    val hours = seconds / 3600
    val minutes = (seconds % 3600) / 60
    val secs = seconds % 60
    
    return if (hours > 0) {
        String.format("%d:%02d:%02d", hours, minutes, secs)
    } else {
        String.format("%d:%02d", minutes, secs)
    }
}
```

### Step 5: Configure Permissions

Add to `AndroidManifest.xml`:

```xml
<uses-permission android:name="android.permission.INTERNET" />
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />

<application
    android:usesCleartextTraffic="true"
    ...>
```

**Note:** For production, remove `usesCleartextTraffic` and use HTTPS only.

---

## 🔐 Security Best Practices

### 1. Use HTTPS Only
Never use HTTP in production. Get a free SSL certificate from Let's Encrypt.

### 2. Implement Authentication
Add API key or JWT authentication:

```swift
// iOS
request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
```

```kotlin
// Android
.addInterceptor { chain ->
    val request = chain.request().newBuilder()
        .addHeader("Authorization", "Bearer $apiKey")
        .build()
    chain.proceed(request)
}
```

### 3. Validate URLs
Always validate video URLs on the client before sending to server.

### 4. Handle SSL Pinning (Production)
Implement certificate pinning for production apps.

---

## 📊 Testing

### Test Checklist

- [ ] Video info fetches correctly
- [ ] Format selection works
- [ ] Download progress updates in real-time
- [ ] File downloads to device
- [ ] File saves to Photos/Downloads
- [ ] Error handling works
- [ ] Network reconnection works
- [ ] Background downloads continue

### Test URLs

```
YouTube: https://www.youtube.com/watch?v=dQw4w9WgXcQ
TikTok: https://www.tiktok.com/@username/video/123456789
Instagram: https://www.instagram.com/p/ABC123/
```

---

## 🐛 Common Issues

### iOS: "App Transport Security" Error
**Solution:** Add exception to Info.plist (development only)

### Android: File Not Saving
**Solution:** Request WRITE_EXTERNAL_STORAGE permission at runtime

### Socket Disconnects Frequently
**Solution:** Increase ping timeout on server and implement reconnection logic

### Downloads Fail on Mobile Networks
**Solution:** Check server CORS configuration and network permissions

---

## 📚 Additional Resources

- [Socket.IO iOS Client](https://github.com/socketio/socket.io-client-swift)
- [Socket.IO Android Client](https://github.com/socketio/socket.io-client-java)
- [Alamofire Documentation](https://github.com/Alamofire/Alamofire)
- [Retrofit Documentation](https://square.github.io/retrofit/)

---

Last Updated: 2024-04-13
