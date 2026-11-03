---
description: "Prepare a version and publish it through the release workflow."
---

# Releasing

Releases are published through
[the Release workflow](https://github.com/sbroenne/pytest-copilot/actions/workflows/release.yml).
The checked-in `project.version` in `pyproject.toml` determines the version.
The workflow creates its matching tag; no manual tagging is required.

Pushing a new, untagged version to `main` automatically starts the release
workflow through Auto Release. Merge a version bump only when publication is
intended. Preparing a version bump on a separate branch does not publish it.
A maintainer can also dispatch Release manually, including when retrying a
failed release.

## Before dispatching

### First release under the new name

Version 2.0.0 changes the package name from `pytest-skill-engineering` to
`pytest-copilot`. The existing GitHub repository should be renamed to
`sbroenne/pytest-copilot`, not replaced. Existing Git tags and PyPI distributions
are preserved. GitHub releases older than 2.0.0 and their attached downloads were
removed after the rename; their source remains available through the Git tags.

Before merging this version into `main`, the owner must configure a PyPI
pending trusted publisher for the new package with:

- PyPI project: `pytest-copilot`
- GitHub owner: `sbroenne`
- GitHub repository: `pytest-copilot`
- Workflow filename: `release.yml`
- Environment: `pypi`

The old package's publisher does not publish to the new package. A missing PyPI
project page does not guarantee that the new name can be registered. Resolve
name or publisher setup problems before merging; otherwise Auto Release can
create a tag and build artifacts before publication fails.

Update local remote URLs and the Copilot app's repository association using
supported settings after the repository rename. Do not manually move its
managed checkouts. GitHub redirects normal repository links and Git operations,
but the GitHub Pages project address changes: deploy and verify
`https://sbroenne.github.io/pytest-copilot/`. Do not reuse the former repository
name for another project, as that removes the repository redirect.

### Retire the old PyPI package

After the new package is published and its installation has been verified,
publish a final `pytest-skill-engineering` 1.0.8 release from the last 1.x source.
Keep that release's existing implementation and dependency names intact; change
only the version, release notes, description, links, and development status.
Use `Development Status :: 7 - Inactive` and place this notice at the top of
its README:

> This package has moved to **pytest-copilot** and will receive no further
> updates under this name. Install `pytest-copilot>=2.0.0,<3`; update imports
> to `pytest_copilot`, `CopilotEval` to `CopilotTask`, and `copilot_eval` to
> `copilot_run`. See the [migration guide](https://sbroenne.github.io/pytest-copilot/migration/).

Do not publish renamed 2.x code under the old distribution name or add a package
that silently installs the replacement. Do not reuse the new package's release
workflow to publish the final old-name release: it deliberately accepts only
`pytest-copilot` artifacts. Build the final 1.x release separately and use an
authorized publisher for the old PyPI project.
The manually started `retire-old-package.yml` workflow builds 1.0.8 from the
fixed pre-rename commit, changes only its package metadata and README, and checks
that every packaged Python file is unchanged. It has separate publishing
permission for `pytest-skill-engineering`; it does not create a new 2.x release
or deploy the old documentation. Start it only to publish the final move notice.
If the old project's trusted publisher still names the former GitHub repository,
update it through the PyPI owner settings before using it after the repository
rename. GitHub's repository redirects do not update a PyPI publisher identity.

Once its final description is visible on PyPI, the owner can archive
`pytest-skill-engineering` in its PyPI project settings. Archiving displays a
notice and blocks new uploads, but preserves downloads of existing releases.
Do not delete the project or yank working releases merely for a rename.
See [PyPI's archival guidance](https://blog.pypi.org/posts/2025-01-30-archival/).
Installing an archived package does not necessarily print a warning, so the
final description must clearly identify the replacement.

### Source checks

Confirm that the intended release commit contains:

1. The reviewed source and intended `project.version`, using plain `X.Y.Z`.
2. The directly related documentation and migration guidance.
3. Passing validation for the changed behavior, plus a strict docs build and package build.
4. Evidence contracts that preserve current schema-4.0 fields and failure paths.

Use the [contribution guide](https://github.com/sbroenne/pytest-copilot/blob/main/CONTRIBUTING.md)
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

Every GitHub release includes the wheel (`.whl`) and source archive (`.tar.gz`),
not just links to PyPI. Both newly created releases and release retries attach
the built packages. Users can
[install the downloaded wheel directly](../getting-started/index.md#install-from-a-release-download)
without downloading pytest-copilot itself from PyPI.

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
