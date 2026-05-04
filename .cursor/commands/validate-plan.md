# validate-plan

Validate a plan file before execution by identifying its purpose, reading relevant rules, validating rule scope, updating the plan with rule references, and ensuring Definition of Done (DoD) requirements are documented.

## Purpose

This command ensures that:

1. Plans are validated against relevant rules before execution
2. Plan authors understand which rules apply to their plan
3. Plans include proper DoD requirements (format → lint → type-check → test)
4. Plans reference relevant rule files for guidance
5. Plans are production-ready before implementation begins
6. Documentation is updated as needed during the validation process
7. Validation guidance prefers quiet execution with full diagnostics captured in `.temp/validation/`
8. Plan task checkboxes and frontmatter `todos` remain synchronized after updates
9. Validation report metadata (especially date) is generated dynamically each run

## Usage

```bash
/validate-plan [plan-file-path]
```

**Parameters**:

- `plan-file-path` (optional): Path to the plan file to validate. If not specified:
  - First checks if there's a current chat plan (from `mcp_create_plan` tool or recent conversation)
  - If no current plan, lists recent plans from `.cursor/plans/` and asks user to select
  - If still unclear, prompts user for clarification

**Examples**:

- `/validate-plan` - Validates current chat plan or prompts for plan selection
- `/validate-plan .cursor/plans/8-language-specific-env-variables.plan.md` - Validates a specific plan

## Silent Command Preference

When this command updates plan DoD/validation command blocks, use silent Make targets first:

- Primary wrapper: `make validate-silent`
- Step-level: `make format-silent`, `make lint-silent`, `make type-check-silent`, `make test-silent`
- Logs: `.temp/validation/` (primary diagnostics source)
- Fallback only if needed: `make validate`, `make format`, `make lint`, `make type-check`, `make test`

### Output Noise Control (MANDATORY)

To keep validation token-efficient while preserving quality gates:

- Prefer `*-silent` commands in plan DoD and validation sections.
- Keep detailed diagnostics in `.temp/validation/` logs.
- In generated report text, provide concise summaries by default.
- Include detailed command output only for failing steps.

## Execution Steps

### Step 1: Plan File Resolution

**Logic**:

1. If `plan-file-path` provided: Use that file directly
2. If empty: Check for current chat plan context
   - Look for plan file references in recent conversation messages
   - Check if `mcp_create_plan` was recently called (check conversation history)
   - If found, use that plan file path
3. If still empty: List recent plans from `.cursor/plans/` directory
   - Sort by modification time (most recent first)
   - Show last 5-10 plans with their titles
   - Ask user to select one or provide a path
4. If unclear: Ask user to specify the plan file path explicitly

**Implementation**:

- Read plan file from resolved path
- Validate file exists and is readable
- Parse markdown structure
- If file doesn't exist, report error and ask for correct path

### Step 2: Identify Plan Purpose

**Analysis**:

1. Read plan file content completely
2. Extract from plan:
   - **Title**: Main title from `# Title` (first H1)
   - **Overview**: Content from `## Overview` section
   - **Scope**: What areas are affected (services, models, utils, HTTP client, Redis, authentication, authorization, logging, encryption, etc.)
   - **Key Components**: Files, modules, services, models mentioned in plan
   - **Type**: Classify as one of:
     - Architecture (structure, design, patterns)
     - Development (services, features, modules)
     - Service Layer (authentication, authorization, logging, encryption)
     - HTTP Client (request handling, interceptors, error handling)
     - Models (Pydantic models, data validation)
     - Refactoring (code improvements, restructuring)
     - Testing (test additions, test improvements)
     - Documentation (docs, guides)
     - Security (ISO 27001 compliance, secret management, data masking)

**Keywords to Detect**:

- **Services**: "service", "services/", "auth", "authorization", "logging", "encryption"
- **HTTP Client**: "http_client", "httpx", "request", "authenticated_request", "interceptor"
- **Models**: "model", "models/", "Pydantic", "validation", "schema"
- **Redis**: "redis", "cache", "caching", "RedisService"
- **Security**: "ISO 27001", "secret", "security", "compliance", "data masking", "audit"
- **Architecture**: "architecture", "structure", "design", "pattern"
- **Testing**: "pytest", "test", "coverage", "mock"

