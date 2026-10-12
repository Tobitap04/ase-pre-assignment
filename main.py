import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


PYPI_URL = "https://pypi.org/pypi"


@dataclass(frozen=True)
class Requirement:
    name: str
    version: str


@dataclass(frozen=True)
class ValidationSummary:
    checked: int
    packages_not_on_pypi: int
    versions_not_on_pypi: int
    oldest_pinned_release: Optional[tuple[str, str, int]]


def parse_requirement(line: str) -> Optional[Requirement]:
    stripped = line.strip()
    # Only pinned requirements are relevant for version validation.
    if not stripped or stripped.startswith("#") or "==" not in stripped:
        return None

    name, version = stripped.split("==", 1)
    if not name.strip() or not version.strip():
        return None
    return Requirement(name.strip(), version.strip())


def fetch_json(url: str) -> Optional[dict]:
    request = Request(url, headers={"User-Agent": "requirements-pypi-validator/1.0"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as error:
        # A 404 is the expected signal for a missing package or version.
        if error.code == 404:
            return None
        raise

    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {url}")
    return payload


def _pypi_url(name: str, version: Optional[str] = None) -> str:
    # Encode names and versions so special characters are safe in the URL.
    package = quote(name, safe="")
    if version is None:
        return f"{PYPI_URL}/{package}/json"
    return f"{PYPI_URL}/{package}/{quote(version, safe='')}/json"


def _upload_time(payload: dict, url: str) -> datetime:
    urls = payload.get("urls")
    if not isinstance(urls, list) or not urls:
        raise ValueError(f"PyPI response has no files listed: {url}")
    # PyPI lists release files in order; use the first file as requested.
    first_file = urls[0]
    if not isinstance(first_file, dict) or not isinstance(
        first_file.get("upload_time"), str
    ):
        raise ValueError(f"PyPI response has no upload_time: {url}")
    return datetime.fromisoformat(first_file["upload_time"].replace("Z", "+00:00"))


def validate_requirements(lines: list[str]) -> ValidationSummary:
    # Count all non-empty lines, including lines that are not pinned.
    checked = sum(bool(line.strip()) for line in lines)
    packages_not_on_pypi = 0
    versions_not_on_pypi = 0
    oldest: Optional[tuple[datetime, Requirement]] = None

    for line in lines:
        requirement = parse_requirement(line)
        if requirement is None:
            continue

        package_payload = fetch_json(_pypi_url(requirement.name))
        if package_payload is None:
            packages_not_on_pypi += 1
            continue

        # Check the exact pinned version only after the package exists.
        version_url = _pypi_url(requirement.name, requirement.version)
        version_payload = fetch_json(version_url)
        if version_payload is None:
            versions_not_on_pypi += 1
            continue

        release_time = _upload_time(version_payload, version_url)
        # Keep the earliest upload time among valid pinned releases.
        if oldest is None or release_time < oldest[0]:
            oldest = (release_time, requirement)

    oldest_release = None
    if oldest is not None:
        release_time, requirement = oldest
        oldest_release = (requirement.name, requirement.version, release_time.year)

    return ValidationSummary(
        checked=checked,
        packages_not_on_pypi=packages_not_on_pypi,
        versions_not_on_pypi=versions_not_on_pypi,
        oldest_pinned_release=oldest_release,
    )


def print_summary(summary: ValidationSummary) -> None:
    print(f"Dependencies checked: {summary.checked}")
    print(f"Packages not on PyPI: {summary.packages_not_on_pypi}")
    print(f"Versions not on PyPI: {summary.versions_not_on_pypi}")
    if summary.oldest_pinned_release is not None:
        name, version, year = summary.oldest_pinned_release
        print(f"Oldest pinned release: {name}=={version} ({year})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate requirements against PyPI.")
    parser.add_argument("requirements_file", help="Path to a requirements.txt file")
    args = parser.parse_args()

    try:
        with open(args.requirements_file, encoding="utf-8") as requirements_file:
            summary = validate_requirements(requirements_file.readlines())
        print_summary(summary)
    except (OSError, ValueError, HTTPError, TimeoutError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())