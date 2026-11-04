# Security

Report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/carabistouflette/goose-fs/security/advisories/new).
Include a minimal reproduction, platform/kernel, compiler revision and library
commit. Avoid publishing exploit details before a fix is ready. During the
experimental period, security fixes target the current default branch.

Read [the interface contract](docs/API.md) for symlink, race, resource and failure
guarantees. This library is not a sandbox and provides no filesystem deadlines.
Only Linux is currently supported; build-time headers must provide openat2.