**Output**:

- Plan purpose summary (1-2 sentences)
- Affected areas list (services, models, HTTP client, Redis, authentication, etc.)
- Plan type classification
- Key components mentioned

### Step 3: Read Rules and Identify Scope

**Rule File** (from `.cursor/rules/`):

- **`project-rules.mdc`** - Single comprehensive rule file containing:
  - Project Overview - Technologies and architecture
  - Architecture Patterns - Service layer, HTTP client, token management, Redis caching, API endpoints
  - Code Style - Python conventions, naming, type hints, error handling
  - Testing Conventions - pytest patterns, test structure, coverage, mocking
  - File Organization - Source structure, import order, export strategy
  - Configuration - Config types, environment variables
  - Common Patterns - Service method patterns, logger chain, HTTP client patterns
  - Security Guidelines - ISO 27001 compliance, data masking, secret management
  - Performance Guidelines - Redis caching, async/await patterns
  - Code Size Guidelines - File size limits, method size limits
  - Documentation - Google-style docstrings, type hints
  - Dependencies - Required packages and versions
  - When Adding New Features - Development workflow
  - Common Pitfalls and Best Practices - Token handling, Redis caching, error handling
  - Critical Rules - Must do and must not do items

**Rule Mapping Logic**:

- **Service changes** → Architecture Patterns, Code Style, Testing Conventions, Common Patterns
- **HTTP Client changes** → Architecture Patterns, Common Patterns, Security Guidelines
- **Model changes** → File Organization, Code Style, Configuration
- **Redis/Caching changes** → Architecture Patterns, Performance Guidelines, Common Patterns
- **Security changes** → Security Guidelines, Architecture Patterns, Common Patterns
- **Testing changes** → Testing Conventions, Code Style
- **All plans** → Code Size Guidelines (MANDATORY), Security Guidelines (MANDATORY), Testing Conventions (MANDATORY)

**Implementation**:

1. Read the rule file `.cursor/rules/project-rules.mdc` completely
2. Based on plan scope, identify relevant sections:
   - Keywords matching (e.g., plan mentions "service" → Architecture Patterns section)
   - Component matching (e.g., plan mentions "HTTP client" → Architecture Patterns, Common Patterns sections)
   - Type matching (e.g., plan type is "Service Layer" → Architecture Patterns, Common Patterns sections)
   - Always include Code Size Guidelines, Security Guidelines, and Testing Conventions (mandatory)
3. For each applicable section, extract:
   - Section name
   - Why it applies (brief reason based on plan content)
   - Key requirements from section (read section and extract main points)

**Key Requirements Extraction**:

- Read each applicable section from the rule file
- Extract main requirements, checklists, critical policies
- Summarize in 2-3 bullet points per section
- Focus on actionable requirements

### Step 4: Validate Rule Compliance

**Validation Checks**:

1. **DoD Requirements** (from Code Size Guidelines and Testing Conventions sections):
   - ✅ Format step documented (`make format-silent`; backup: `make format`)
   - ✅ Lint step documented (`make lint-silent`; backup: `make lint`)
   - ✅ Type-check step documented (`make type-check-silent`; backup: `make type-check`)
   - ✅ Test step documented (`make test-silent`; backup: `make test`, all tests must pass, ≥80% coverage for new code)
   - ✅ Validation order specified (FORMAT → LINT → TYPE CHECK → TEST)
   - ✅ Zero warnings/errors requirement mentioned
   - ✅ Mandatory sequence documented (never skip steps)
   - ✅ Test coverage ≥80% requirement mentioned (for new code)
   - ✅ File size limits mentioned (files ≤500 lines, methods ≤20-30 lines)
   - ✅ Type hints requirement mentioned (all functions must have type hints)
   - ✅ Docstrings requirement mentioned (Google-style docstrings for public methods)

