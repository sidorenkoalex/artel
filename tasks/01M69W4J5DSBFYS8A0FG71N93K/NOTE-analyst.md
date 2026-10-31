## Выяснено
- Возврат с spec_gate (К1): у bare origin нет user.name/email; CI глобальную идентичность не задаёт → commit-tree с --git-dir <origin> падает. Закрыто: требование 6 SPEC (явные `-c user.name='artel tests' -c user.email=artel@example.invalid`, значения tests/sandbox.py:1276-1277), AC-2 дополнен, AC-1 — проверка в окружении HOME=пустой каталог, GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_NOSYSTEM=1, без EMAIL.
- Остальное SPEC без изменений (5 AC, budget_usd 15 — рамка ТЗ, skip_tests, матрица неослабления). guard — ок.
- advance_origin сейчас — :56-70 файла; push по пути :63-64.

## Не сработало
- `echo rc=$?` в Bash отклоняется (simple_expansion) — звать guard без него.

## Где остановился
- Шаг завершён, SPEC status: ready.

## Чего не хватило
- Явного места, где CI задаёт git identity (его нет) — нашлось только в причине возврата.
