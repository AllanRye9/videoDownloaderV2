import 'package:flutter/material.dart';
import '../models/download_model.dart';

/// A card showing live progress for an active [DownloadJob].
class DownloadCard extends StatelessWidget {
  final DownloadJob job;

  const DownloadCard({super.key, required this.job});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final (icon, color) = _iconAndColor(job.status);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title row
            Row(
              children: [
                Icon(icon, color: color, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    job.title,
                    style: theme.textTheme.bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                _StatusChip(status: job.status, color: color),
              ],
            ),
            const SizedBox(height: 10),
            // Progress bar
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: job.status == 'completed'
                    ? 1.0
                    : job.status == 'failed'
                        ? 0.0
                        : job.percent / 100,
                minHeight: 6,
                backgroundColor: Colors.grey.shade200,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
            const SizedBox(height: 6),
            // Percentage label
            Text(
              job.status == 'completed'
                  ? 'Done'
                  : job.status == 'failed'
                      ? 'Failed'
                      : '${job.percent.toStringAsFixed(1)} %',
              style: theme.textTheme.bodySmall?.copyWith(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }

  static (IconData, Color) _iconAndColor(String status) => switch (status) {
        'completed' => (Icons.check_circle, Colors.green),
        'failed' => (Icons.error, Colors.red),
        'downloading' => (Icons.download, Colors.blue),
        _ => (Icons.hourglass_empty, Colors.orange),
      };
}

class _StatusChip extends StatelessWidget {
  final String status;
  final Color color;
  const _StatusChip({required this.status, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        status,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
