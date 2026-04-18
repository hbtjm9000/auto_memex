# CI/Testing Implementation Plan

**Goal:** Catch bugs before they burn tokens. Zero AI calls in CI.

**Architecture Decision (2026-04-17):**
- Primary: GitHub Actions (cloud CI, zero local resource cost)
- Local: `act` for workflow testing before push
- Fallback: Drone CI self-hosted (if GitHub Actions limits exceeded)
- Rationale: Old laptop hardware constraints; OpenClaw community standard pattern

## Phase 1: GitHub Actions CI for auto_memex
- `.github/workflows/ci.yml` with:
  - `ruff` linting (fast, catches syntax/type errors)
  - `pytest` on every push/PR
  - Coverage report (track test quality)
- Runs on GitHub's free tier (2000 min/month)
- No AI tokens burned - pure unit tests

## Phase 1b: Local Workflow Testing with `act`
- Install `act` for local GitHub Actions simulation
- Test workflows before push (saves CI minutes)
- Uses Docker: micro image (200MB) for minimal resource usage

## Phase 2: Skill/Script Testing Framework
- Create `~/.hermes/skills/__tests__/` structure
- Add pytest fixtures for common patterns (file ops, API mocks)
- Each skill gets `test_<skill>.py` with:
  - Unit tests for pure functions
  - Mocked external dependencies (no real API calls)
- CI job runs all skill tests

## Phase 3: Pre-commit Hooks
- `pre-commit` config to run linting before commits
- Catches errors locally before pushing
- Saves CI minutes + token debugging time

## Phase 4: Git Remote + PR Workflow
- Configure GitHub remote for ~/lab
- Require CI pass before merge
- Enforces test coverage on new code

## Token-Efficient Testing Patterns
1. **No live LLM calls** - Mock responses or use cached fixtures
2. **Deterministic tests** - Same input = same output, always
3. **Fast feedback** - Lint first, then unit tests, skip slow e2e in CI
4. **Test the wrapper, not the AI** - Test prompt construction, not model response

## Steps
1. Check if GitHub CLI is available
2. Create GitHub repo (if needed)
3. Add `.github/workflows/ci.yml` to ~/lab
4. Add `pyproject.toml` with pytest/ruff config
5. Add `pre-commit` config
6. Configure Git remote
7. Create skill test template
8. Run initial CI to verify
