# Flutter README

A Flutter front-end for the [VideoDownloaderV2](https://github.com/AllanRye9/videoDownloaderV2) backend.

## Getting Started

### Prerequisites
- Flutter SDK ≥ 3.0 – https://flutter.dev/docs/get-started/install
- The backend running (see root `README.md` / `Dockerfile`)

### Configuration
Open `lib/services/api_service.dart` and change `baseUrl` to point at your
running server, e.g.:
```dart
static const String baseUrl = 'http://192.168.1.100:5000';
```

### Run
```bash
flutter pub get
flutter run
```

### Features
| Screen | Description |
|--------|-------------|
| **Download** | Paste a URL, pick quality/format, start a download, watch real-time progress via WebSocket |
| **Files** | Browse all files already downloaded on the server and open/stream them |
