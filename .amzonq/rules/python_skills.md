# Amazon Q Developer — Python PR Review Rules

Use these rules as the standard for every Pull Request review in this repository.

---

## 1. Code Style & Formatting

- Follow **PEP 8** strictly: indentation, spacing, line length (max 120 chars), blank lines between functions/classes.
- Use **snake_case** for variables, functions and modules; **PascalCase** for classes; **UPPER_SNAKE_CASE** for constants.
- Prefer **f-strings** over `.format()` or `%` formatting.
- Remove trailing whitespace, unused imports and commented-out dead code.
- Each file must end with a single blank line.
- Imports must be grouped in order: stdlib → third-party → local, separated by blank lines.

---

## 2. Type Hints

- All public functions and methods **must** have type hints for parameters and return values.
- Use `Optional[X]` (or `X | None` in Python ≥ 3.10) instead of leaving parameters untyped.
- Complex types should use `TypedDict`, `dataclass` or Pydantic models — avoid raw `dict` with unclear structures.
- Flag any `Any` usage that is not explicitly justified by a comment.

```python
# ✅ Correct
def get_user(user_id: int) -> Optional[User]:
    ...

# ❌ Flag this
def get_user(user_id, data):
    ...
```

---

## 3. Error Handling

- Never use bare `except:` — always catch specific exceptions.
- Do not silence exceptions with `pass` unless justified by a comment.
- Use custom exception classes for domain errors instead of generic `Exception`.
- Avoid using exceptions for control flow in normal execution paths.
- Always log or re-raise exceptions — never swallow silently.

```python
# ✅ Correct
try:
    result = process(data)
except ValueError as e:
    logger.error("Invalid data: %s", e)
    raise

# ❌ Flag this
try:
    result = process(data)
except:
    pass
```

---

## 4. Security

- Flag any **hardcoded secrets**: passwords, tokens, API keys, connection strings.
- Credentials must come from environment variables or a secrets manager (e.g., AWS Secrets Manager, `.env` via `python-dotenv`).
- Validate and sanitize all external inputs (HTTP, CLI, file uploads) before use.
- Flag SQL queries built with string concatenation — require parameterized queries or ORM.
- Flag use of `eval()`, `exec()`, `pickle` with untrusted data, or `subprocess` with `shell=True`.
- Check for path traversal risks when building file paths from user input (`os.path.join` + validation).

---

## 5. Performance

- Flag obvious N+1 query patterns (queries inside loops hitting a database or external API).
- Flag loading entire large datasets into memory when generators or streaming would suffice.
- Flag repeated expensive operations inside loops that could be extracted or cached.
- Prefer list/dict/set comprehensions over equivalent `for` loops when readability is maintained.
- Flag missing indexes or lack of pagination in database queries that return unbounded results.

---

## 6. Testing

- Every new public function or method must have at least one corresponding unit test.
- Tests must cover: happy path, edge cases and expected error/exception cases.
- No hardcoded test data that leaks real credentials, PII or production URLs.
- Mocks and fixtures must be cleaned up — avoid test pollution between cases.
- Test function names must be descriptive: `test_<function>_<scenario>_<expected_result>`.

```python
# ✅ Correct
def test_get_user_with_invalid_id_raises_value_error():
    ...

# ❌ Flag this
def test_1():
    ...
```

---

## 7. Documentation

- All public functions, classes and modules must have docstrings (Google style preferred).
- Docstrings must describe: purpose, parameters (`Args:`), return value (`Returns:`) and exceptions (`Raises:`).
- Inline comments should explain *why*, not *what* — avoid restating the code.
- Flag TODOs and FIXMEs that have no associated issue/ticket reference.

```python
# ✅ Correct
def calculate_discount(price: float, rate: float) -> float:
    """Calculate the discounted price.

    Args:
        price: Original price in BRL.
        rate: Discount rate between 0 and 1.

    Returns:
        Final price after discount.

    Raises:
        ValueError: If rate is not between 0 and 1.
    """
```

---

## 8. Architecture & Design

- Functions must follow the **Single Responsibility Principle** — flag functions doing more than one thing.
- Flag functions longer than **50 lines** — suggest splitting.
- Flag classes with more than **10 public methods** — suggest decomposition.
- Avoid deep nesting (more than 3 levels) — suggest early returns or extraction.
- Flag global mutable state outside of configuration modules.
- Dependency injection is preferred over hardcoded instantiation inside functions.

---

## 9. Logging

- Use the `logging` module — never use `print()` in production code.
- Log levels must match severity: `DEBUG` for tracing, `INFO` for business events, `WARNING` for recoverable issues, `ERROR`/`CRITICAL` for failures.
- Never log sensitive data: passwords, tokens, full PII.
- Structured logging (JSON) is preferred for services that feed log aggregation tools.

---

## 10. Dependencies

- New dependencies added to `requirements.txt` or `pyproject.toml` must be pinned to a version range.
- Flag unpinned (`package` with no version) or overly broad (`package>=1.0`) dependencies in production code.
- Flag imports of packages not declared in the dependency file.
- Prefer standard library solutions over adding a new dependency for simple tasks.

---

## Review Severity Levels

Use these labels when reporting findings:

| Level | When to use |
|---|---|
| 🔴 **BLOCKER** | Security vulnerability, data loss risk, broken logic |
| 🟠 **MAJOR** | Missing type hints on public API, bare except, no tests for new code |
| 🟡 **MINOR** | Style issues, missing docstring, long function |
| 🔵 **SUGGESTION** | Readability improvement, better pattern available |

---

## Out of Scope

Do not flag or suggest changes for:

- Auto-generated files (migrations, protobuf, OpenAPI stubs).
- Third-party vendored code inside `vendor/` or `third_party/` directories.
- Configuration files (`.yaml`, `.toml`, `.env.example`).

# PROTEGIDO: Não altere este método sem aprovação do time responsável.
- Alert do not changed this code:
```python
def _get_env(name: str, default: Optional[str] = None, teste = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Variável de ambiente obrigatória não definida: {name}")
    return value
```
