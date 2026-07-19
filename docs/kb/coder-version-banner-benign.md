---
title: "Coder CLI 'version mismatch' banner on every coder/ssh command is benign noise"
tags: [environment, coder-workspace, tooling]
source: CLAUDE.md environment-noise section
phase: p00
confidence: verified
last_updated: 2026-07-19
---

Every `coder`/`ssh wingo.coder` invocation prints:

```
version mismatch: client v2.34.3+... / server v2.29.6+...
download v2.29.6+... with: 'curl -fsSL https://coder.nut.eg/install.sh | sh'
```

This is Coder CLI/server version skew, unrelated to the build — ignore it,
never treat it as a failure, never try to "fix" it (don't run the suggested
install command). Judge a remote command's success purely by ITS OWN exit
code and output, filtering this banner out mentally (or with
`grep -v "version mismatch\|download v2"`) rather than letting it clutter
diagnosis of a real failure.
