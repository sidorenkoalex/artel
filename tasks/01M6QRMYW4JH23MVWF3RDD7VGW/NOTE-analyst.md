## Выяснено
- Факты ТЗ сверены с кодом на ветке: `orchestrator/acceptance.py` — `COMPOSE_OVERRIDE_RULE` :830-834 (версия «1:»), `_socket_source` :1049, `_bind_sources` :1063, `_compose_config_refusal` :1077 (порядок: сервисы → сети → тома → secrets/configs), вызов :1286. Других вызовов нет.
- `tests/` — общая зона (`config.COMMON_ZONES`), поэтому `zones:` = acceptance.py, tests/.
- Тесты ядра: `base_config` даёт bind и build.context под `@TREE@` — новая проверка их не должна краснить; тест Docker монтирует `../{left}:/work`.
- SPEC написан, status: ready, guard ок. Бюджет $30 = рамка Оператора; сигналы деления (10 AC, $30) закрыты обоснованием монолита.

## Не сработало
- `ls` в оболочке шага недоступен; составная команда с `$?` отклонена («simple_expansion»).

## Где остановился
- Готово: SPEC.md сдан, QUESTIONS.md не создавался.

## Чего не хватило
- Ничего существенного: ТЗ несёт точные адреса строк.
