import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:intl/intl.dart';
import 'package:filesize/filesize.dart';
import '../services/api_service.dart';
import '../models/download_model.dart';

/// Screen showing all files that have already been downloaded on the server.
class FilesScreen extends StatefulWidget {
  const FilesScreen({super.key});

  @override
  State<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends State<FilesScreen> {
  @override
  void initState() {
    super.initState();
    // Fetch files the first time this screen is shown.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ApiService>().fetchFiles();
    });
  }

  @override
  Widget build(BuildContext context) {
    final api = context.watch<ApiService>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Downloaded Files'),
        centerTitle: true,
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () => api.fetchFiles(),
          ),
        ],
      ),
      body: api.filesLoading
          ? const Center(child: CircularProgressIndicator())
          : api.files.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.folder_open,
                          size: 64, color: Colors.grey),
                      SizedBox(height: 12),
                      Text(
                        'No files yet.\nStart a download from the home tab.',
                        textAlign: TextAlign.center,
                        style: TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: api.fetchFiles,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: api.files.length,
                    itemBuilder: (_, i) =>
                        _FileCard(file: api.files[i], api: api),
                  ),
                ),
    );
  }
}

class _FileCard extends StatelessWidget {
  final DownloadedFile file;
  final ApiService api;

  const _FileCard({required this.file, required this.api});

  Future<void> _open(BuildContext context) async {
    final url = Uri.parse(api.fileUrl(file.name));
    if (await canLaunchUrl(url)) {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    } else if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Cannot open: ${url.toString()}')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final modifiedDate = DateTime.fromMillisecondsSinceEpoch(
      (file.modified * 1000).toInt(),
    );
    final dateStr = DateFormat('dd MMM yyyy - HH:mm').format(modifiedDate);

    final isVideo = file.name.endsWith('.mp4') ||
        file.name.endsWith('.mkv') ||
        file.name.endsWith('.webm') ||
        file.name.endsWith('.mov');
    final isAudio = file.name.endsWith('.mp3') ||
        file.name.endsWith('.m4a') ||
        file.name.endsWith('.opus');

    final icon = isVideo
        ? Icons.videocam
        : isAudio
            ? Icons.music_note
            : Icons.insert_drive_file;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.deepPurple.shade50,
          child: Icon(icon, color: Colors.deepPurple),
        ),
        title: Text(
          file.name,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        subtitle: Text('${filesize(file.sizeBytes)} · $dateStr',
            style: const TextStyle(fontSize: 11)),
        trailing: IconButton(
          icon: const Icon(Icons.open_in_new, color: Colors.deepPurple),
          tooltip: 'Open / Play',
          onPressed: () => _open(context),
        ),
      ),
    );
  }
}