2. **Plan-Specific Rules**:
   - Check if plan addresses key requirements from applicable rule sections
   - Identify missing rule references in plan
   - Identify potential violations based on rule requirements
   - Check if plan mentions rule-specific patterns (e.g., Google-style docstrings, type hints, async/await, try-except)

**Output**:

- List of applicable rule sections with compliance status
- Missing requirements checklist
- Recommendations for plan improvement

### Step 4.5: Synchronize Task States (MANDATORY)

When plan sections are added or updated, keep task state representations consistent:

1. Markdown checkboxes (`- [ ]` / `- [x]`)
   - Do not mark task completion unless supported by plan content.
2. Frontmatter `todos`
   - Normalize status values to `pending|in_progress|completed|cancelled`.
   - Align statuses with markdown task states and current validation outcome.
3. Conflict resolution
   - Resolve contradictions immediately; do not leave stale `in_progress` items.

### Step 5: Update Plan with Rule References

**Plan Updates**:

1. **Add or update `## Rules and Standards` section**:
   - Reference the main rule file: `.cursor/rules/project-rules.mdc`
   - List all applicable sections with brief descriptions
   - Format: `- **[Section Name](.cursor/rules/project-rules.mdc#section-name)** - [Brief description]`
   - Explain why each section applies (1 sentence)
   - Add "Key Requirements" subsection with bullet points from each section

2. **Add or update `## Definition of Done` section**:
   - Format requirement: `make format-silent` (must run first; backup: `make format`)
   - Lint requirement: `make lint-silent` (must run after format; backup: `make lint`)
   - Type-check requirement: `make type-check-silent` (must run after lint; backup: `make type-check`)
   - Test requirement: `make test-silent` (must run after type-check; backup: `make test`, all tests must pass, ≥80% coverage for new code)
   - Validation order: FORMAT → LINT → TYPE CHECK → TEST (mandatory sequence, never skip steps)
   - File size limits: Files ≤500 lines, methods ≤20-30 lines
   - Type hints: All functions must have type hints
   - Docstrings: All public methods must have Google-style docstrings
   - Code quality: All rule requirements met
   - Security: No hardcoded secrets, ISO 27001 compliance, data masking
   - Documentation: Update documentation as needed (README, API docs, guides, usage examples)
   - All tasks completed

3. **Add or update `## Before Development` section**:
   - Checklist of rule compliance items
   - Prerequisites from rules (e.g., "Read project-rules.mdc")
   - Validation requirements
   - Rule-specific preparation steps
   - Review existing similar implementations for patterns
   - Update documentation as needed (README, API docs, guides)

4. **Update documentation as needed**:
   - Review plan scope to identify documentation that may need updates
   - Check if plan affects public APIs, configuration, or usage patterns
   - Update relevant documentation files (README.md, docs/, API documentation)
   - Ensure documentation reflects any new features, changes, or patterns introduced by the plan

**Update Strategy**:

- If section exists: Update/merge with new information (preserve existing content, add missing items)
- If section missing: Add new section at appropriate location (after Overview, before Tasks)
- Preserve existing content where possible
- Use consistent markdown formatting
- Add rule links using anchor links: `.cursor/rules/project-rules.mdc#section-name`

**Section Order** (if creating new sections):

1. Overview
2. Rules and Standards (add here)
3. Before Development (add here)
4. Definition of Done (add here)
5. Tasks/Implementation (existing)

### Step 6: Generate and Attach Validation Report

**Report Attachment**:

- Append the validation report directly to the plan file at the end
- Do not create separate validation documents
- Place the report after all existing plan content
- If `## Plan Validation Report` already exists, replace it instead of appending a duplicate

**Date Generation Instructions**:

- Generate date dynamically on each run (never hardcode).
- Date format: `YYYY-MM-DD (today is YYYY-MM-DD)`.

**Report Structure**:

