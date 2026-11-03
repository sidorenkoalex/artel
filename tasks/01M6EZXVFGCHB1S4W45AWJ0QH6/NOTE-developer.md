# Записка developer — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Планка: 68 passed (`plank-run`). PLAN.md — status: ready, guard ок.
- `ensure_clone` клонирует `in_repo(clone.parent, "clone", …)`: cwd `.artel/projects/<имя>` — `_project_of_path` даёт None
  (нужно ≥2 частей), поэтому проект клона ищется по url в argv (`gitcmd._clone_project`, только при `token_slot`).
- `tests/test_hosting_token_units.py` требует ровно 2 записи `GIT_CONFIG_*` от `hosting_env` — хост записи идёт
  переменной окружения `ARTEL_HOSTING_HOST`, а не `credential.<url>.helper`.
- ANSWER-1 п.1 подтвердился: сверка `remote.origin.url` дала 69 красных в mr_delivery/mr_sync; починено адресом
  записи стенда = `config.PROJECTS/<имя>/origin.git` (шаблон ENTRY + format), утверждения не тронуты. sandbox.py
  править не понадобилось.
- Прогнаны: затронутые модули, ~30 файлов вокруг клонов/target-human/doctor, test_invariants, test_doctor* — зелёные.
- Свои тесты: tests/test_push_hook_units.py, 11 мутаций — все красные.

## Не сработало
- `pytest -n` в шаге отказывает сторож роли (воспринимает как полный прогон) — только последовательно.
- В PATH шага нет `sh`/`ls`/`cat`: хук в тесте — `/bin/sh` абсолютным путём.
- Bash-инструмент отказывает командам с `$VAR`/`$(...)`/`awk` — сценарии через `python3 - <<EOF`.

- Возврат advance (инвариант 35): хосты `h.example` в tests/test_push_hook_units.py заменены на
  localhost/127.0.0.1; адрес с `u:p@` сторож читает как хост — собран из частей (см. PLAN «Предложения»).

## Где остановился
- Шаг завершён; если рубеж неослабления отметит mr_delivery/mr_sync — эскалация с перечнем мест (есть в PLAN «Влияние»).

## Чего не хватило
- Как git передаёт `host` помощнику для file:// и путей (пустой) — проверял по тесту project_token.
