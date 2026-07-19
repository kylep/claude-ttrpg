"""ttrpg_engine package init.

On macOS, WeasyPrint's native libraries (pango / gobject, installed via Homebrew)
are not on the dynamic loader's default search path, so a bare `import weasyprint`
fails with `OSError: cannot load library 'libgobject-2.0-0'`. Pointing
DYLD_FALLBACK_LIBRARY_PATH at Homebrew's lib dir before the first weasyprint
import fixes it. We do it here, at package import, so both the `engine` CLI and
the test suite work without any manual environment setup — importing any
`ttrpg_engine.*` submodule runs this first. No-op off macOS, or when the variable
is already set by the environment.
"""

import os
import sys


def _ensure_native_lib_path() -> None:
    if sys.platform != "darwin" or os.environ.get("DYLD_FALLBACK_LIBRARY_PATH"):
        return
    # Common Homebrew lib dirs first — avoids spawning `brew` on every import.
    candidates = ["/opt/homebrew/lib", "/usr/local/lib"]
    if not any(os.path.isdir(p) for p in candidates):
        import subprocess

        try:
            prefix = subprocess.run(
                ["brew", "--prefix"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
            if prefix:
                candidates.insert(0, os.path.join(prefix, "lib"))
        except (OSError, subprocess.SubprocessError):
            pass
    existing = [p for p in dict.fromkeys(candidates) if os.path.isdir(p)]
    if existing:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(existing)


_ensure_native_lib_path()
