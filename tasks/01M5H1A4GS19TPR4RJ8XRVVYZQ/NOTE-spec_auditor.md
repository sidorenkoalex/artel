# Записка spec_auditor — 01M5H1A4GS19TPR4RJ8XRVVYZQ

## Выяснено
- Номера строк SPEC сверены с кодом worktree (HEAD 33547d9a) — все сходятся; 13 сборок `tests_dir` подтверждены `pytest --collect-only`.
- Гейт неослабления тестов сравнивает утверждения ОДНОИМЁННОГО метода (scripts/guard.py:2056 `changed_test_assertions`, orchestrator/advance_gates/test_integrity.py:690): метод под старым именем с одним первым подслучаем теряет утверждения других ветвей у test_ac8 (outcome_gate.py:1454-1464), test_ac11 (1711-1714), test_ac9 (spec_audit_flow.py:747,758,781-784) → находка гейта → эскалация. Сверка SPEC треб. 7 (⊆ объединения) слабее гейта.
- pytest_own_places `check_home` копит `self.homes` через все места метода (:440-442) — разбиение по одному месту ослабляет проверку «общий HOME на несколько прогонов».
- `PLACES` — литерал модуля (:62), не перечень времени выполнения; `FULL_PLACES`/`TWO_SIDED` — срезы по позиции (:66-67).
- Артель вне границы гейта исходов (orchestrator/advance_gates/acceptance.py:213) — исчезновение `tests_dir` отказа не даст.

## Не сработало
- `ls`, `awk` в Bash недоступны/требуют подтверждения — пользовался find/grep/Read.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан (status: ready), guard — «ок». Шаг завершён.

## Чего не хватило
- Дольше всего искал, по каким именам гейт сравнивает утверждения (guard.changed_test_assertions — только живые по обе стороны имена).
