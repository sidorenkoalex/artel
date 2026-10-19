# Записка analyst — 01M59KMPG2ZMK10V556VZVQD65 (G2а-1)

## Выяснено
- ТЗ достаточно, вопросов нет: пишу SPEC, не QUESTIONS.
- Закрепляемые тексты артели сверены по main: `scripts/guard.py:2283` EXTRANEOUS_ACCEPTANCE_FILE_REASON = "посторонний файл в каталоге планки"; `orchestrator/checkpoint.py:44` STRAY_ACCEPTANCE_FILES_DETAIL_PREFIX = "в каталоге планки посторонние файлы: "; `scripts/guard.py:2333` RESERVED_PLANK_HELPER_HINT = "имя занято помощником пульта"; `orchestrator/preflight.py:37` INPUT_FILTERS = (guard.is_extraneous_acceptance_test_file,); отказы `guard.py:2490-2536`; маркер красноты `guard.py:574-581`; `dry_run.py:78,84`; `fsm_autogate.py:264`; `acceptance.py:3354`.
- Сигналы деления: файлов зоны ≥5, AC ≥10. budget $50 (рамка ТЗ = дефолт) — сигнал бюджета (порог $60) не срабатывает. Дал обоснование монолита по образцу G1б (01M590GJAF0EDV4NBC4C99MFVH).

## Не сработало
- Составные bash-команды (`;`, пайпы с sed) требуют подтверждения — читать по одной команде.

## Где остановился
- SPEC написан (15 AC, status: ready, budget 50, обоснование монолита со швом «треб. 1–7 / треб. 8–9»), `guard.py` — ок. Раздела «Меняемое поведение» нет: у артели всё прежнее.

## Чего не хватило
- Ничего существенного: ТЗ уже несёт адреса строк.
