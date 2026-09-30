# Security policy

## Supported versions

The latest release and the default branch are supported. Release metadata MUST
identify any additional supported lines. Unlisted versions do not receive
security maintenance.

## Security-sensitive areas

Implementations MUST treat all SREF content as untrusted input. Important risk
areas include:

- ZIP path traversal and absolute paths;
- symbolic or hard links;
- duplicate archive entries;
- decompression bombs and excessive entry counts;
- misleading file extensions or media types;
- oversized integers, rationals, strings, and images;
- deeply nested JSON;
- invalid or confusing Unicode paths and identifiers;
- external links and remote asset fetching; and
- unsafe rendering of imported text, markup, or media.

The package rules in [spec.md](spec.md) and
[docs/package-format.md](docs/package-format.md) are minimum requirements, not a
complete implementation threat model.

## Reporting

Report a vulnerability privately through
[GitHub private vulnerability reporting](https://github.com/savorum/sref/security/advisories/new).
Do not include exploit details in a public issue.

A report SHOULD include the affected artifact, impact, reproduction steps,
unsafe input when it can be shared safely, and any proposed mitigation.

The project acknowledges a report within 7 days and assesses affected versions.
It prepares fixtures that reproduce the issue without unnecessary risk and
coordinates disclosure with the reporter. The disclosure timeline is 90 days
from the report, or earlier when a fix is released.

A confirmed vulnerability is published as a GitHub security advisory once a fix
is available, naming the affected and fixed versions.

Security fixes MUST add a regression fixture or bounded test unless publishing
that artifact would create disproportionate risk.
