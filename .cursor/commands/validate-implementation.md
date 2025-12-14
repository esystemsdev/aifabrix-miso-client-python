# validate-implementation

This command validates that a plan has been implemented correctly according to its requirements, verifies tests exist, and ensures no code violations of cursor rules.

## Purpose

The command:

1. Analyzes a plan file (from `.cursor/plans/`) to extract implementation requirements
2. Validates that all tasks are completed
3. Verifies that all mentioned files exist and are implemented
4. Checks that tests exist for new/modified code
5. Runs code quality validation (format → lint → test)
6. Validates against cursor rules
7. Attaches validation results to the plan file itself (adds/updates `## Validation` section)

## Usage

Run this command in chat with `/validate-implementation [plan-file-path]`

**Examples**:

- `/validate-implementation` - Validates the most recently modified plan file
- `/validate-implementation .cursor/plans/68-data-client-browser-wrapper.plan.md` - Validates a specific plan

## What It Does

### 1. Plan Analysis

**Extracts from Plan File**:

- All tasks with checkboxes (`- [ ]` or `- [x]`)
- All files mentioned (paths, new files, modified files)
- All services, types, utilities mentioned
- Test requirements (unit tests, integration tests)
- Documentation requirements
- **Existing validation section** (if present) - Will be replaced with new validation results

**Validates Task Completion**:

- Checks if all tasks are marked as complete (`- [x]`)
- Identifies incomplete tasks (`- [ ]`)
- Reports completion percentage

### 2. File Existence Validation

**Checks for**:

- All mentioned files exist at specified paths
- New files are created (if marked as "New" in plan)
- Modified files exist and contain expected changes
- Type definition files exist (if mentioned)
- Test files exist for new/modified code

**Validates File Content**:

- Checks if mentioned classes/functions exist in files
- Verifies expected imports are present
- Validates that key changes are implemented
- Checks Python type hints and Pydantic models

### 3. Test Coverage Validation

**Checks for**:

- Unit test files exist for new services/modules
- Integration test files exist (if required by plan)
- Test structure mirrors code structure
- Test files are in correct locations (`tests/unit/` mirrors `miso_client/`)

**Validates Test Quality**:

- Tests use proper fixtures and mocks (pytest fixtures, pytest-mock)
- Tests cover error cases
- Tests use async patterns where needed (`@pytest.mark.asyncio`)
- Tests follow cursor rules for testing
- Tests properly mock HttpClient, RedisService, httpx, redis, PyJWT
- Tests complete in reasonable time (all mocked, no real network calls)

### 4. Code Quality Validation

**Runs Validation Steps (MANDATORY ORDER)**:

1. **STEP 1 - FORMAT**:
   - Run `make format` or `black miso_client/ tests/` and `isort miso_client/ tests/` FIRST
   - Verify exit code 0
   - Report any formatting issues

2. **STEP 2 - LINT**:
   - Run `make lint` or `ruff check miso_client/ tests/` AFTER format
   - Verify exit code 0
   - Report all linting errors/warnings
   - **CRITICAL**: Zero warnings/errors required

3. **STEP 3 - TYPE CHECK**:
   - Run `make type-check` or `mypy miso_client/ --ignore-missing-imports` AFTER lint
   - Verify exit code 0 or acceptable warnings
   - Report type checking issues

4. **STEP 4 - TEST**:
   - Run `make test` or `pytest tests/ -v` AFTER type-check
   - Verify all tests pass
   - Report test failures
   - Check test execution time (should be fast with proper mocking)

**Validates Code Against Cursor Rules**:

- Reads relevant rules from repository-specific cursor rules (`.cursorrules`)
- Checks for violations in:
  - Code reuse (no duplication, use utilities)
  - Error handling (proper exception usage, try-except, return empty arrays/None on error)
  - Logging (proper logging, no secrets logged, use DataMasker)
  - Type safety (Python type hints, Pydantic models for public APIs)
  - Async patterns (async/await, no raw coroutines)
  - HTTP client patterns (use HttpClient, authenticated_request, proper headers)
  - Token management (JWT decode, proper header usage, x-client-token lowercase)
  - Redis caching (check is_connected, proper fallback)
  - Service layer patterns (proper dependency injection, config access via public property)
  - Security (no hardcoded secrets, proper secret management, ISO 27001 compliance)
  - API data conventions (camelCase for all outgoing data, snake_case for Python code)
  - File size guidelines (files < 500 lines, methods < 20-30 lines)

### 5. Implementation Completeness Check

**Validates**:

- All service methods are implemented
- All Pydantic models are updated
- All utilities are implemented
- All documentation is updated
- All exports are properly configured in `miso_client/__init__.py`

### 6. Report Generation

**Attaches Validation Section to Plan File**:

- Updates the plan file itself by adding/updating a `## Validation` section
- Location: Same plan file (`.cursor/plans/<plan-name>.plan.md`)
- Contains:
  - Executive summary (overall status)
- **Note**: If a validation section already exists, it will be replaced with the new validation results
  - File existence validation results
  - Test coverage analysis
  - Code quality validation results
  - Cursor rules compliance check
  - Implementation completeness assessment
  - Issues and recommendations
  - Final validation checklist

## Output

### Validation Section Structure

