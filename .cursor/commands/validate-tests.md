# validate-tests

When the `/validate-tests` command is used, the agent must automatically fix all errors and ensure all validation steps pass. The agent must work autonomously without asking the user for input or showing intermediate progress.

**Execution Process:**

1. **Format Step**:
   - Run `make format` (or `black miso_client/ tests/` and `isort miso_client/ tests/`) to automatically fix formatting issues
   - If format fails or produces errors, automatically fix the issues in the codebase
   - Re-run format until it passes (exit code 0)
   - Do not proceed until format step is green

2. **Lint Check Step**:
   - Run `make lint` (or `ruff check miso_client/ tests/`) to check for remaining linting errors
   - If linting fails, automatically fix all linting errors in the codebase
   - Re-run lint until it passes (exit code 0)
   - Do not proceed until lint step is green

3. **Type Check Step** (Optional but Recommended):
   - Run `make type-check` (or `mypy miso_client/ --ignore-missing-imports`) to check for type errors
   - If type checking fails, automatically fix type errors where possible
   - Re-run type-check until it passes or has acceptable warnings (exit code 0)
   - Do not proceed until type-check step is green or acceptable

4. **Test Step**:
   - Run `make test` (or `pytest tests/ -v`) to run all tests
   - If tests fail, automatically fix all test failures
   - Re-run tests until all tests pass (exit code 0)
   - Do not proceed until test step is green
   - **All tests MUST be mocked** - no real database connections, external API calls, or I/O operations
   - **Test execution time MUST be reasonable** - if tests take too long, optimize by ensuring all external dependencies are properly mocked (httpx, redis, etc.)

5. **Final Verification Step**:
   - Run `make format` again to ensure no formatting changes were introduced
   - Run `make lint` again to ensure no linting issues were introduced
   - If format or lint made any changes, run `make test` again to verify tests still pass
   - Continue this loop until format and lint make no changes AND tests pass
   - This ensures the codebase is in a stable, validated state

**Critical Requirements:**

- **Automatic Error Fixing**: The agent MUST automatically fix all errors found during validation
- **Iterative Process**: Keep running each step and fixing errors until it passes
- **No User Interaction**: Do NOT ask the user for input or show what's being done
- **Silent Operation**: Work autonomously and only report completion when all steps are green
- **Test Performance**: All tests must be mocked and complete in reasonable time (no real network calls, all dependencies mocked)
- **Final Verification**: Format and lint must be run again after tests pass, and if changes are made, tests must be re-run
- **Complete Success**: The command is only complete when ALL steps pass AND final verification shows no changes:
  - ✅ Format passes (initial)
  - ✅ Lint passes (initial)
  - ✅ Type-check passes (initial, optional)
  - ✅ Tests pass (initial, all mocked, reasonable execution time)
  - ✅ Format passes (final, no changes)
  - ✅ Lint passes (final, no changes)
  - ✅ Tests pass (final, if format/lint made changes)

**Work is only done when all validation checks are green and working, final verification shows no changes, and all tests pass with proper mocking.**

## Python-Specific Notes

### Formatting Tools
- **black**: Code formatter (line length 100, Python 3.8+)
- **isort**: Import sorter (profile: black, line length 100)
- Both tools should be run together: `black miso_client/ tests/ && isort miso_client/ tests/`

### Linting Tool
- **ruff**: Fast Python linter (replaces flake8, pylint, etc.)
- Configuration in `pyproject.toml` under `[tool.ruff]`
- Should check both `miso_client/` and `tests/` directories

### Type Checking
- **mypy**: Static type checker
- Configuration in `pyproject.toml` under `[tool.mypy]`
- Use `--ignore-missing-imports` for third-party libraries
- Should check `miso_client/` directory (not tests, as they may have intentional type flexibility)

### Testing
- **pytest**: Test framework with pytest-asyncio for async tests
- Configuration in `pytest.ini` and `pyproject.toml`
- Tests should be in `tests/unit/` directory
- All tests must use proper mocking:
  - `pytest-mock` for mocking (mocker fixture)
  - `AsyncMock` for async method mocks
  - Mock HttpClient, RedisService, httpx.AsyncClient, redis, PyJWT
  - No real network calls or database connections

### Common Fixes

**Formatting Issues**:
- Run `black` to fix code formatting
- Run `isort` to fix import ordering
- Ensure line length is 100 characters

**Linting Issues**:
- Fix unused imports
- Fix undefined names
- Fix code style violations
- Fix complexity issues

**Type Checking Issues**:
- Add type hints where missing
- Fix type mismatches
- Use `Optional[T]` for nullable types
- Use proper type annotations for async functions

**Test Failures**:
- Ensure all external dependencies are mocked
- Use `@pytest.mark.asyncio` for async tests
- Use `mocker.patch()` for patching dependencies
- Use `AsyncMock` for async method mocks
- Ensure test fixtures are properly configured in `conftest.py`
