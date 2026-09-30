# Invalid registry cases

Each JSON document in this directory violates one registry invariant while
remaining otherwise small enough to diagnose. The conformance manifest records
the required error category for every case.

The cases cover duplicate unit identities, missing or cyclic conversion bases,
nonpositive multipliers, affine definitions outside temperature, multiple base
units for one dimension, case-folded alias duplication, invalid replacement
state, active units without parser aliases, duplicate alias-set scopes, invalid
language tags, and physical units without a cited source.

Add a case here whenever a registry rule cannot be enforced by JSON Schema
alone. A structural rejection MAY also live here when it protects an immutable
unit identity or conversion rule.
