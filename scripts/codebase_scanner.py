#!/usr/bin/env python3
"""
codebase_scanner.py — Factual codebase metrics extractor for the codebase-5yr-forecast skill.

Outputs scan.json with the schema documented in SKILL.md § Phase 2.
This script is NOT a scoring tool — it only extracts factual data. No LLM judgment here.

Usage:
    python codebase_scanner.py /path/to/codebase > scan.json
    python codebase_scanner.py /path/to/codebase --output scan.json
    python codebase_scanner.py --version
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Language detection by file extension
# ---------------------------------------------------------------------------

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".r": "R",
    ".lua": "Lua",
    ".pl": "Perl",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "LESS",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".fs": "F#",
    ".elm": "Elm",
    ".julia": "Julia",
    ".vim": "Vim Script",
    ".dockerfile": "Dockerfile",
}

# Manifest files and their associated ecosystems
MANIFEST_FILES = {
    "package.json": ("npm", "javascript"),
    "package-lock.json": ("npm", "javascript"),
    "yarn.lock": ("npm", "javascript"),
    "pnpm-lock.yaml": ("npm", "javascript"),
    "requirements.txt": ("pip", "python"),
    "pyproject.toml": ("pip", "python"),
    "Pipfile": ("pip", "python"),
    "Pipfile.lock": ("pip", "python"),
    "poetry.lock": ("pip", "python"),
    "go.mod": ("go_modules", "go"),
    "go.sum": ("go_modules", "go"),
    "Cargo.toml": ("cargo", "rust"),
    "Cargo.lock": ("cargo", "rust"),
    "pom.xml": ("maven", "java"),
    "build.gradle": ("gradle", "java"),
    "build.gradle.kts": ("gradle", "kotlin"),
    "Gemfile": ("bundler", "ruby"),
    "Gemfile.lock": ("bundler", "ruby"),
    "composer.json": ("composer", "php"),
    "mix.exs": ("mix", "elixir"),
    "rebar.config": ("rebar3", "erlang"),
    "Package.swift": ("swift", "swift"),
    "Packages.swift": ("swift", "swift"),
    "Project.toml": ("julia", "julia"),
}

# Patterns indicating CI/CD
CI_FILES = [
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    ".travis.yml",
    "bitbucket-pipelines.yml",
    ".drone.yml",
    "cloudbuild.yaml",
    ".buildkite/pipeline.yml",
]

# README variants
README_FILES = ["README.md", "README.rst", "README.txt", "README", "readme.md", "Readme.md"]

# License patterns (simple)
LICENSE_FILES = ["LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE-MIT", "LICENSE-APACHE", "COPYING"]

# Test file patterns
TEST_PATTERNS = [
    "test_*.py", "*_test.py", "*_spec.py",
    "*.test.js", "*.test.ts", "*.test.tsx", "*.test.jsx",
    "*.spec.js", "*.spec.ts", "*.spec.tsx", "*.spec.jsx",
    "*_test.go", "*_test.rs",
    "*Test.java", "*Tests.java", "*TestCase.java",
    "*_spec.rb", "*_test.rb", "spec/**",
    "*Test.kt", "*Tests.kt",
    "*Test.cs", "*Tests.cs",
]

# Directories to skip
SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "vendor", "venv", ".venv", "env",
    ".tox", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    "dist", "build", "target", "out", "bin", "obj", ".next", ".nuxt",
    ".gradle", ".idea", ".vscode", "coverage", ".coverage", "htmlcov",
    ".terraform", ".serverless", ".aws", ".azure", ".gcloud",
    "Pods", "Carthage", ".swiftpm", ".build",
    ".deno", ".bun", "_build", "deps", "_vendor",
}


# ---------------------------------------------------------------------------
# Counting LOC (non-comment, non-blank)
# ---------------------------------------------------------------------------

COMMENT_PATTERNS = {
    "Python": [r"^\s*#", r'^\s*"""', r"^\s*'''"],
    "JavaScript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "TypeScript": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Go": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Rust": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Java": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Kotlin": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Ruby": [r"^\s*#", r"^\s*=begin"],
    "PHP": [r"^\s*//", r"^\s*#", r"^\s*/\*", r"^\s*\*"],
    "C": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "C++": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "C#": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Shell": [r"^\s*#"],
    "Bash": [r"^\s*#"],
    "Swift": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Scala": [r"^\s*//", r"^\s*/\*", r"^\s*\*"],
    "Elixir": [r"^\s*#"],
    "Erlang": [r"^\s*%"],
    "Haskell": [r"^\s*--", r"^\s*\{-"],
    "Lua": [r"^\s*--", r"^\s*--\[\["],
    "R": [r"^\s*#"],
    "SQL": [r"^\s*--", r"^\s*/\*"],
}


