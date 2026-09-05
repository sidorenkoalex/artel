---
task: 01M1REVEZ1HESMJ7AFD5A9MEJ8
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

1. Предыдущий шаг developer ушёл в таймаут 45 минут: пять запусков
   полного набора `python3 -m unittest discover -s tests` за один шаг
   (каждый — минуты). Полный набор в шаге НЕ запускать — его гоняет CI
   кодовой ветки (skills/coding-standards.md). Проверять адресно: свои
   тесты (`tests/test_venv.py`, `tests/test_stack.py`,
   `tests/test_review_package.py`) и модули, которые правишь.
2. Код в кодовой ветке есть (16 файлов), но `PLAN.md` не написан —
   шаг без PLAN.md не засчитывается. Довести: PLAN.md со `status: ready`,
   раздел «Диф для Оператора» с unified-диффом `.github/workflows/ci.yml`
   (требование 3, `git apply --check` на чистом main), покрытие
   требований, риски.
3. Про «падение на чистом origin/main»: если конкретный тест `tests/`
   красный на main без твоих правок — назови его в PLAN.md (раздел
   «Риски») с командой воспроизведения и не чини его в этой задаче;
   не подгоняй.
4. Рабочие копии (`git worktree add/remove`) не создавать и не удалять —
   это территория оркестратора.
