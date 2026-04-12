import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:socket_io_client/socket_io_client.dart' as io;
import '../models/download_model.dart';

/// All communication with the VideoDownloaderV2 Flask backend.
class ApiService extends ChangeNotifier {
  // ── Configuration ─────────────────────────────────────────────────────────
  // Change this to your server's IP / hostname when running outside localhost.
  static const String baseUrl = 'http://localhost:5000';

  // ── Internal state ─────────────────────────────────────────────────────────
  late io.Socket _socket;
  final Map<String, DownloadJob> _activeJobs = {};
  List<DownloadedFile> _files = [];
  bool _filesLoading = false;

  // ── Public read-only accessors ─────────────────────────────────────────────
  Map<String, DownloadJob> get activeJobs => Map.unmodifiable(_activeJobs);
  List<DownloadedFile> get files => List.unmodifiable(_files);
  bool get filesLoading => _filesLoading;

  // ── Constructor / Socket setup ─────────────────────────────────────────────
  ApiService() {
    _initSocket();
  }

  void _initSocket() {
    _socket = io.io(
      baseUrl,
      io.OptionBuilder()
          .setTransports(['websocket'])
          .disableAutoConnect()
          .build(),
    );

    _socket.onConnect((_) => debugPrint('Socket connected'));
    _socket.onDisconnect((_) => debugPrint('Socket disconnected'));

    // Real-time progress line from yt-dlp stdout
    _socket.on('progress', (data) {
      final id = data['id'] as String;
      final line = data['line'] as String;
      if (_activeJobs.containsKey(id)) {
        // Try to parse a percentage from the line
        if (line.contains('%')) {
          try {
            final pctStr = line.split('%')[0].split(' ').last;
            _activeJobs[id]!.percent = double.parse(pctStr);
          } catch (e) {
            debugPrint('Could not parse progress percentage from: "$line" ($e)');
          }
        }
        _activeJobs[id]!.status = 'downloading';
        notifyListeners();
      }
    });

    _socket.on('completed', (data) {
      final id = data['id'] as String;
      if (_activeJobs.containsKey(id)) {
        _activeJobs[id]!.status = 'completed';
        _activeJobs[id]!.percent = 100;
        notifyListeners();
      }
      fetchFiles(); // refresh file list
    });

    _socket.on('failed', (data) {
      final id = data['id'] as String;
      if (_activeJobs.containsKey(id)) {
        _activeJobs[id]!.status = 'failed';
        notifyListeners();
      }
    });

    _socket.on('files_updated', (_) => fetchFiles());

    _socket.connect();
  }

  // ── REST: start a new download ─────────────────────────────────────────────
  Future<String?> startDownload({
    required String url,
    String format = 'best',
    String? cookies,
  }) async {
    final uri = Uri.parse('$baseUrl/start_download');
    final body = <String, String>{'url': url, 'format': format};
    if (cookies != null && cookies.isNotEmpty) body['cookies'] = cookies;

    final response = await http.post(uri, body: body);
    if (response.statusCode != 200) return null;

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    final id = json['download_id'] as String;

    final job = DownloadJob(
      id: id,
      url: url,
      title: 'Loading…',
      status: 'queued',
    );
    _activeJobs[id] = job;
    notifyListeners();

    // Subscribe to Socket.IO room for this job
    _socket.emit('subscribe', {'download_id': id});

    // Fetch the real title asynchronously
    _refreshJobStatus(id);

    return id;
  }

  // ── REST: refresh a single job's status ───────────────────────────────────
  Future<void> _refreshJobStatus(String id) async {
    final uri = Uri.parse('$baseUrl/status/$id');
    try {
      final response = await http.get(uri);
      if (response.statusCode == 200) {
        final json = jsonDecode(response.body) as Map<String, dynamic>;
        if (json.isNotEmpty) {
          _activeJobs[id] = DownloadJob.fromJson(json, id);
          notifyListeners();
        }
      }
    } catch (_) {}
  }

  // ── REST: list downloaded files ────────────────────────────────────────────
  Future<void> fetchFiles() async {
    _filesLoading = true;
    notifyListeners();
    try {
      final response = await http.get(Uri.parse('$baseUrl/files'));
      if (response.statusCode == 200) {
        final list = jsonDecode(response.body) as List<dynamic>;
        _files = list
            .map((e) => DownloadedFile.fromJson(e as Map<String, dynamic>))
            .toList();
      }
    } catch (_) {}
    _filesLoading = false;
    notifyListeners();
  }

  // ── File URL helper ────────────────────────────────────────────────────────
  String fileUrl(String filename) => '$baseUrl/downloads/$filename';

  @override
  void dispose() {
    _socket.dispose();
    super.dispose();
  }
}
