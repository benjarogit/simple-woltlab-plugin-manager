# Version-specific WoltLab references

SWPM supports individual plugins, apps and arbitrary package families. A package's WCF dependency determines its target; a family manifest is selected explicitly. Existing downloads and the newest GitHub branch do not determine compatibility.

Run from the SWPM repository:

```bash
# Read-only check of an explicitly selected development line.
./tools/update-woltlab-version.sh --check --refs-only 6.3

# Synchronize clean references separately for this line.
./tools/update-woltlab-version.sh --refs-only 6.3

# Check another package using its own WCF dependency.
./tools/update-woltlab-version.sh --check --refs-only --package /path/to/package
```

Each line uses `.references/X.Y/`. An optional `WOLTLAB_REFERENCES_ROOT` identifies one exact line root, not its parent. Existing manager-root references remain intact and are not migrated automatically. Use `--legacy-root --check` for explicit read-only inspection, or select that root explicitly.

`reference-lock.json` records source URLs, branches and commits. Core release archives have separate version/hash provenance. A Git development line does not imply an available stable Core ZIP; `--refs-only` downloads none. Missing lines, mismatched pins, local changes and incompatible Core versions fail instead of falling back to another latest line.

Build and validation check the package's compatibility, selected Core and typings. To select a reference set explicitly:

```bash
WOLTLAB_REFERENCES_ROOT=/path/to/SWPM/.references/6.3 \
  ./tools/build.sh /path/to/package same
```

An explicit `WOLTLAB_CORE_REFERENCE` must satisfy the same compatible line. Compiler paths are never silently rewritten. Currently the checker requires JSON with direct compiler paths; inherited `tsconfig` configurations fail and require explicitly resolved inputs. This limitation is not a successful TypeScript check.

Reference synchronization does not update an installed test suite. Source checks, package builds, live acceptance and GitHub CI remain separate evidence.

Managed references must be standalone Git checkouts with their own Git directory inside the reference path. Redirected `core.worktree` paths, shared Git directories and linked worktrees are rejected. Symbolic links in the reference path require an explicitly selected canonical destination.
