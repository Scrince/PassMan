from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packaging.markers import default_environment  # noqa: E402
from packaging.requirements import Requirement  # noqa: E402
from packaging.utils import canonicalize_name  # noqa: E402

from src.version import APP_NAME, APP_VERSION  # noqa: E402


def _purl(name: str, version: str) -> str:
    normalized = canonicalize_name(name)
    return f"pkg:pypi/{quote(normalized, safe='.-_')}@{quote(version, safe='.+-')}"


def create_sbom(target: str, architecture: str, build_environment: str) -> dict[str, object]:
    installed: dict[tuple[str, str], metadata.Distribution] = {}
    for item in metadata.distributions():
        location = getattr(item, "_path", None)
        if location and Path(location).name.startswith("._"):
            continue
        try:
            name = item.metadata.get("Name", "")
            version = item.version
        except (OSError, UnicodeError, ValueError):
            continue
        if name:
            installed[(canonicalize_name(name), version)] = item
    distributions = sorted(installed.values(), key=lambda item: item.metadata.get("Name", "").lower())
    by_name = {
        canonicalize_name(item.metadata.get("Name", "")): item
        for item in distributions
        if item.metadata.get("Name")
    }
    direct_names: set[str] = set()
    requirements_path = ROOT / "requirements.txt"
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if value and not value.startswith("#"):
            direct_names.add(canonicalize_name(Requirement(value).name))

    components: list[dict[str, object]] = []
    dependencies: list[dict[str, object]] = []
    refs_by_name: dict[str, str] = {}
    for dist in distributions:
        name = dist.metadata.get("Name", "")
        if not name:
            continue
        version = dist.version
        ref = _purl(name, version)
        normalized = canonicalize_name(name)
        refs_by_name[normalized] = ref
        components.append({
            "type": "library",
            "bom-ref": ref,
            "name": name,
            "version": version,
            "purl": ref,
            "properties": [{
                "name": "passman:direct-requirement",
                "value": "true" if normalized in direct_names else "false",
            }],
        })

    environment = default_environment()
    for dist in distributions:
        name = dist.metadata.get("Name", "")
        normalized = canonicalize_name(name) if name else ""
        if normalized not in refs_by_name:
            continue
        depends_on: set[str] = set()
        for raw_requirement in dist.requires or []:
            try:
                requirement = Requirement(raw_requirement)
            except Exception:
                continue
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            dependency_ref = refs_by_name.get(canonicalize_name(requirement.name))
            if dependency_ref:
                depends_on.add(dependency_ref)
        if depends_on:
            dependencies.append({"ref": refs_by_name[normalized], "dependsOn": sorted(depends_on)})

    python_version = ".".join(map(str, sys.version_info[:3]))
    python_ref = f"pkg:generic/python@{python_version}"
    components.append({
        "type": "framework",
        "bom-ref": python_ref,
        "name": "Python",
        "version": python_version,
        "purl": python_ref,
    })
    root_ref = f"pkg:generic/{canonicalize_name(APP_NAME)}@{APP_VERSION}"
    root_dependencies = [refs_by_name[name] for name in sorted(direct_names) if name in refs_by_name]
    root_dependencies.append(python_ref)
    dependencies.append({"ref": root_ref, "dependsOn": sorted(root_dependencies)})

    pyinstaller = by_name.get("pyinstaller")
    tool_components = []
    if pyinstaller:
        tool_components.append({
            "type": "application",
            "name": pyinstaller.metadata.get("Name", "PyInstaller"),
            "version": pyinstaller.version,
            "purl": _purl("pyinstaller", pyinstaller.version),
        })

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "tools": {"components": tool_components},
            "component": {
                "type": "application",
                "bom-ref": root_ref,
                "name": APP_NAME,
                "version": APP_VERSION,
                "purl": root_ref,
            },
            "properties": [
                {"name": "passman:target-platform", "value": target},
                {"name": "passman:target-architecture", "value": architecture},
                {"name": "passman:build-environment", "value": build_environment},
                {"name": "passman:sbom-scope", "value": "installed build environment, runtime requirements, and packaging dependencies"},
                {"name": "passman:source-requirements", "value": "requirements.txt"},
            ],
        },
        "components": sorted(components, key=lambda item: str(item["name"]).lower()),
        "dependencies": sorted(dependencies, key=lambda item: str(item["ref"])),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a CycloneDX SBOM for a PassMan release build environment.")
    parser.add_argument("--target", required=True, help="Target platform, for example macOS or Ubuntu 24.04 Linux")
    parser.add_argument("--architecture", required=True, help="Target architecture or architectures")
    parser.add_argument("--build-environment", required=True, help="Build OS and Python version")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(create_sbom(args.target, args.architecture, args.build_environment), indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