```markdown
## Plan Validation Report

**Date**: [Generated dynamically: YYYY-MM-DD (today is YYYY-MM-DD)]
**Plan**: [plan-file-path]
**Status**: ✅ VALIDATED / ⚠️ NEEDS UPDATES / ❌ INCOMPLETE

### Plan Purpose

[Summary of plan purpose, scope, and type]

### Applicable Rules

- ✅ [Section Name](.cursor/rules/project-rules.mdc#section-name) - [Why it applies]
- ✅ [Section Name](.cursor/rules/project-rules.mdc#section-name) - [Why it applies]
- ⚠️ [Section Name](.cursor/rules/project-rules.mdc#section-name) - [Why it applies] (missing from plan)

### Rule Compliance

- ✅ DoD Requirements: Documented
- ✅ [Section Name]: Compliant
- ⚠️ [Section Name]: Missing [requirement]

### Plan Updates Made

- ✅ Added Rules and Standards section
- ✅ Updated Definition of Done section
- ✅ Added Before Development checklist
- ✅ Added rule references: [list of sections added]
- ✅ Updated documentation as needed: [list of documentation files updated]

### Recommendations

- [List of recommendations for plan improvement]
- [Any missing requirements]
- [Any potential issues]
```

**Status Determination**:

- ✅ **VALIDATED**: All DoD requirements present, all applicable rules referenced, plan is production-ready
- ⚠️ **NEEDS UPDATES**: DoD requirements present but some rules missing or incomplete
- ❌ **INCOMPLETE**: Missing critical DoD requirements or major rule violations

**Report Attachment**:

- **Always append validation report to plan file**: The validation report is appended directly to the plan file at the end, after all existing content
- **No separate documents**: Validation reports are never created as separate files - they are always integrated into the plan file itself
- **Report placement**: Add the validation report section at the very end of the plan file, after all tasks and other sections

## Integration with Existing Commands

**Relationship to Other Commands**:

- **`/validate-code`**: Validates code after implementation (code quality, rule compliance)
- **`/validate-implementation`**: Validates plan execution (tasks completed, files exist, tests pass)
- **`/validate-plan`**: Validates plan before execution (rule compliance, DoD requirements) - **NEW**

**Workflow**:

1. Create plan → `/validate-plan` (validate plan structure and rule compliance)
2. Implement plan → Code changes
3. `/validate-code` (validate code quality and rule compliance)
4. `/validate-implementation` (validate plan completion and test coverage)

## DoD Requirements (Mandatory)

Every plan must include these requirements in the Definition of Done section:

1. **Format Step**: `make format-silent` (must run first; backup: `make format`)
2. **Lint Step**: `make lint-silent` (must run after format with zero errors/warnings; backup: `make lint`)
3. **Type-check Step**: `make type-check-silent` (must run after lint; backup: `make type-check`)
4. **Test Step**: `make test-silent` (must run after type-check, all tests must pass, ≥80% coverage for new code; backup: `make test`)
5. **Validation Order**: FORMAT → LINT → TYPE CHECK → TEST (mandatory sequence, never skip steps)
6. **File Size Limits**: Files ≤500 lines, methods ≤20-30 lines
7. **Type Hints**: All functions must have type hints
8. **Docstrings**: All public methods must have Google-style docstrings
9. **Code Quality**: Code quality validation passes
10. **Security**: No hardcoded secrets, ISO 27001 compliance, data masking
11. **Rule References**: Links to applicable sections from `.cursor/rules/project-rules.mdc`
12. **Documentation**: Update documentation as needed (README, API docs, guides, usage examples)
13. **All Tasks Completed**: All plan tasks marked as complete
14. **Task State Sync**: Markdown checkboxes and frontmatter `todos` are consistent

## Example Plan Updates

### Before Validation

```markdown
# Example Plan

## Overview

Create a new authentication service method for user login.

## Tasks

- [ ] Create login method
- [ ] Add tests
```

### After Validation

