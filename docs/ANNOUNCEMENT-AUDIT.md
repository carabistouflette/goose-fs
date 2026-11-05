# Documentation audit

Task GL-DOCSFS-01 reviews the public reader path before an upstream announcement.
It does not open a discussion or change the library API.

The runtime baseline is `60cec1e1956962772fff6091b4c7ff1876533f9e`. Changes here
are documentation, example error handling and an offline audit script. README
contains the short setup/use path; API guides retain the precise ownership,
no-follow, bounds, error, close and non-snapshot contracts.

[The audit inventory](announcement-audit.json) lists every Markdown file, every
published benchmark profile, source/dependency comparisons and local links.
[Performance scope](PERFORMANCE.md) explains which evidence matches this runtime,
which remains historical, and missing old provenance. Raw artifacts and tags are
not changed. No new performance claim or benchmark run is introduced.

[Example validation](example-validation.json) records a fresh anonymous-clone
`make setup`, the three README commands, API checks and nine success/error cases
with both the recorded compiler and the freshly built compiler. All completed
with exit status 0 within the coordinator's finite correctness window. This is
command validation, not a benchmark. Final exact-commit CI is linked in the
publication handoff. The script below checks the source bridge, historical artifact
bytes, local links and derived dispersion without timing library code:

```sh
python3 scripts/audit-docs.py --output .build/docs-audit.json \
  --dispersion .build/dispersion.json
```

The optional --goose flag requires the original recorded compiler/dependency
identities, rather than silently accepting another build. Existing measurements
are explicitly platform-specific and do not prove universal leadership.
