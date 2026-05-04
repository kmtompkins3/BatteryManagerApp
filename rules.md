# Coding Rules — Battery Tracker

This project is used in a learning environment. These rules exist so students can read, understand, and safely edit the code.

---

## 1. Explain What the Code Does

- Every function must have a short docstring that says **what it does** and **why it exists**.
- If a block of code is doing something non-obvious, add a plain-English comment above it.
- Prefer clear variable names over short ones. `scan_out_time` is better than `sot`.

```python
# Good
def get_total_uses(battery_id: int) -> int:
    """Returns the number of times this battery has been used (completed sessions only)."""
    ...

# Too terse — a student won't know what this means
def gtu(bid):
    ...
```

---

## 2. Keep Changes Focused and Simple

- Change **one thing at a time**. Don't refactor surrounding code unless it's directly related to the task.
- Avoid clever one-liners when a simple multi-line version is easier to read.
- If you need to add a helper function, put it in the same file and keep it short.
- Don't add features that weren't asked for.

```python
# Good — clear steps
elapsed_seconds = (now - cooling_start_time).total_seconds()
is_complete = elapsed_seconds >= cooling_limit_seconds

# Avoid — hard to read at a glance
is_complete = (datetime.now() - row.cooling_start_time).total_seconds() >= settings_dal.get_setting_int("cooling_minutes", 15) * 60
```

---

## 3. File and Folder Roles

Each folder has a specific job. Put new code in the right place:

| Folder / File | What goes here |
|---|---|
| `db/` | All database code — reading and writing to SQLite |
| `db/*_dal.py` | Functions for one specific table (DAL = Data Access Layer) |
| `app/services/` | Business logic — the rules of how the app works |
| `app/constants.py` | Status values and mode names used across the whole app |
| `app/exceptions.py` | Custom error types so problems are easy to identify |
| `app/state.py` | Tracks whether we're in Practice or Competition mode |
| `main.py` | Starts the app — kept as simple as possible |

**Rule:** UI code never goes in `db/` or `app/services/`. Database SQL never goes in `app/services/`. Keep the layers separate.

---

## 4. Error Handling

- Use the custom exception classes in `app/exceptions.py` instead of generic `Exception`.
- This makes it easy to understand *what went wrong* without reading the full traceback.
- If you need a new error type, add it to `exceptions.py` — don't create it inline.

```python
# Good
raise BatteryNotFoundError(battery_id)

# Avoid
raise Exception("battery not found")
```

---

## 5. No Magic Numbers

- Don't write raw numbers in logic. Use a named constant or read from settings.

```python
# Good
if elapsed_hours > PRACTICE_MAX_SESSION_HOURS:

# Avoid
if elapsed_hours > 3:
```

---

## 6. Test Your Change Manually Before Finishing

- Run `python main.py` — it should complete with no errors.
- Try the function you changed in a Python shell and verify it behaves as expected.
- If you broke something, fix it before moving on.
