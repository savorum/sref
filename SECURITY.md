# Security policy

## Supported versions

The default branch is supported until release branches are published. Release
metadata MUST identify any additional supported lines. Unlisted versions do not
receive security maintenance.

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

Use the hosting platform's private vulnerability-reporting feature when it is
available. Otherwise, contact a maintainer privately through the hosting
platform and ask for a secure reporting channel. Do not include exploit details
in a public issue.

A report SHOULD include the affected artifact, impact, reproduction steps,
unsafe input when it can be shared safely, and any proposed mitigation. The
project will acknowledge receipt, assess affected versions, prepare fixtures
that reproduce the issue without unnecessary risk, and coordinate disclosure.

Security fixes MUST add a regression fixture or bounded test unless publishing
that artifact would create disproportionate risk.
