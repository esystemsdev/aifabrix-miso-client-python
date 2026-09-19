# push-github

Publish an approved `miso-client` version **after** its release-branch PR has been
merged into `main`. Run from the `aifabrix-miso-client-python` root.

Use [/push-release-branch](push-release-branch.md) first for development → release
branch → PR preparation. See the [Deployment Guide](../../docs/DEPLOYMENT.md).
This command never bumps versions, merges PRs, or pushes to `main`.

## 1. Verify the approved release

1. Fetch origin and tags; record the original local branch and preserve its work.
2. Identify the merged PR from `release/miso-client-python-X.Y.0` to `main` for
   the requested version. An open or unmerged PR stops publication.
3. Record the PR URL, approved head SHA and merge commit SHA. Verify the merge
   commit is reachable from `origin/main`. Read the version and changelog at that
   commit, not from the current development worktree or a newer `main` tip.
4. Require matching versions in `pyproject.toml`, `setup.py`,
   `miso_client/__init__.py`, `.bumpversion.cfg`, and `CHANGELOG.md`.
5. Require successful PR checks and the zero-finding CodeQL evidence for the
   approved release head. Require `Test` for the selected main merge commit; run
   manual CodeQL on that immutable commit's tag before publishing (step 2).
6. Check PyPI version availability. HTTP 404 allows publication; HTTP 200 means
   already published and requires verification/resume, never an overwrite.
   Any other response or network failure stops publication.
7. Inspect local and remote `vX.Y.Z`. Peel annotated tags to commits. Existing
   tags must identify the selected approved merge commit; otherwise stop without
   moving, deleting or force-updating them.

## 2. Tag and publish

Show the version, merged PR URL, immutable merge SHA, tag state, proposed release
notes and validation evidence. Obtain outstanding authorization for tag creation,
tag push and GitHub Release publication; reuse explicit authorization already
given. Use AskQuestion if available, otherwise numbered choices in chat.

Create a missing annotated tag on the verified merge SHA and push only that tag:

```bash
git tag -a "$releaseTag" "$mergeSha" -m "Release miso-client $version"
git push origin "refs/tags/$releaseTag:refs/tags/$releaseTag"
```

Skip completed actions when resuming. Verify the remote peeled tag equals the
approved merge SHA. Never use `--tags` or force options.

Run `codeql-manual.yml` with `--ref "$releaseTag"`. Require its exact `headSha`
to equal the merge SHA and inspect both fresh SARIF artifacts using the procedure
in `/push-release-branch`. Stop on failure, missing artifacts, or findings.

Create the release only after these checks, using a notes file containing the
version's changelog and installation command. Do not claim PyPI publication yet:

```bash
gh release create "$releaseTag" --verify-tag \
  --title "@aifabrix/miso-client-python v$version" \
  --notes-file "$releaseNotesFile"
```

Reuse an existing published release rather than creating a duplicate. Publishing
triggers `.github/workflows/publish.yml`; pushing a tag alone does not.

## 3. Verify publication and recover

Monitor the `publish.yml` release-event run for the exact tag/merge SHA and report
its URL. Require success and HTTP 200 for the intended version on PyPI before
claiming completion. A successful skipped job is not evidence of a new upload.

For transient publication failures, inspect logs and retry the failed run within
existing authorization. If using manual dispatch, pin it to the verified tag:

```bash
gh workflow run publish.yml --ref "$releaseTag" -f "version=$version"
```

The input must equal the package metadata at that tag. Never retry against a
moving `main` tip. Source/workflow fixes go through development → release branch
→ reviewed PR again; use a new version/tag for changed release contents. Never
replace existing PyPI artifacts or move an existing tag.

Return the PR, GitHub Release, workflow and PyPI links with the verified version
and SHA. Preserve the original development branch and local work.
