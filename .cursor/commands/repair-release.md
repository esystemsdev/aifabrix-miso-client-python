# repair-release

When the `/repair-release` command is used, the agent must automatically prepare the component for release by running validation, analyzing changes, updating the changelog, and incrementing the version number. The agent must work autonomously without asking the user for input.

**Execution Process:**

1. **Validation Step**:
   - First, run validation to ensure all tests pass, linting is clean, and the codebase is in a validated state
   - This includes: `make validate` (or equivalent: `ruff check`, `black`, `isort`, `pytest`)
   - Do not proceed until all validation steps pass

2. **Change Detection Step**:
   - Get the last deployed version from git tags (e.g., `v2.1.2`)
   - Compare current HEAD with the last tag to detect what has changed
   - Analyze git commit messages and file changes to categorize changes:
     - **New Features**: New services, new utilities, new functionality (minor version bump: 2.x.0)
     - **Bug Fixes**: Fixes, patches, corrections (patch version bump: 2.1.x)
   - Use git commands to get:
     - Commit messages since last tag: `git log <last-tag>..HEAD --oneline`
     - Changed files: `git diff <last-tag>..HEAD --name-status`
     - Summary of changes for changelog

3. **Version Determination Step**:
   - Read current version from `pyproject.toml` (e.g., `2.1.2`)
   - Also check `setup.py` and `miso_client/__init__.py` for version consistency
   - Determine version increment based on change analysis:
     - **Patch increment** (2.1.2 → 2.1.3): If only bug fixes, small corrections, or minor changes
     - **Minor increment** (2.1.2 → 2.2.0): If new features, new services, new utilities, or significant functionality added
   - Calculate new version number

4. **Changelog Update Step**:
   - Read `CHANGELOG.md` to understand the format
   - Extract changes from git commits since last tag
   - Categorize changes into sections:
     - `### Added` - New features, services, utilities, modules
     - `### Changed` - Modifications to existing functionality
     - `### Fixed` - Bug fixes and corrections
     - `### Technical` - Technical details, dependencies, architecture changes
   - Add new version entry at the top of CHANGELOG.md with:
     - Version number in format: `## [X.Y.Z] - YYYY-MM-DD`
     - Date in format: YYYY-MM-DD (current date)
     - Categorized changes from git analysis
   - Follow the existing changelog format and style

5. **Version Update Step**:
   - Update version in all required files:
     - `pyproject.toml`: Update `version = "X.Y.Z"` in `[project]` section
     - `setup.py`: Update `version="X.Y.Z"` in `setup()` call
     - `miso_client/__init__.py`: Update `__version__ = "X.Y.Z"`
     - `.bumpversion.cfg`: Update `current_version = X.Y.Z` (optional, for bumpversion tool)
   - Ensure formatting is preserved in each file

6. **Final Verification Step**:
   - Verify all version files were updated correctly
   - Verify CHANGELOG.md was updated with new entry
   - Verify changelog entry follows the correct format
   - Display summary of changes made

**Critical Requirements:**

- **Automatic Execution**: The agent MUST automatically execute all steps without user interaction
- **Validation First**: Always run validation first to ensure codebase is ready for release
- **Change Analysis**: Properly analyze git changes to determine version increment type
- **Changelog Format**: Follow the exact format used in existing CHANGELOG.md entries
- **Version Semantics**:
  - Patch (2.1.2 → 2.1.3): Bug fixes, small corrections, patches
  - Minor (2.1.2 → 2.2.0): New features, new services, new utilities, significant functionality
- **Date Format**: Use YYYY-MM-DD format for changelog dates
- **Git Tag Detection**: Use `git tag --sort=-version:refname` to find the latest version tag
- **Change Extraction**: Extract meaningful change descriptions from git commits
- **No User Input**: Work autonomously and only report completion when all steps are done
- **Version Consistency**: Update version in all three locations: `pyproject.toml`, `setup.py`, and `miso_client/__init__.py`

**Version Bump Rules:**

- **Patch Version (2.1.2 → 2.1.3)**: Use when changes include:
  - Bug fixes
  - Security patches
  - Small corrections
  - Documentation updates (if only docs)
  - Code quality improvements (refactoring, linting fixes)
  - Performance optimizations (without new features)
  - Test improvements
  - Type definition fixes

- **Minor Version (2.1.2 → 2.2.0)**: Use when changes include:
  - New services (AuthService, RolesService, etc.)
  - New utilities (HTTP client, config loader, etc.)
  - New features or functionality
  - New configuration options
  - Breaking changes (should be rare, but if they occur, use minor version)
  - Significant enhancements to existing features
  - New type definitions or interfaces

**Work is only complete when:**
- ✅ All validation tests pass (via `make validate` or equivalent)
- ✅ Changes have been analyzed from git
- ✅ Version number has been determined and incremented
- ✅ CHANGELOG.md has been updated with new version entry
- ✅ All version files have been updated (`pyproject.toml`, `setup.py`, `miso_client/__init__.py`)
- ✅ All changes follow the project's format and standards
