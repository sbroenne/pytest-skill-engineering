---
description: "How to release a new version of pytest-skill-engineering"
---

# Releasing

This guide explains how to create a new release of pytest-skill-engineering.

## Release Process

Releases are triggered via **GitHub Actions workflow dispatch**. No manual tagging or version updates are required.

### Steps

1. Navigate to [Actions → Release](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/release.yml)
2. Click **"Run workflow"**
3. Select the branch (typically `main`)
4. Choose the version bump type:
   - **patch** (default) — Bug fixes, backwards-compatible changes
   - **minor** — New features, backwards-compatible
   - **major** — Breaking changes
5. Optionally, specify a custom version to override automatic versioning
6. Click **"Run workflow"**

### Version Bump Examples

| Current | Bump Type | New Version |
|---------|-----------|-------------|
| 0.2.0   | patch     | 0.2.1       |
| 0.2.0   | minor     | 0.3.0       |
| 0.2.0   | major     | 1.0.0       |

Custom versions can be any valid semver string (e.g., `1.2.3`, `2.0.0-beta.1`).

## What Happens During Release

The release workflow automatically:

1. **Calculates version** — Fetches the latest git tag and increments based on your selection
2. **Updates pyproject.toml** — Writes the new version to the package metadata
3. **Builds package** — Creates wheel and source distribution
4. **Tests build** — Installs and verifies the package
5. **Creates git tag** — Tags the commit with the version (e.g., `v0.2.1`)
6. **Publishes to PyPI** — Uploads the package using trusted publishing
7. **Creates GitHub release** — Generates release notes and attaches artifacts
8. **Deploys documentation** — Updates the docs site with the new version

## Version Management

!!! note "No manual version updates"
    The version in `pyproject.toml` is automatically updated during the release workflow. **Do not** manually edit it before releasing.

The workflow uses `git describe --tags --abbrev=0` to find the latest release tag. If no tags exist, it starts from `v0.0.0`.

## Custom Versions

Use custom versions for special releases:

```yaml
# Pre-release versions
custom_version: 1.0.0-alpha.1
custom_version: 2.0.0-beta.2
custom_version: 1.5.0-rc.1

# Specific version
custom_version: 3.2.1
```

Custom versions bypass automatic version calculation. Ensure they follow semantic versioning.

## Troubleshooting

### Tag already exists

If the workflow fails with "Tag already exists", either:

- Use a custom version that hasn't been released
- Delete the existing tag if it was created in error
- Increment the version manually

### Build or test failures

The workflow stops before tagging if build or tests fail. Fix the issues and re-run the workflow.

### PyPI publish failures

If PyPI publishing fails, the tag and release already exist. You may need to:

1. Delete the tag: `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z`
2. Delete the GitHub release
3. Fix the issue
4. Re-run the workflow

## Prerequisites

Releases require:

- **Maintainer access** to the repository
- **PyPI trusted publishing** configured (handled by GitHub Actions)
- **GitHub Pages** enabled for documentation deployment

Only repository maintainers can trigger releases.
