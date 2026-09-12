import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="contentstudio-pytest-"))
os.environ["CONTENT_STUDIO_DB_PATH"] = str(_root / "content-studio.db")
os.environ["CONTENT_STUDIO_MEDIA_DIR"] = str(_root / "content-media")
os.environ["CONTENT_STUDIO_RENDER_WIDTH"] = "320"
os.environ["CONTENT_STUDIO_RENDER_HEIGHT"] = "180"
os.environ["CONTENT_STUDIO_RENDER_FRAME_RATE"] = "10"
