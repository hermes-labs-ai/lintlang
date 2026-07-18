# Preflight examples

Run these only against the unreleased Track B candidate:

```bash
printf '%s' 'Is it true that remote work always reduces productivity?' \
  | lintlang preflight - --include-snippets

printf '%s' 'What evidence supports or refutes whether remote work always reduces productivity?' \
  | lintlang preflight -

printf '%s' 'Make a video about alligators.' \
  | lintlang preflight - --context examples/preflight/video-context.json --format json
```

The first command is the hero path, the second is its matched hard negative, and
the third proves explicit context materialization without history mining or a
provider call. The default output is redacted; `--include-snippets` deliberately
reveals local evidence and correction text.
