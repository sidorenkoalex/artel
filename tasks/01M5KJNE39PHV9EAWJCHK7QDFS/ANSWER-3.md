---
task: 01M5KJNE39PHV9EAWJCHK7QDFS
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

# Ответ Оператора на эскалацию разработчика (23.10.2026, вопрос 1)

1. **(а)**. Планка AC-6 поправлена командой `amend-tests` (7a1b6853): в `foreign_statements` допущен ровно один узел `Try` канонической формы — импорт `prefer_direct_git`; обработчик `ModuleNotFoundError as exc` с `if exc.name != 'tests.direct_git': raise`, затем `DIRECT_GIT_DIR = None`; `else` — `DIRECT_GIT_DIR = prefer_direct_git(os.environ)`. Иная форма — посторонний код, как прежде. Ограда в `tests/__init__.py` рабочей копии остаётся как есть; код не менять. Толкование AC-6 SPEC: ограда этой формы — допустимая часть правки `tests/__init__.py` (решение Оператора на возврате из verifying). Шаг сдаётся `ready`.

Существующие тесты не правятся; мандата нет.

Независимая проверка: форма в планке совпадает с текстом `tests/__init__.py` рабочей копии (ast.unparse одинаков); планка AC-6 на рабочей копии — зелёная (прогон 23.10, `-p no:xdist`); прочие утверждения планки не изменены.