```markdown
# Example Plan

## Overview

Create a new authentication service method for user login.

## Rules and Standards

This plan must comply with the following rules from [Project Rules](.cursor/rules/project-rules.mdc):

- **[Architecture Patterns](.cursor/rules/project-rules.mdc#architecture-patterns)** - Service layer patterns, HTTP client patterns, token management
- **[Code Style](.cursor/rules/project-rules.mdc#code-style)** - Python conventions, type hints, error handling
- **[Code Size Guidelines](.cursor/rules/project-rules.mdc#code-size-guidelines)** - File size limits, method size limits
- **[Testing Conventions](.cursor/rules/project-rules.mdc#testing-conventions)** - pytest patterns, test structure, coverage requirements
- **[Security Guidelines](.cursor/rules/project-rules.mdc#security-guidelines)** - ISO 27001 compliance, data masking, secret management
- **[Common Patterns](.cursor/rules/project-rules.mdc#common-patterns)** - Service method patterns, error handling patterns

**Key Requirements**:

- Use service layer pattern with HttpClient and RedisService dependencies
- Use async/await for all I/O operations
- Use try-except for all async operations, return empty list `[]` or `None` on errors
- Write tests with pytest and pytest-asyncio
- Add Google-style docstrings for all public methods
- Add type hints for all function parameters and return types
- Keep files ≤500 lines and methods ≤20-30 lines
- Never log secrets or sensitive data (use DataMasker)
- Always check `redis.is_connected()` before Redis operations
- Extract userId from JWT before calling validate when possible

## Before Development

- [ ] Read Architecture Patterns section from project-rules.mdc
- [ ] Review existing service methods for patterns
- [ ] Review error handling patterns (try-except, return defaults)
- [ ] Understand testing requirements (pytest, pytest-asyncio, mocking)
- [ ] Review Google-style docstring patterns
- [ ] Review type hint patterns

## Definition of Done

Before marking this plan as complete, ensure:

1. **Format**: Run `make format-silent` FIRST (must pass; backup: `make format`)
2. **Lint**: Run `make lint-silent` AFTER format (must pass with zero errors/warnings; backup: `make lint`)
3. **Type-check**: Run `make type-check-silent` AFTER lint (must pass; backup: `make type-check`)
4. **Test**: Run `make test-silent` AFTER type-check (all tests must pass, ≥80% coverage for new code; backup: `make test`)
5. **Validation Order**: FORMAT → LINT → TYPE CHECK → TEST (mandatory sequence, never skip steps)
6. **File Size Limits**: Files ≤500 lines, methods ≤20-30 lines
7. **Type Hints**: All functions have type hints
8. **Docstrings**: All public methods have Google-style docstrings
9. **Code Quality**: All rule requirements met
10. **Security**: No hardcoded secrets, ISO 27001 compliance, data masking
11. **Documentation**: Update documentation as needed (README, API docs, guides, usage examples)
12. All tasks completed
13. Service method follows all standards from Architecture Patterns section
14. Tests have proper coverage (≥80%) and use pytest-asyncio for async tests

## Tasks

- [ ] Create login method
- [ ] Add tests
- [ ] Run format → lint → type-check → test validation
```

## Success Criteria

- ✅ Plan purpose identified correctly
- ✅ Applicable rule sections identified and referenced
- ✅ DoD requirements documented
- ✅ Plan updated with rule references
- ✅ Validation report generated
- ✅ Plan ready for production implementation

## Notes

- **Rule Reading**: Always read the rule file completely to extract accurate requirements
- **Plan Preservation**: Preserve existing plan content when updating sections
- **Mandatory Sections**: Code Size Guidelines, Security Guidelines, and Testing Conventions are mandatory for ALL plans
- **Rule Links**: Use anchor links for rule file sections (`.cursor/rules/project-rules.mdc#section-name`)
- **DoD Order**: Always document validation order as FORMAT → LINT → TYPE CHECK → TEST
- **Status**: Report status accurately based on compliance level
- **Documentation Updates**: Review plan scope and update relevant documentation files (README.md, docs/, API documentation) as needed during validation
- **Project-Specific**: This is a Python SDK project (library), adapt scope detection accordingly (services, models, HTTP client, Redis, etc.)
- **Report Attachment**: Validation reports are always appended to the plan file itself - never create separate validation documents
- **Task State Consistency**: Keep markdown checkboxes and frontmatter `todos` synchronized after updates
