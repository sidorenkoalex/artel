# Записка analyst

## Выяснено
- Возврат из spec_gate (3 уточнения повторного аудита) внесён, guard ок, status: ready.
  - AC-7: ожидаемые argv/cwd — литералы теста; вычисляемы только `stack.pytest_python_executable()` и временные каталоги; строить ожидание через `_pytest_command`/`_pytest_env` запрещено.
  - AC-7: наборы env по местам: все восемь ставят PYTHONPYCACHEPREFIX (все идут через `_pytest_env`, acceptance.py:86; каталог из tempfile, вне cwd); `_run_full_suite_to_log` ещё PYTHONUNBUFFERED="1" (:1372); `two_sided._run_side` ещё REPORT_ENV=путь отчёта и PYTHONPATH с началом plugin_dir (two_sided.py:230-232).
  - Треб. 3/AC-2/AC-6: `..` — сегмент пути, как у вида dir (targets.py:300-301): a/../b отказ, a..b проходит.
- Прочее в SPEC не менялось (8 AC, бюджет 25).

## Не сработало
- `; echo rc=$?` в Bash режет разрешение (simple_expansion) — звать guard без него.

## Где остановился
- SPEC сдан, QUESTIONS.md нет.

## Чего не хватило
- —
