import os
import tempfile
from pathlib import Path

_root = Path(tempfile.mkdtemp(prefix="contentstudio-pytest-"))
os.environ["CONTENT_STUDIO_DB_PATH"] = str(_root / "content-studio.db")
os.environ["CONTENT_STUDIO_MEDIA_DIR"] = str(_root / "content-media")