def count_loc(file_path: Path, language: str) -> tuple[int, int, int]:
    """Return (total, blank, comment) line counts. LOC = total - blank - comment."""
    total = 0
    blank = 0
    comment = 0
    comment_patterns = [re.compile(p) for p in COMMENT_PATTERNS.get(language, [])]
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                total += 1
                stripped = line.strip()
                if not stripped:
                    blank += 1
                    continue
                if any(p.match(line) for p in comment_patterns):
                    comment += 1
    except (OSError, UnicodeDecodeError):
        pass
    return total, blank, comment


# ---------------------------------------------------------------------------
# Dependency parsing (best-effort)
# ---------------------------------------------------------------------------

def parse_dependencies(repo_root: Path) -> list[dict]:
    deps = []
    for manifest_name in MANIFEST_FILES:
        for path in repo_root.rglob(manifest_name):
            # Skip if in skipped dir
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                ecosystem, lang = MANIFEST_FILES[manifest_name]
                text = path.read_text(encoding="utf-8", errors="ignore")
                parsed = []
                if manifest_name == "package.json":
                    parsed = parse_npm(text)
                elif manifest_name == "requirements.txt":
                    parsed = parse_requirements(text)
                elif manifest_name == "pyproject.toml":
                    parsed = parse_pyproject(text)
                elif manifest_name == "go.mod":
                    parsed = parse_go_mod(text)
                elif manifest_name == "Cargo.toml":
                    parsed = parse_cargo(text)
                elif manifest_name == "Gemfile":
                    parsed = parse_gemfile(text)
                elif manifest_name == "pom.xml":
                    parsed = parse_pom(text)
                for name, version in parsed:
                    deps.append({
                        "name": name,
                        "version": version,
                        "ecosystem": ecosystem,
                        "language": lang,
                        "manifest": str(path.relative_to(repo_root)),
                    })
            except Exception:
                continue
    return deps


def parse_npm(text: str) -> list[tuple[str, str]]:
    try:
        data = json.loads(text)
        result = []
        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            for name, version in data.get(section, {}).items():
                result.append((name, version))
        return result
    except json.JSONDecodeError:
        return []


def parse_requirements(text: str) -> list[tuple[str, str]]:
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Strip environment markers
        line = line.split(";")[0].strip()
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([=<>!~]=?\s*[\w.\-+]+)?", line)
        if m:
            name = m.group(1)
            version = (m.group(2) or "").strip()
            result.append((name, version))
    return result


def parse_pyproject(text: str) -> list[tuple[str, str]]:
    # Best-effort: extract [project.dependencies] and [tool.poetry.dependencies]
    result = []
    # Simple regex extraction
    in_deps = False
    current_section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "dependencies" in stripped.lower():
            in_deps = True
            current_section = stripped
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            # poetry style: package = "1.0.0"
            m = re.match(r'^([A-Za-z0-9_.\-]+)\s*=\s*"([^"]+)"', stripped)
            if m:
                result.append((m.group(1), m.group(2)))
                continue
            # toml style: "package>=1.0.0"
            m = re.match(r'^"([^"]+)"\s*=\s*"([^"]+)"', stripped)
            if m:
                parsed = parse_requirements_line(m.group(1))
                if parsed:
                    result.append(parsed)
    return result


