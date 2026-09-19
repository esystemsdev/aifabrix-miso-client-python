# push-release-branch

Prepare and promote the current development branch to
`release/miso-client-python-X.Y.0`, validate the release commit, and open a PR to
`main` for human review. Run from the `aifabrix-miso-client-python` root.

Process reference: [Deployment Guide](../../docs/DEPLOYMENT.md).
After the PR is merged, use `/push-github` to publish the approved version.

## Scope and approval

- Default source: the current development branch (`dev` or a feature branch).
  Record its name and finish on that branch. Reject detached HEAD and `main`;
  use a release branch as source only when explicitly requested.
- Never push directly to `main`, merge the PR, force-push, or publish to PyPI.
- Do not create a version tag here. `/push-github` tags the approved commit
  after merge, keeping publication tied to human approval.
- Preserve unrelated working changes; stage only reviewed release files.
- Existing explicit user authorization applies. Otherwise present the concrete
  changes and validation evidence before asking for commit/push approval.
  Use AskQuestion when available, or numbered choices in chat when unavailable.
- `/push-release-branch silent` combines commit and release-branch push into one
  approval after preparation and validation. It does not authorize publication.
  PR creation is a separate decision unless already explicitly requested.

## 1. Readiness and target selection

```bash
git branch --show-current
git status --short --branch
git fetch --prune origin
git branch -r --list 'origin/release/miso-client-python-*'
```

Record repository path, source branch, upstream ahead/behind state, modified and
untracked files, current version, and relevant changes since the previous release.
Check GitHub access and workflow availability. Never silently discard or stash
user changes. Stop for an unresolved merge or an unsafe upstream divergence.

Read and compare all version locations:

- `pyproject.toml` `[project].version`
- `setup.py` `version`
- `miso_client/__init__.py` `__version__`
- `.bumpversion.cfg` `current_version`

Resolve ambiguous version drift before preparing a release. A prepared version
must match the top versioned entry in `CHANGELOG.md`.

The target follows the **prepared version**, not whichever branch was updated
most recently: `X.Y.Z` targets `release/miso-client-python-X.Y.0`.
Sort release lines numerically by major/minor when reporting the latest line.
Do not merge a newer, unrelated release line into an older maintenance release.

Legacy branches such as `release/miso-client-python-4.20.2` may exist. Inspect
same-line legacy branches for commits absent from the source before creating
`release/miso-client-python-4.20.0`. Include required fixes through an ordinary
merge; resolve ambiguous competing histories with the user. Do not rename,
delete, or overwrite legacy branches automatically.

For an existing target, require its remote tip to be an ancestor of the source:

```bash
git merge-base --is-ancestor "origin/$releaseBranch" "$sourceBranch"
```

If not, merge the release fixes into the development source within the authorized
scope, then revalidate. Never bypass this check with a force push. Also inspect
`origin/main` for missing fixes; resolve conflicts on the source before promotion.

## 2. Prepare the version once

Use `/repair-release` when a new version is needed. Reuse an already prepared,
unpublished version whose metadata and changelog agree; resuming must not bump
again. Patch changes stay on the same release line; a minor or major bump selects
a new `X.Y.0` branch. Read the current date for changelog entries.

Check `https://pypi.org/pypi/miso-client/{version}/json`: HTTP 200 means already
published; choose a new version for changed package contents. Only HTTP 404 means
absent. Authentication, rate-limit, network, and server errors are blockers, not
proof that a version is available.

Inspect existing local and remote `vX.Y.Z` tags. If one exists, inspect its peeled
commit and publication state before proceeding. Never move or delete it. If a
release is already merged or published, resume `/push-github` verification rather
than preparing the same version again.

Do not use bare `bump2version`: this repository config enables automatic commits
and tags. Edit metadata directly or use `--no-commit --no-tag`.

## 3. Validate and commit

Run `make validate-silent` (fallback: `make validate` only if the wrapper is
unavailable). Read failures under `.temp/validation/`, fix relevant issues and
rerun affected gates until green. Report format, lint, basedpyright, type-check,
and test results accurately, including any skipped gate.

Show source, target, version, exact files, proposed commit message, validation
results, and whether the target branch will be created. Obtain any outstanding
commit/push authorization. Commit only reviewed files; never use `git add .` to
include unrelated work. Record the validated commit SHA.

## 4. Push the release branch

Fetch again and repeat the ancestry check against the target immediately before
pushing. A changed source commit requires fresh validation. Push the explicit
refspec (this also creates a missing remote target):

```bash
git push origin "$sourceBranch:refs/heads/$releaseBranch"
git fetch origin
git rev-parse "$sourceBranch"
git rev-parse "origin/$releaseBranch"
```

Require both SHAs to equal the validated release SHA. On a concurrent remote
update, synchronize and validate again; never force-push.

For IDE visibility, create a missing local tracking branch with
`git branch --track "$releaseBranch" "origin/$releaseBranch"`. An existing local
release branch may be advanced with `git merge --ff-only` after switching to it
in a clean worktree; return to the original source afterward. If it diverges or
is checked out in another worktree, report it without resetting it.

## 5. Verify release CI and CodeQL

Require the `Test` workflow to succeed for the exact pushed release SHA. Run the
existing manual security workflow on the release branch:

```bash
gh workflow run codeql-manual.yml --ref "$releaseBranch"
```

Select runs by workflow, branch, event and exact `headSha`, not simply the latest
run. Watch each selected run and report its URL. Missing runs or artifacts are
blockers. Download both `codeql-sarif-actions` and `codeql-sarif-python` into a
fresh directory under `.temp/codeql/<run-id>/`. Parse every SARIF file and require
zero `runs[].results[]` findings; successful workflow status alone is insufficient.

Fix findings on the development source, rerun local validation, commit/push the
release target within authorization, then repeat CI and CodeQL for the new SHA.
No earlier run certifies a changed commit.

## 6. PR to main

Show the base (`main`), head (`$releaseBranch`), version, release SHA, CI/CodeQL
URLs and proposed PR title/body. If PR creation is not already authorized, offer:
**Create PR (recommended)**, **Skip PR**, or **Stop**. In `silent` mode this remains
separate from the combined commit/push approval.

Reuse an existing open PR for the same head/base. Otherwise write the reviewed
body to a temporary file and run:

```bash
gh pr list --base main --head "$releaseBranch" --state open
gh pr create --base main --head "$releaseBranch" \
  --title "Release miso-client $version" --body-file "$prBodyFile"
```

The body describes delivered changes, version, release SHA and validation
results. Require PR checks and human review before merge. Do not merge from this
command. If the release tip changes, repeat validation and security checks.

## Completion

Report source → release branch, version, verified SHA, validation and CI results,
and the clickable PR URL for human review (or explicit PR decline). State that
publication follows merge via `/push-github`. Never report publication at this
stage. Finish on the original development branch.
