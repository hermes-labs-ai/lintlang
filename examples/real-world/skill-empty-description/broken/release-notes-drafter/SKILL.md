---
name: release-notes-drafter
description:
---

# Release Notes Drafter

Draft release notes from the merged pull requests since the last tag.

1. Run `git log --merges --oneline <last-tag>..HEAD` and collect the PR titles.
2. Group the titles under Added, Changed, and Fixed.
3. Write one plain sentence per entry. Do not invent changes that are not in the log.
4. Stop and ask the maintainer if the last tag cannot be determined.