def parse_requirements_line(line: str) -> tuple[str, str] | None:
    m = re.match(r"^([A-Za-z0-9_.\-]+)\s*([=<>!~]=?\s*[\w.\-+]+)?", line)
    if m:
        return (m.group(1), (m.group(2) or "").strip())
    return None


def parse_go_mod(text: str) -> list[tuple[str, str]]:
    result = []
    in_require = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ") and "{" in stripped:
            in_require = True
            continue
        if stripped == "}" and in_require:
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            m = re.match(r"(?:require\s+)?([^\s]+)\s+(\S+)", stripped)
            if m:
                result.append((m.group(1), m.group(2)))
    return result


def parse_cargo(text: str) -> list[tuple[str, str]]:
    result = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[dependencies]":
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps and "=" in stripped:
            m = re.match(r'^([A-Za-z0-9_.\-]+)\s*=\s*"([^"]+)"', stripped)
            if m:
                result.append((m.group(1), m.group(2)))
    return result


def parse_gemfile(text: str) -> list[tuple[str, str]]:
    result = []
    for line in text.splitlines():
        m = re.match(r'^\s*gem\s+["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']+)["\'])?', line)
        if m:
            result.append((m.group(1), m.group(2) or ""))
    return result


def parse_pom(text: str) -> list[tuple[str, str]]:
    result = []
    # Best-effort: <dependency><groupId>...</groupId><artifactId>...</artifactId><version>...</version></dependency>
    pattern = re.compile(
        r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>(?:\s*<version>([^<]+)</version>)?",
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        result.append((f"{m.group(1)}:{m.group(2)}", m.group(3) or ""))
    return result


# ---------------------------------------------------------------------------
# Tech-debt proxies
# ---------------------------------------------------------------------------

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG)\b")


def count_tech_debt(repo_root: Path, max_files: int = 5000) -> dict:
    todo = 0
    fixme = 0
    hack = 0
    xxx = 0
    bug = 0
    files_scanned = 0
    for path in repo_root.rglob("*"):
        if files_scanned >= max_files:
            break
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in LANGUAGE_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in TODO_PATTERN.finditer(text):
                token = m.group(1).upper()
                if token == "TODO":
                    todo += 1
                elif token == "FIXME":
                    fixme += 1
                elif token == "HACK":
                    hack += 1
                elif token == "XXX":
                    xxx += 1
                elif token == "BUG":
                    bug += 1
            files_scanned += 1
        except OSError:
            continue
    return {
        "todo_count": todo,
        "fixme_count": fixme,
        "hack_count": hack,
        "xxx_count": xxx,
        "bug_count": bug,
        "total_markers": todo + fixme + hack + xxx + bug,
        "files_scanned": files_scanned,
    }


# ---------------------------------------------------------------------------
# Test file detection
# ---------------------------------------------------------------------------

def is_test_file(path: Path) -> bool:
    name = path.name
    for pattern in TEST_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    # Also detect by path
    parts = path.parts
    if "test" in parts or "tests" in parts or "spec" in parts or "specs" in parts:
        if path.suffix.lower() in LANGUAGE_EXTENSIONS:
            return True
    return False


# ---------------------------------------------------------------------------
# Git metadata
# ---------------------------------------------------------------------------

def get_git_last_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def get_git_remote(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan(repo_root: Path) -> dict:
    repo_root = repo_root.resolve()

    if not repo_root.exists():
        return {"error": f"Path does not exist: {repo_root}"}
    if not repo_root.is_dir():
        return {"error": f"Path is not a directory: {repo_root}"}

    language_files: Counter = Counter()
    language_loc: Counter = Counter()
    file_count_by_ext: Counter = Counter()
    test_file_count = 0
    source_file_count = 0
    total_files_scanned = 0
    largest_file_loc = 0
    largest_file_path = None
    file_sizes: list[int] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        total_files_scanned += 1

        ext = path.suffix.lower()
        if ext == ".dockerfile" or path.name.lower() == "dockerfile":
            ext = ".dockerfile"

        if ext in LANGUAGE_EXTENSIONS:
            language = LANGUAGE_EXTENSIONS[ext]
            language_files[language] += 1
            total, blank, comment = count_loc(path, language)
            loc = total - blank - comment
            language_loc[language] += loc
            file_count_by_ext[ext] += 1
            file_sizes.append(loc)

            if loc > largest_file_loc:
                largest_file_loc = loc
                largest_file_path = str(path.relative_to(repo_root))

            if is_test_file(path):
                test_file_count += 1
            else:
                source_file_count += 1

    total_loc = sum(language_loc.values())
    avg_file_size = (sum(file_sizes) / len(file_sizes)) if file_sizes else 0

    # Primary language
    if language_loc:
        primary_language = language_loc.most_common(1)[0][0]
        secondary_languages = [lang for lang, _ in language_loc.most_common()[1:4]]
    else:
        primary_language = None
        secondary_languages = []

    # Languages with percentages
    languages_pct = {
        lang: round((loc / total_loc * 100), 2) if total_loc > 0 else 0
        for lang, loc in language_loc.most_common()
    }

    # Dependencies
    dependencies = parse_dependencies(repo_root)

    # Tech debt
    tech_debt = count_tech_debt(repo_root)

    # Manifests present
    manifests_present = []
    for manifest in MANIFEST_FILES:
        if list(repo_root.rglob(manifest))[:1]:
            manifests_present.append(manifest)

    # CI present
    ci_present = False
    ci_files_found = []
    for pattern in CI_FILES:
        if list(repo_root.rglob(pattern))[:1]:
            ci_present = True
            ci_files_found.append(pattern)

    # README present
    readme_present = any((repo_root / r).exists() for r in README_FILES)

    # License present
    license_present = any((repo_root / l).exists() for l in LICENSE_FILES)

    # Git metadata
    last_commit_date = get_git_last_commit(repo_root)
    git_remote = get_git_remote(repo_root)

    # Test-to-source ratio
    test_to_source_ratio = (
        test_file_count / source_file_count if source_file_count > 0 else 0
    )

    # Tech debt density (markers per 1000 LOC)
    tech_debt_density = (
        tech_debt["total_markers"] / (total_loc / 1000) if total_loc > 0 else 0
    )

    return {
        "scan_version": SCRIPT_VERSION,
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_root": str(repo_root),
        "total_files_scanned": total_files_scanned,
        "languages": dict(language_files),
        "languages_by_loc": dict(language_loc),
        "languages_pct": languages_pct,
        "primary_language": primary_language,
        "secondary_languages": secondary_languages,
        "total_loc": total_loc,
        "file_count_by_ext": dict(file_count_by_ext),
        "source_file_count": source_file_count,
        "test_file_count": test_file_count,
        "test_to_source_ratio": round(test_to_source_ratio, 4),
        "avg_file_loc": round(avg_file_size, 2),
        "largest_file_loc": largest_file_loc,
        "largest_file_path": largest_file_path,
        "dependency_count": len(dependencies),
        "dependencies": dependencies,
        "manifests_present": manifests_present,
        "ci_present": ci_present,
        "ci_files_found": ci_files_found,
        "readme_present": readme_present,
        "license_present": license_present,
        "tech_debt": tech_debt,
        "tech_debt_density_per_1k_loc": round(tech_debt_density, 2),
        "last_commit_date": last_commit_date,
        "git_remote": git_remote,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Factual codebase scanner")
    parser.add_argument("path", help="Path to the codebase root")
    parser.add_argument("--output", "-o", help="Write to file instead of stdout")
    parser.add_argument("--version", action="version", version=f"codebase_scanner.py v{SCRIPT_VERSION}")
    args = parser.parse_args()

    result = scan(Path(args.path))
    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote scan to {args.output}", file=sys.stderr)
    else:
        print(output)

    if "error" in result:
        sys.exit(2)


if __name__ == "__main__":
    main()
