# Third-party notices

## Timeline Studio

- Repository: https://github.com/MartinDelophy/ai-video-editor
- License: MIT License
- Relationship: this project uses no source code from Timeline Studio. Its inspectable, operation-oriented editing-plan concept informed the product design of `contentstudio-edit-plan`.

The separate project and its assets remain subject to their own license.

## imageio-ffmpeg

- Repository: https://github.com/imageio/imageio-ffmpeg
- License: BSD 2-Clause License
- Relationship: Content Studio uses its Python wrapper to locate a local FFmpeg executable for rendering.

The wrapper may provide an FFmpeg binary. Distribution of a desktop package must audit the exact FFmpeg build and include its required notices before release.

## faster-whisper (optional)

- Repository: https://github.com/SYSTRAN/faster-whisper
- License: MIT License
- Relationship: when the optional `local-transcription` dependency is installed and the creator provides a local model directory, Content Studio uses it for offline CPU/INT8 voiceover transcription. Content Studio does not bundle, download, or redistribute speech models.
