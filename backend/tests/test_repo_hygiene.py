import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAC_RE = re.compile(r"(?<![0-9A-Fa-f:-])[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}(?![0-9A-Fa-f:-])")
ALLOWED_PREFIXES = ("00:00:5E:00:53", "02:00:5E:00:53")


def _candidate_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def test_only_documentation_macs_are_tracked():
    offenders = []
    for path in _candidate_files():
        if not path.is_file():
            continue
        text = path.read_text(errors="ignore")
        for match in MAC_RE.finditer(text):
            mac = match.group(0).upper().replace("-", ":")
            if not mac.startswith(ALLOWED_PREFIXES):
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
    assert not offenders, "real MAC addresses would be committed:\n" + "\n".join(offenders[:25])
