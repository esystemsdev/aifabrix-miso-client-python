# tag-and-push-release

When the `/tag-and-push-release` command is used, the agent must create a git tag based on the version in config files and push both commits and tag to origin. This command assumes the user has already committed all release changes locally.

**Prerequisites:**
- All release changes must be committed locally (run `/repair-release` first, then commit)
- No uncommitted changes should exist
- Local branch should be ready to push

**Execution Process:**

1. **Pre-flight Checks:**
   - Check for uncommitted changes: `git status --porcelain`
   - If uncommitted changes exist, STOP and inform user to commit first
   - Fetch from origin: `git fetch origin`
   - Check if local is behind origin: `git status -uno`
   - If behind origin, WARN user and ask if they want to pull/merge first before tagging

2. **Read Version:**
   - Extract version from `pyproject.toml` using regex: `version = "X.Y.Z"`
   - Verify version format matches semantic versioning (X.Y.Z)
   - Display the version that will be tagged

3. **Verify Tag Doesn't Exist:**
   - Check if tag `vX.Y.Z` already exists locally: `git tag -l "vX.Y.Z"`
   - Check if tag exists on remote: `git ls-remote --tags origin "refs/tags/vX.Y.Z"`
   - If tag exists, STOP and inform user (tag already exists)

4. **Create Tag:**
   - Create annotated tag: `git tag -a vX.Y.Z -m "Release version X.Y.Z"`
   - Annotated tags include tagger info and timestamp

5. **Push to Origin:**
   - Push commits: `git push origin HEAD`
   - Push tag: `git push origin vX.Y.Z`
   - Verify push succeeded

6. **Verify Tag on Remote:**
   - Confirm tag exists on remote: `git ls-remote --tags origin "refs/tags/vX.Y.Z"`

7. **Final Summary:**
   - Display success message with tag name and commit hash
   - Note that pushing the tag automatically triggers `publish.yml` workflow
   - PyPI publish will run automatically (no manual GitHub Release needed)

**Critical Requirements:**

- **No Auto-Commit**: This command does NOT commit changes - user must commit first
- **Safety First**: Always check for uncommitted changes before proceeding
- **Behind Origin Warning**: If local is behind origin, warn user and suggest pulling first
- **No Force Push**: Never use `--force` flags
- **Annotated Tags**: Use annotated tags (`-a`) for better metadata
- **Version Source**: Always read version from `pyproject.toml` as source of truth
- **Tag Format**: Tags must be in format `vX.Y.Z` (e.g., `v4.1.0`)

**Error Handling:**

- If uncommitted changes exist: "Please commit your changes first before tagging"
- If local is behind origin: "Your local branch is behind origin. Run `git pull` first to avoid issues"
- If tag already exists: "Tag vX.Y.Z already exists. Delete it first if you need to re-tag"
- If push fails: Display the error and suggest checking remote permissions

**Example Workflow:**

```bash
# User runs /repair-release first (updates version + changelog)
# User reviews changes
git add -A
git commit -m "Release version 4.1.0"
# User runs /tag-and-push-release
# Agent creates tag v4.1.0 and pushes everything
# Tag push automatically triggers publish.yml -> PyPI publish
```

**Work is only complete when:**
- ✅ No uncommitted changes verified
- ✅ Version extracted from pyproject.toml
- ✅ Tag vX.Y.Z created locally
- ✅ Commits pushed to origin
- ✅ Tag pushed to origin
- ✅ Tag verified on remote
- ✅ Summary displayed (PyPI publish triggered automatically)
