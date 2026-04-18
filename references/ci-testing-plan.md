# CI/Testing Implementation Plan

**Goal:** Catch bugs before they burn tokens. Zero AI calls in CI.

**Architecture Decision (2026-04-17):**
- Primary: GitHub Actions (cloud CI, zero local resource cost)
- Local: `act` for workflow testing before push
- Fallback: Drone CI (if GitHub Actions limits exceeded)
- Rationale: Old laptop hardware constraints; OpenClaw community standard pattern

---

## CI Workflow Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI PIPELINE                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Local Development          Cloud CI              Fallback       │
│  ───────────────         ──────────             ──────────        │
│                                                                 │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐      │
│  │ ruff --fix│         │ ruff lint │         │ ruff lint │      │
│  └────┬─────┘         └────┬─────┘         └────┬─────┘      │
│       │                    │                    │            │
│       ▼                    ▼                    ▼            │
│  ┌──────────┐         ┌──────────┐         ┌──────────┐      │
│  │ pytest   │ ──────▶ │ pytest   │ ◀────── │ pytest   │      │
│  └──────────┘   act   └──────────┘  drone  └──────────┘      │
│                    └────┬─────┘         └────┬─────┘      │
│                         ▼                    ▼            │
│                    ┌──────────┐         ┌──────────┐      │
│                    │ coverage │         │ coverage│      │
│                    └─────────┘         └─────────┘      │
│                                                                 │
│  GitHub Actions ───▶ repo.ci ---> PR/merge              │
│  Drone CI    <--- (fallback)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. GitHub Actions (Primary CI)

### Configuration
- **File:** `.github/workflows/ci.yml`
- **Triggers:** push to main, pull_request to main
- **Runs on:** GitHub hosted runners (ubuntu-latest)

### Jobs

#### lint
```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5 (python 3.14)
- run: pip install ruff
- run: ruff check src/ tests/
- run: ruff format --check src/ tests/
```

#### test
```yaml
needs: lint
- uses: actions/checkout@v4
- uses: actions/setup-python@v5 (python 3.14)
- run: pip install pytest pytest-cov pyyaml
- run: pytest tests/ -v --tb=short --cov=src
- uses: actions/upload-artifact@v4 (coverage.xml)
```

### Monitoring & Execution

**View runs:**
- Web: https://github.com/<user>/auto_memex/actions
- CLI: `gh run list`
- CLI: `gh run view <run-id>`

**Re-run failed jobs:**
- Web: Click "Re-run all jobs" on failed run
- CLI: `gh run rerun <run-id>`

---

## 2. Local Testing with act

`act` simulates GitHub Actions locally using Docker.

### Installation
```bash
# macOS
brew install act

# Linux
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sh
```

### Configuration
- **File:** `~/.actrc`
- **Example:**
  ```
  -P ubuntu-latest=catthehacker/ubuntu:act-latest
  ```

### Execution

**List workflows:**
```bash
act --dryrun --list
```

**Run specific job:**
```bash
act --job lint
act --job test
```

**Run entire pipeline:**
```bash
act
```

**Run for pull_request event:**
```bash
act -PullRequest
```

**Verbose output:**
```bash
act -v
```

---

## 3. Drone CI (Fallback)

Drone CI is self-hosted, runs when GitHub Actions limits are exceeded.

### Configuration
- **File:** `.drone.yml`
- **Kind:** pipeline
- **Type:** docker

### Jobs

#### lint
```yaml
- name: lint
  image: ruff/ruff
  commands:
    - ruff check src/ tests/
    - ruff format --check src/ tests/
```

#### test
```yaml
needs: lint
- name: test
  image: python:3.14-slim
  commands:
    - pip install pytest pytest-cov pyyaml
    - pytest tests/ -v --tb=short --cov=src
```

### Execution

**CLI installation:**
```bash
curl -L https://tools.drone.io/cli | sh
```

**Run locally (if Drone server running):**
```bash
drone exec
```

**Trigger manually:**
```bash
drone build start --branch main
drone build info <build-number>
drone build logs <build-number>
```

---

## 4. Decision Tree: Which CI to Use

```
START
  │
  ▼
┌────────────────────┐
│ Developing locally │
└────────┬──────────┘
         │
         ▼
    ┌────────────┐
    │ Run act   │─────── Yes ────> Uses Docker, saves GitHub minutes
    │ locally │
    └────┬────┘
         │
         │ No issues
         ▼
┌───────────────────┐
│ Push to branch   │
└────────┬─────────┘
         │
         ▼
    ┌────────────┐
    │ GitHub      │─────── Yes ────> Primary CI, free tier
    │ Actions OK │
    └────┬───────┘
         │
         │ No (limits exceeded)
         ▼
┌──────────────────┐
│ Drone CI         │─────── Fallback, self-hosted
│ (if configured)  │
└──────────────────┘
```

---

## 5. Token-Efficient Testing Patterns

1. **No live LLM calls** - Mock responses or use cached fixtures
2. **Deterministic tests** - Same input = same output, always
3. **Fast feedback** - Lint first, then unit tests, skip slow e2e in CI
4. **Test the wrapper, not the AI** - Test prompt construction, not model response

---

## 6. Accessing CI Results

| CI System | URL/Command |
|----------|-------------|
| GitHub Actions | https://github.com/<org>/auto_memex/actions |
| GitHub CLI | `gh run list`, `gh run view <id>` |
| act (local) | `act` or `act --job <job>` |
| Drone | drone server URL (self-hosted) |
| Drone CLI | `drone build list`, `drone build info <id>` |