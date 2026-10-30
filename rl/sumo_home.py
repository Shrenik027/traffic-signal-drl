"""
Finds SUMO on this machine and sets SUMO_HOME, on Windows, macOS or Linux.

Why this file exists: `sumo_rl` refuses to import unless the SUMO_HOME
environment variable points at a real SUMO installation. That variable is
set by the Windows installer and by most package managers, but not always --
and when it is missing, the error you get is cryptic. Rather than
hard-coding one platform's path (which then silently breaks on the other
two), this works it out from wherever SUMO actually is.

Call `ensure_sumo_home()` BEFORE importing sumo_rl.
"""
import os
import shutil
import sys

# Places SUMO commonly lives, if it is not on PATH and SUMO_HOME is unset.
COMMON_LOCATIONS = [
    r"C:\Program Files (x86)\Eclipse\Sumo",   # Windows installer default
    r"C:\Program Files\Eclipse\Sumo",
    "/usr/share/sumo",                        # Debian/Ubuntu apt
    "/usr/local/share/sumo",
    "/opt/homebrew/share/sumo",               # macOS, Apple Silicon
    "/usr/local/opt/sumo/share/sumo",         # macOS, Intel
]


def _looks_like_sumo_home(path: str) -> bool:
    """A real SUMO_HOME has a 'tools' directory inside it."""
    return bool(path) and os.path.isdir(os.path.join(path, "tools"))


def ensure_sumo_home() -> str:
    """Set os.environ['SUMO_HOME'] to a valid SUMO installation and return it.

    Order of preference:
      1. SUMO_HOME, if it is already set AND actually points somewhere real
      2. derived from the `sumo` executable on PATH
      3. the usual install locations for this platform
    """
    # 1. already set correctly -- leave it alone
    current = os.environ.get("SUMO_HOME")
    if _looks_like_sumo_home(current):
        return current

    # 2. derive it from the binary on PATH.
    #    Windows: C:\...\Sumo\bin\sumo.exe  -> C:\...\Sumo
    #    (On Linux, /usr/bin/sumo gives /usr, which has no tools/ dir, so
    #     this correctly falls through to the list below.)
    binary = shutil.which("sumo") or shutil.which("sumo.exe")
    if binary:
        candidate = os.path.dirname(os.path.dirname(os.path.realpath(binary)))
        if _looks_like_sumo_home(candidate):
            os.environ["SUMO_HOME"] = candidate
            return candidate

    # 3. the usual suspects
    for candidate in COMMON_LOCATIONS:
        if _looks_like_sumo_home(candidate):
            os.environ["SUMO_HOME"] = candidate
            return candidate

    sys.exit(
        "\nCould not find your SUMO installation.\n\n"
        "SUMO is installed separately from the Python packages -- get it from\n"
        "  https://sumo.dlr.de/docs/Downloads.php\n\n"
        "If it IS installed, point SUMO_HOME at it and open a new terminal:\n"
        '  Windows : setx SUMO_HOME "C:\\Program Files (x86)\\Eclipse\\Sumo"\n'
        "  macOS   : export SUMO_HOME=\"$(brew --prefix sumo)/share/sumo\"\n"
        "  Linux   : export SUMO_HOME=/usr/share/sumo\n"
    )


if __name__ == "__main__":
    print("SUMO_HOME =", ensure_sumo_home())
