---
task: 01M1TKP6AAY4W8GDGZNA9R0JZT
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: P1a — раннер pytest в пульте: acceptance, dry_run, amend и их тесты

# ТЗ: P1a — раннер pytest в пульте (acceptance, dry_run, amend и их тесты)

Источник: роадмап §3, фаза S, пункт P1 (деление P1a/P1b). Условие старта
выполнено: R6, R7, №15 смержены 06.09; pytest, pytest-timeout,
pytest-xdist закреплены в requirements.lock (P0), venv пульта есть.

Требуется:
1. Все места, где пульт сам запускает тесты и читает итог, переходят на
   pytest: `orchestrator/acceptance.py` (прогон планки `run(tdir,
   code_root=...)` и полного набора `run_full`), `dry_run.py`, `amend.py`
   — разбор итога вместо строки unittest «Ran N … OK» читает сводку
   pytest (`N passed`, `failed`, `error`); маркеры планки
   `# AC-n: manual|skip` и «Красен до реализации»/«Зелёный с рождения»
   — прежний разбор, не зависит от раннера.
2. Таймаут на каждый тест через pytest-timeout (значение — в манифесте
   стека `orchestrator/stack.py`, по умолчанию 120 с) — закрывает класс
   зависаний 04–05.09; `-p no:cacheprovider` либо `.pytest_cache` в
   исключениях автокоммита артефактов и в `.gitignore`.
3. `pyproject.toml`/`pytest.ini`: testpaths, python_files, таймаут;
   тесты в стиле unittest НЕ переписываются — pytest исполняет их как
   есть.
4. Тесты пульта, поднимающие `-m unittest` подпроцессом (≈10), переводятся
   на вызов pytest; утверждения о результате сохраняются по смыслу
   (зелёный/красный/число тестов).
5. `doctor`: проверка, что pytest из venv доступен ролям и пульту
   (`venv-packages` уже есть — расширить сообщение).
Не входит (P1b): CI-джоб, скилы, `role_prompt.py`, `templates/REVIEW.md`,
регулярки `scripts/guard.py`.

Зоны: orchestrator/acceptance.py, orchestrator/dry_run.py,
orchestrator/amend.py, orchestrator/stack.py, orchestrator/doctor.py,
pyproject.toml, tests/. Зона doctor.py сейчас у наблюдателя карты
(соседняя сессия, на приёмке) — стартовать после его мержа.

Рамка: $45.
