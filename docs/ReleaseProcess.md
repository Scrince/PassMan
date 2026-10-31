# Release process

This procedure describes the checks for a PassMan source release. Platform
packages must be built on native Windows, macOS, and Linux runners or machines.

## Prepare

1. Create a release pull request from a clean branch based on `main`.
2. Update `src/version.py` and `CHANGELOG.md` together. Confirm README release
   notes and platform instructions describe the same version and artifacts.
3. Update dependencies in `pyproject.toml` and `requirements.txt` as needed,
   then regenerate `uv.lock` with `uv lock`.
4. Run Ruff and the complete unit test suite. Review security-sensitive changes
   against `docs/Encryption.txt` and `docs/OpSec.txt`.
5. Confirm the CI test matrix, CodeQL analysis, and native packaging smoke jobs
   pass on the pull request.

## Build and verify packages

1. Merge the reviewed pull request, then create an annotated version tag such
   as `v1.0.8` pointing to the approved commit.
2. Build each platform package on its target OS from that exact tag using the
   locked dependencies and documented native prerequisites in `docs/Build.txt`.
3. Launch each packaged application in a clean environment and verify the
   version shown by the app. Do not use a real vault for smoke checks.
4. Generate a CycloneDX SBOM and per-platform SHA-256 manifest for the exact
   files being distributed. Sign each package, SBOM, and manifest with the
   release key according to `docs/Build.txt`.
5. Verify signatures and checksums from a clean directory using only the
   published public key. Ensure no vault data, private keys, or build
   environment files are included.

## Publish

1. Draft a GitHub release for the version tag and attach the platform packages,
   SBOMs, signatures, and checksum manifests.
2. Confirm each asset name, platform, architecture, and checksum matches the
   release notes. Keep packaged binaries out of Git history.
3. Publish the release only after all artifacts have been independently
   verified. Record any platform limitations, such as macOS notarization or
   Windows Authenticode status, in the release notes.
