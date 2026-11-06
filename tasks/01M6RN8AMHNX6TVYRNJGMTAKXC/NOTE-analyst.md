# NOTE-analyst

## Выяснено
- Факты ТЗ сверены с кодом: `PULT_ACTOR_TRAILER` gitcmd.py:544, `pult_message` :585-593, `LOCAL_FIELDS` targets.py:391-411, `_check_delivery` :664, `co_author` :721-727.
- `target-set` (projects.py::cmd_target_set) generic: поле, известное `LOCAL_FIELDS`, пишется без правки projects.py. Проверено: `yamlmini` читает аргумент `Harness-Actor: orchestrator` строкой, `_literal` пишет `"Harness-Actor: orchestrator"`, обратное чтение — та же строка.
- `_argument_value` отказывает пустому значению — запись `""` через target-set невозможна, в SPEC вынесено в «Не входит» (projects.py только чтение).

## Не сработало
- Первый прогон guard: сигнал «число файлов» (считает пути в тексте) — добавлена секция «Оценка объёма» с прогнозом диффа 12 КиБ и обоснованием монолита.

## Где остановился
- SPEC.md status: ready, guard ок. budget_usd 25 (рамка ТЗ $20 ниже планки $25).

## Чего не хватило
- Ничего существенного.
