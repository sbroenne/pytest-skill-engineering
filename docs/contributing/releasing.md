---
description: "Prepare a version and publish it through the release workflow."
---

# Releasing

Releases are published through
[the Release workflow](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/release.yml).
The checked-in `project.version` in `pyproject.toml` determines the version.
The workflow creates its matching tag; no manual tagging is required.

Pushing a new, untagged version to `main` automatically starts the release
workflow through Auto Release. Merge a version bump only when publication is
intended. Preparing a version bump on a separate branch does not publish it.
A maintainer can also dispatch Release manually, including when retrying a
failed release.

## Before dispatching

Confirm that the intended release commit contains:

1. The reviewed source and intended `project.version`, using plain `X.Y.Z`.
2. The directly related documentation and migration guidance.
3. Passing validation for the changed behavior, plus a strict docs build and package build.
4. Evidence contracts that preserve current schema-4.0 fields and failure paths.

Use the [contribution guide](https://github.com/sbroenne/pytest-skill-engineering/blob/main/CONTRIBUTING.md)
for the applicable source and execution checks. For docs and packaging:

```bash
uv run --frozen python -X utf8 -m mkdocs build --strict
uv build
```

Do not hand-edit saved JSON to make it match a new schema. Fix its producer and
regenerate. Check that evidence loads without starting Copilot, preserves
unknown values and images, and retains failed setup/cleanup outcomes.

The quickstart should match the current API. Historical examples must keep
their frozen fixtures and default to offline checks; paid comparisons require
explicit authorization. There is no framework companion skill or report
renderer to publish.

## Dispatch the release

Open the Release workflow, choose **Run workflow**, and select the branch or
tag containing the intended release commit. Verify that commit's
`project.version` before confirming.

This requires maintainer access. PyPI trusted publishing and GitHub Pages must
already be configured.

## What the workflow does

| Stage | Behavior |
| --- | --- |
| Validate source | Require plain `X.Y.Z`, reject version regressions, and check tag/PyPI provenance |
| Create tag | Create `vX.Y.Z` at the release commit if it does not already exist |
| Build | Check out that tag and build the wheel and source distribution |
| Verify artifacts | Compare source, wheel, sdist, and installed-wheel versions |
| Publish to PyPI | Use trusted publishing; skip an already published version with valid provenance |
| Create GitHub release | Create the release or refresh its attached artifacts |
| Deploy docs | Build and deploy from the same release tag |

An existing matching tag must point to the workflow commit. The workflow
rejects a reused version on a different commit. Pre-release and special
versions are not supported without an explicit workflow change.

## Recover from a failure

Inspect the failed stage before rerunning. Later failures may leave a valid tag,
published package, or GitHub release in place.

| Failure | Action |
| --- | --- |
| Version/tag mismatch | Select the intended tagged commit, or prepare a new source version for changed code |
| Build or artifact verification | Determine whether the tag was created; source fixes need a new version if the old tag is retained |
| PyPI publication | Check whether the version was actually published before retrying |
| GitHub release or docs | Retry from the same tagged source when only the downstream operation failed |

A published PyPI version cannot be replaced with different artifacts. If source
must change after publication, prepare a new version. Do not delete or move a
release tag merely to bypass a provenance check.
