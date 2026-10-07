---
name: release-notes-drafter
description: Drafts release notes from the merged pull requests since the last git tag. Use when a maintainer asks for a changelog entry, release notes, or a summary of what changed since the previous release.
---

# Release Notes Drafter

Draft release notes from the merged pull requests since the last tag.

1. Run `git log --merges --oneline <last-tag>..HEAD` and collect the PR titles.
2. Group the titles under Added, Changed, and Fixed.
3. Write one plain sentence per entry. Do not invent changes that are not in the log.
4. Stop and ask the maintainer if the last tag cannot be determined.
