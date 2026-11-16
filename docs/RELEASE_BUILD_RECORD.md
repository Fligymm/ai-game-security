# Release build record — 2026-11-14

Status: **published to `release/research-whitelist`; `main` untouched**

Remote branch:
https://github.com/Fligymm/ai-game-security/tree/release/research-whitelist  
Latest commit: `769e2d6` (initial publication: `bdca2e5`)

## Artifact

```text
build/ai-game-security-research-whitelist-2026-11-14.zip
size: 47,152 bytes
files: 21
SHA256: 8F371777DDD7FF9BFCC09E066AA049474F69B33FCB6BCE96563A49573EFEFDC3
```

The archive expands to the documentation/evidence whitelist plus
`LICENSE`, `THIRD_PARTY_NOTICES.md`, `README.md`, `RELEASE_NOTES.md`, and
`MANIFEST.sha256`. The code/documentation license is MIT,
`Copyright (c) 2026 Fligymm`.

## Build checks

- 21 files: 20 hashed Markdown/JSON/license entries plus `MANIFEST.sha256`.
- No `.py`, `.onnx`, `.pt`, images, videos, logs, or CSV files.
- No absolute Windows/POSIX paths, `AI_Security`, or high-confidence token
  patterns found in the sanitized export.
- `MANIFEST.sha256`: all 20 listed files match.
- Package is UTF-8 and contains no source code or model weights.

## Source state

Built from working tree at commit `713f183` plus the uncommitted audit/fix
changes. This is a build snapshot, not a Git tag or release commit.

## Publication target

Recommended target if the owner later uploads: a separate branch/release named
`release/research-whitelist`, not `main`, and not a push of the full working
tree. No push was performed.

Before upload: owner must confirm the MIT scope notice, destination visibility,
and final file list. The full repository contains tracked `runs/` images, logs,
and local manifests and must not be pushed as the release.

## Reproduce

```text
source: docs/RELEASE_WHITELIST.md
archive: build/ai-game-security-research-whitelist-2026-11-14.zip
hash: build/ai-game-security-research-whitelist-2026-11-14.zip.sha256
```

The `build/` directory is ignored by Git; the archive is a local deliverable.