```markdown
## Validation

**Date**: [Generated date]
**Status**: ✅ COMPLETE / ⚠️ INCOMPLETE / ❌ FAILED

### Executive Summary

[Overall status and completion percentage]

### File Existence Validation

- ✅/❌ [File path] - [Status]
- ✅/❌ [File path] - [Status]

### Test Coverage

- ✅/❌ Unit tests exist
- ✅/❌ Integration tests exist
- Test coverage: [percentage]%

### Code Quality Validation

**STEP 1 - FORMAT**: ✅/❌ PASSED
**STEP 2 - LINT**: ✅/❌ PASSED (0 errors, 0 warnings)
**STEP 3 - TYPE CHECK**: ✅/❌ PASSED
**STEP 4 - TEST**: ✅/❌ PASSED (all tests pass)

### Cursor Rules Compliance

- ✅/❌ Code reuse: PASSED
- ✅/❌ Error handling: PASSED
- ✅/❌ Logging: PASSED
- ✅/❌ Type safety: PASSED
- ✅/❌ Async patterns: PASSED
- ✅/❌ HTTP client patterns: PASSED
- ✅/❌ Token management: PASSED
- ✅/❌ Redis caching: PASSED
- ✅/❌ Service layer patterns: PASSED
- ✅/❌ Security: PASSED
- ✅/❌ API data conventions: PASSED
- ✅/❌ File size guidelines: PASSED

### Implementation Completeness

- ✅/❌ Services: COMPLETE
- ✅/❌ Models: COMPLETE
- ✅/❌ Utilities: COMPLETE
- ✅/❌ Documentation: COMPLETE
- ✅/❌ Exports: COMPLETE

### Issues and Recommendations

[List of issues found and recommendations]

### Final Validation Checklist

- [x] All tasks completed
- [x] All files exist
- [x] Tests exist and pass
- [x] Code quality validation passes
- [x] Cursor rules compliance verified
- [x] Implementation complete

**Result**: ✅/❌ **VALIDATION PASSED/FAILED** - [Summary message]
```

## Execution Behavior

**Automatic Execution**:
- The command executes automatically without asking for user input
- Shows progress during validation
- Attaches validation results to the plan file itself (adds/updates `## Validation` section)
- Only asks for user input if critical issues require confirmation

**Error Handling**:
- If format fails: Reports error, does not proceed to lint
- If lint fails: Reports all errors, does not proceed to type-check
- If type-check fails: Reports all errors, does not proceed to tests
- If tests fail: Reports all failures
- If files are missing: Reports missing files
- If tasks are incomplete: Reports incomplete tasks

**Critical Requirements**:
- **Format must pass** before linting
- **Lint must pass** (zero errors/warnings) before type-checking
- **Type-check should pass** (or have acceptable warnings) before testing
- **Tests must pass** before marking as complete
- **All tasks must be completed** for full validation
- **All files must exist** for full validation
- **Tests must exist** for new/modified code
- **Tests must use proper mocking** (no real network calls, all dependencies mocked)

## Notes

- **Plan File Detection**: If no plan file is specified, the command finds the most recently modified plan file in `.cursor/plans/`
- **Task Parsing**: Extracts tasks from markdown checkboxes (`- [ ]` or `- [x]`)
- **File Detection**: Identifies file paths mentioned in plan (code blocks, file references, paths in text)
- **Validation Section Update**: Adds or updates the `## Validation` section in the plan file itself with validation results
- **Report Location**: Validation results are attached directly to the plan file (no separate report file created)
- **Python-Specific**: Adapted for Python project structure (`miso_client/` instead of `src/`, pytest instead of jest, etc.)

## Integration with Plans

This command is designed to be added to every code plan as a final validation step:

```markdown
## Validation

After implementation, run:
/validate-implementation .cursor/plans/<plan-name>.plan.md

This will validate:
- All tasks are completed
- All files exist and are implemented
- Tests exist and pass
- Code quality validation passes
- Cursor rules compliance verified
```

## Example Usage in Plan

```markdown
# Example Plan

## Tasks
- [ ] Task 1: Create service
- [ ] Task 2: Add tests
- [ ] Task 3: Update documentation

## Validation
After completing all tasks, run:
/validate-implementation .cursor/plans/example-plan.plan.md

The validation results will be added to this plan file as a `## Validation` section below.
```

## Python-Specific Adaptations

### File Structure
- Source code: `miso_client/` (instead of `src/`)
- Tests: `tests/unit/` (mirrors `miso_client/`)
- Main exports: `miso_client/__init__.py` (instead of `src/index.ts`)

### Testing
- Framework: `pytest` (instead of jest)
- Async tests: `@pytest.mark.asyncio` decorator
- Mocking: `pytest-mock` (mocker fixture)
- Fixtures: `conftest.py` for shared fixtures
- Test files: `test_*.py` pattern

### Code Quality Tools
- Formatting: `black` and `isort`
- Linting: `ruff`
- Type checking: `mypy`
- Testing: `pytest`

### Mocking Patterns
- HttpClient: `mocker.Mock(spec=HttpClient)`
- Redis: `mocker.Mock(spec=RedisService)`
- httpx: `mocker.patch('httpx.AsyncClient')`
- JWT: `mocker.patch('miso_client.utils.jwt_tools.decode_token')`
- Async methods: `AsyncMock` from `unittest.mock`

### Type Safety
- Type hints: Python 3.8+ type hints throughout
- Models: Pydantic models for public APIs
- Type checking: mypy (with `--ignore-missing-imports` for third-party libs)
