"""Generate SHA-256 checksums and a machine-readable provenance record for a
release-candidate build's canonical artifacts.

Answers, for any candidate run, the questions M15.1 requires:
what product version, which exact commit, which workflow run, what are the
canonical artifact filenames/checksums, and did the automated release gates
pass.

Usage:
    python scripts/generate_provenance.py \\
        --version 1.0.0 \\
        --commit <sha> \\
        --run-id <github-actions-run-id> \\
        --run-url <github-actions-run-url> \\
        --tests-passed 948 \\
        --output-dir packaging/dist \\
        packaging/dist/ListenTrace-1.0.0-win64-portable.zip \\
        packaging/dist/ListenTrace-Setup-1.0.0.exe

Writes `<output-dir>/SHA256SUMS.txt` (standard `sha256sum`-compatible
format -- verifiable with `sha256sum --check` on any platform) and
`<output-dir>/provenance.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Product version, e.g. 1.0.0")
    parser.add_argument("--commit", required=True, help="Exact source commit SHA the artifacts were built from")
    parser.add_argument("--run-id", required=True, help="GitHub Actions workflow run id")
    parser.add_argument("--run-url", required=True, help="GitHub Actions workflow run URL")
    parser.add_argument("--tests-passed", type=int, required=True, help="Number of automated tests that passed")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory to write SHA256SUMS.txt/provenance.json into")
    parser.add_argument("artifacts", nargs="+", type=Path, help="Canonical artifact files to checksum")
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    artifact_records = []
    checksum_lines = []
    for artifact in args.artifacts:
        if not artifact.is_file():
            parser.error(f"artifact does not exist: {artifact}")
        digest = sha256_of(artifact)
        artifact_records.append(
            {
                "name": artifact.name,
                "sha256": digest,
                "size_bytes": artifact.stat().st_size,
            }
        )
        checksum_lines.append(f"{digest}  {artifact.name}")

    sha256sums_path = args.output_dir / "SHA256SUMS.txt"
    sha256sums_path.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    provenance = {
        "product": "ListenTrace",
        "version": args.version,
        "commit": args.commit,
        "workflow_run_id": args.run_id,
        "workflow_run_url": args.run_url,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "automated_tests": {"passed": args.tests_passed, "result": "pass"},
        "artifacts": artifact_records,
    }
    provenance_path = args.output_dir / "provenance.json"
    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {sha256sums_path} and {provenance_path} for {len(artifact_records)} artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
