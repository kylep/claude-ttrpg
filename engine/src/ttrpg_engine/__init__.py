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
    candidates: list[str] = []
    import subprocess

    try:
        prefix = subprocess.run(
            ["brew", "--prefix"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
        if prefix:
            candidates.append(os.path.join(prefix, "lib"))
    except (OSError, subprocess.SubprocessError):
        pass
    candidates += ["/opt/homebrew/lib", "/usr/local/lib"]
    existing = [p for p in dict.fromkeys(candidates) if os.path.isdir(p)]
    if existing:
        os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = ":".join(existing)


_ensure_native_lib_path()
