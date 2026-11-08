# Записка developer

## Выяснено
- Реализация — конец `tests/sandbox.py`: `shared_state_snapshot`, `_shared_state_changes`, `_SharedModuleState`, `shared_readonly` (состояние модуля в `module.stash` по `pytest.StashKey`, уборка `module.addfinalizer`, `tests.fixtures._run_cleanups` лениво).
- Долгоживущие файлы задачи: 30/30 зелёные (≈45 с).
- `ps`: `/bin/ps -A -ww -o pid=,ppid=,stat=,command=` через `_REAL_POPEN` (pid самого ps исключается, зомби отброшены).

## Не сработало
- `cat >> file <<'EOF'` с кодом отклоняется хуком («brace with quote») — дописывал Edit.

## Где остановился
- Готово: мутации проверены (5 шт., все красные, код возвращён), карта регенерирована, `tests/test_invariants.py` 88 passed, guard PLAN ок, PLAN `status: ready`. Код не закоммичен — коммитит пульт.
- `pytest -n 4` в шаге роли падает «node down» — гонял без xdist (`-p no:xdist`).

## Чего не хватило
- —
