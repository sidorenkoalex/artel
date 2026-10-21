# Записка spec_auditor

## Выяснено
- Аудит 2 (spec_sha ea291daa…): вердикт fail (второй возврат).
- Главное: требование 8 / AC-12 (тело test_ac1 two_sided → помощник с зерном) — гейт неослабления
  теряет 5 утверждений `self.assertEqual(res.returncode, 0, …)` из `RealGitSandbox.git`
  (tests/sandbox.py:1956–1959): они помощник первого уровня метода сейчас и второго — после переноса.
  Проверено прямым вызовом guard.test_assertions/changed_test_assertions (9 → 4, LOST ×5).
  Мандата на two_sided нет (ANSWER-1 — только kill-метод). Утверждение SPEC «гейт по two_sided полный» неверно.
- AC-16: в молчащем сценарии пуш удаления не доходит до pre-receive (Silence возвращается до http-backend,
  project_kill_cleanup.py:159–163) → `deletions()` пуст; «ровно один пуш по журналу» без новой записи в журнал невыполним.
- «срок молчания строго меньше времени самоосвобождения без предела» (треб. 11) не определён; pytest timeout 120 (pyproject.toml:13).
- Отклонения аудита 1 закрыты: флаг «не поднят», ANSWER-1, адреса isinstance/backup, db_tracked_count().

## Не сработало
- awk/цепочки команд требуют одобрения — по одной команде.

## Где остановился
- Готово: SPEC-AUDIT.md сдан (fail, второй возврат), guard ок.

## Чего не хватило
- Как guard считает помощники второго уровня — _helper_calls/_assertion_records, scripts/guard.py:1892–1962.
