---
description: "How to release a new version of pytest-skill-engineering"
---

# Releasing

This guide explains how to create a new release of pytest-skill-engineering.

## Release Process

Releases are triggered via **GitHub Actions workflow dispatch**. No manual tagging is required.

### Steps

1. Navigate to [Actions → Release](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/release.yml)
2. Click **"Run workflow"**
3. Select the branch (typically `main`)
4. Confirm you are running from the commit whose checked-in `project.version` you want to release
5. Click **"Run workflow"**

## What Happens During Release

The release workflow automatically:

1. **Validates checked-in metadata** — Reads `pyproject.toml`, requires plain `X.Y.Z`, and verifies it agrees with any existing tag on the commit
2. **Creates the matching git tag** — If `vX.Y.Z` does not exist yet, the workflow creates it from the current commit
3. **Builds from the tag** — The package build runs from a checkout of `vX.Y.Z`, so the tagged source is the release source of truth
4. **Verifies artifacts** — Confirms source metadata, wheel metadata, sdist metadata, and an installed wheel all report the same version
5. **Publishes to PyPI** — Uploads the package using trusted publishing
6. **Creates GitHub release** — Generates release notes and attaches artifacts
7. **Deploys documentation** — Builds docs from the same tag and fails if docs source metadata drifts

## Version Management

!!! note "Version source of truth"
    `pyproject.toml` is the release source of truth. The checked-in `project.version` must already be the version you intend to publish, and the matching `vX.Y.Z` tag must resolve to that exact source tree.

The workflow scans existing `v*` tags only to prevent version regressions and to detect whether the matching tag already exists on the release commit.

## Pre-releases and Special Versions

Pre-releases and special versions still follow the same rule: update `project.version` in source first, then run the workflow from that commit.

## Troubleshooting

### Tag already exists

If the workflow fails with "Tag already exists", either:

- Run the workflow from the already-tagged commit if that is the intended release source
- Bump `project.version` in source and tag the new commit instead
- Delete the existing tag only if it was created in error

### Build or test failures

The workflow stops before tagging if build or tests fail. Fix the issues and re-run the workflow.

### PyPI publish failures

If PyPI publishing fails, the tag and release may already exist. You may need to:

1. Confirm the tagged source metadata is correct
2. Delete the GitHub release if it was partially created
3. Fix the issue
4. Re-run the workflow from the same tag if PyPI was not published, or bump the source version for a new release if it was

## Prerequisites

Releases require:

- **Maintainer access** to the repository
- **PyPI trusted publishing** configured (handled by GitHub Actions)
- **GitHub Pages** enabled for documentation deployment

Only repository maintainers can trigger releases.
