/// Represents a single download job tracked by the backend.
class DownloadJob {
  final String id;
  final String url;
  final String title;
  String status; // queued | downloading | completed | failed
  double percent;

  DownloadJob({
    required this.id,
    required this.url,
    required this.title,
    required this.status,
    this.percent = 0,
  });

  factory DownloadJob.fromJson(Map<String, dynamic> json, String id) {
    return DownloadJob(
      id: id,
      url: json['url'] as String? ?? '',
      title: json['title'] as String? ?? id,
      status: json['status'] as String? ?? 'queued',
      percent: (json['percent'] as num?)?.toDouble() ?? 0,
    );
  }
}

/// Represents a file that has already been downloaded and lives on the server.
class DownloadedFile {
  final String name;
  final int sizeBytes;
  final double modified; // epoch seconds
  final String path;

  DownloadedFile({
    required this.name,
    required this.sizeBytes,
    required this.modified,
    required this.path,
  });

  factory DownloadedFile.fromJson(Map<String, dynamic> json) {
    return DownloadedFile(
      name: json['name'] as String,
      sizeBytes: json['size'] as int,
      modified: (json['modified'] as num).toDouble(),
      path: json['path'] as String,
    );
  }
}
