"""Install the reviewed local add-on without editing Workshop files or save settings."""
from pathlib import Path
import hashlib
import json
import shutil

source = Path(__file__).resolve().parent / "FarmTrailer"
destination = Path.home() / "Zomboid/mods/FarmTrailer"
manifest = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source.rglob("*")) if p.is_file()}
if destination.exists():
    actual = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(destination.rglob("*")) if p.is_file()}
    if actual != manifest:
        raise SystemExit(f"Existing install differs. Preserve it before an update: {destination}")
else:
    shutil.copytree(source, destination)
actual = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(destination.rglob("*")) if p.is_file()}
assert actual == manifest, "Installed files differ from source"
print(json.dumps({"installed": str(destination), "files": len(manifest), "verified": True}))
