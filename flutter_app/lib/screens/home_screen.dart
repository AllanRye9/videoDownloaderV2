import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../widgets/download_card.dart';

/// Main screen: URL input form + live download progress list.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _formKey = GlobalKey<FormState>();
  final _urlCtrl = TextEditingController();
  final _cookiesCtrl = TextEditingController();
  String _format = 'best';
  bool _showCookies = false;
  bool _submitting = false;

  static const _formats = [
    ('Best quality', 'best'),
    ('Best video + audio (mp4)', 'bestvideo+bestaudio/best'),
    ('720p', 'bestvideo[height<=720]+bestaudio/best'),
    ('480p', 'bestvideo[height<=480]+bestaudio/best'),
    ('Audio only (mp3)', 'bestaudio[ext=mp3]/bestaudio'),
  ];

  @override
  void dispose() {
    _urlCtrl.dispose();
    _cookiesCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);

    final api = context.read<ApiService>();
    final id = await api.startDownload(
      url: _urlCtrl.text.trim(),
      format: _format,
      cookies: _showCookies ? _cookiesCtrl.text.trim() : null,
    );

    setState(() => _submitting = false);

    if (!mounted) return;
    if (id == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Failed to start download. Check the server.'),
          backgroundColor: Colors.red,
        ),
      );
    } else {
      _urlCtrl.clear();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Download queued!')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final jobs = context.watch<ApiService>().activeJobs.values.toList()
      ..sort((a, b) => a.status.compareTo(b.status));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Video Downloader'),
        centerTitle: true,
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Download form ──────────────────────────────────────────────────
          Card(
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            elevation: 3,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'New Download',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                            color: Colors.deepPurple,
                          ),
                    ),
                    const SizedBox(height: 14),

                    // URL field
                    TextFormField(
                      controller: _urlCtrl,
                      keyboardType: TextInputType.url,
                      decoration: const InputDecoration(
                        labelText: 'Video URL',
                        hintText: 'https://www.youtube.com/watch?v=…',
                        prefixIcon: Icon(Icons.link),
                        border: OutlineInputBorder(),
                      ),
                      validator: (v) {
                        if (v == null || v.trim().isEmpty) {
                          return 'Please enter a URL';
                        }
                        final uri = Uri.tryParse(v.trim());
                        if (uri == null || !uri.hasScheme) {
                          return 'Enter a valid URL';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 12),

                    // Format selector
                    DropdownButtonFormField<String>(
                      value: _format,
                      decoration: const InputDecoration(
                        labelText: 'Format',
                        prefixIcon: Icon(Icons.high_quality),
                        border: OutlineInputBorder(),
                      ),
                      items: _formats
                          .map((f) => DropdownMenuItem(
                                value: f.$2,
                                child: Text(f.$1),
                              ))
                          .toList(),
                      onChanged: (v) => setState(() => _format = v!),
                    ),
                    const SizedBox(height: 8),

                    // Optional cookies toggle
                    Row(
                      children: [
                        Checkbox(
                          value: _showCookies,
                          onChanged: (v) =>
                              setState(() => _showCookies = v ?? false),
                        ),
                        const Text('Provide cookies (for private/age-gated)'),
                      ],
                    ),
                    if (_showCookies) ...[
                      TextFormField(
                        controller: _cookiesCtrl,
                        maxLines: 3,
                        decoration: const InputDecoration(
                          labelText: 'Cookies (Netscape format)',
                          hintText: '# Netscape HTTP Cookie File\n…',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 8),
                    ],

                    const SizedBox(height: 8),

                    // Submit button
                    FilledButton.icon(
                      onPressed: _submitting ? null : _submit,
                      icon: _submitting
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.download),
                      label: Text(_submitting ? 'Starting…' : 'Download'),
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.deepPurple,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          const SizedBox(height: 24),

          // ── Active / recent downloads ──────────────────────────────────────
          if (jobs.isNotEmpty) ...[
            Text(
              'Downloads (${jobs.length})',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 8),
            ...jobs.map((job) => DownloadCard(job: job)),
          ],
        ],
      ),
    );
  }
}
