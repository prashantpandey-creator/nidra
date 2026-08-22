---
name: commands-not-paths
description: "A backticked span may be a COMMAND. The path ends where the flags begin."
metadata:
  type: reference
---
Always run `~/tools/preflight.sh --human` first, then
`/Users/dev/bin/build.sh --clean --verbose` to rebuild. Plain invocation is
still a path claim: `~/tools/status.sh`. A shell pipeline is not a path:
`cat ~/tools/list.txt | head -3`.
