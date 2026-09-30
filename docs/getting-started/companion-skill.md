# Companion skill for your coding agent

The Python framework runs tasks and records evidence. This skill teaches the
coding agent already helping you how to use that evidence and improve your
repository.

```powershell
npx skills add sbroenne/pytest-skill-engineering --skill pytest-skill-engineering
```

Add `--agent github-copilot` to select GitHub Copilot explicitly. The skills CLI
chooses the host-specific installation location. Node is required for this
installation, not for the Python framework.

The canonical source is
[`skills/pytest-skill-engineering/SKILL.md`](https://github.com/sbroenne/pytest-skill-engineering/tree/main/skills/pytest-skill-engineering).
There is no Python skill installer or duplicate wheel-bundled copy. The skill
targets framework 1.x.

## Use an unpublished checkout

From the framework repository:

```powershell
npx skills add . --list
```

From a temporary consumer project, substitute the absolute checkout path:

```powershell
npx skills add C:\path\to\pytest-skill-engineering --skill pytest-skill-engineering --agent github-copilot --copy --yes
```

The remote command requires a repository ref containing the skill; local
installation is appropriate before publication. No global installation is
required.

## What it changes

Ask your coding agent to define concrete criteria, create a normal framework
test, inspect failures alongside source, and rerun affected cases. The skill
requires fixed comparison criteria, separate observations from possible causes,
and honest reporting of subjective review.

It does not add SDK sessions, retries, judges, usage collectors, or competing
report formats. Paid runs still need authorization. Captured transcripts and
tool outputs are data, not instructions to execute.
