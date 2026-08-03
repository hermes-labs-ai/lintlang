# LintLang development workspace

This file answers one question: where should development begin?

## Canonical workspace

- Upstream repository: `https://github.com/hermes-labs-ai/lintlang.git`
- Hermes Labs maintainer checkout: `/Users/rbr_lpci/github-projects/lintlang`
- Codex local project: `lintlang`, with that checkout as its primary folder
- Claude Code: start it from that checkout:

  ```bash
  cd /Users/rbr_lpci/github-projects/lintlang
  claude
  ```

Codex and Claude Code should operate on this same Git repository. A task may use a linked worktree for isolation, but it should not create another clone merely to obtain a clean branch.

## Start every development task here

```bash
git remote get-url origin
git status --short --branch
git worktree list
```

Then read `AGENTS.md`, `INTENT.md`, and the relevant product documentation. Do not assume that local `main`, a release tag, or an old handoff equals the current public state. Select the intended base explicitly; public-facing changes normally begin from current `origin/main` unless the task names another branch or commit.

## Repository topology

- Paths reported by `git worktree list` are linked working trees that share this repository's history. Their branches may contain unfinished or intentionally isolated work.
- `/Users/rbr_lpci/Documents/projects/hermes-flagship-outsider-journey/lintlang` is a task-specific clone created for the August 2026 outsider-adoption mission. It is not the canonical development checkout. Preserve any unpushed commit there until it is deliberately adopted or retired.
- `/Users/rbr_lpci/ai-infra/_workspace/` contains staging, archaeology, evaluation, and reconciliation artifacts. These are evidence inputs, not alternate source-of-truth repositories.
- `/Users/rbr_lpci/Documents/Codex/` and `/Users/rbr_lpci/Documents/HAL/_handoffs/` contain task receipts, release artifacts, and review packets. They document prior work but do not supersede live Git state.
- `/Users/rbr_lpci/Documents/projects/hermes-labs-hackathon-2/lintlang` is a distinct `lintlang-v2` experiment inside another repository. Never use it to infer this package's version, branch, or release state.

Historical artifacts should keep their original paths and hashes for provenance. Do not move, duplicate, or delete them as part of routine onboarding.

## If this workspace ever moves

Move it only for a concrete technical reason. Preserve the Git repository and worktree relationships, then update all three durable routes together:

1. this file and `AGENTS.md`;
2. the `lintlang` entry in `~/.config/hermes/supersession-pointers.json` and durable memory;
3. the Codex local project's primary folder and Claude Code launch path.

A directory move is incomplete until all three routes agree.
