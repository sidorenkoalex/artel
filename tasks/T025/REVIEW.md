---
task: T025
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: A5 — роль analyst: SPEC из свободного ТЗ Оператора

## Фаза A — гейт плана

Покрытие требований в PLAN полное (таблица «Покрытие требований» —
все 5 требований закрыты шагами, требование 5 обоснованно без шага
кода). Шаги 1–9 — проверяемые единицы размера MR, не микрооперации.
Подход (ролевая функция `runner.step_role` вместо правки статического
`config.STATE_ROLE`) не конфликтует с существующей архитектурой и
явно защищает два существующих регрессионных теста-инварианта.
Раздел «Влияние на систему» соответствует фактическому diff — protected
paths (`roles.yaml`, `skills/spec-authoring.md`, `templates/QUESTIONS.md`)
названы точно, лишних side effects нет. Гейт плана — без замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (ТЗ артефактом, обратная совместимость) | Реализовано не так | `catalog.cmd_new`/`runner.step_role` корректны и покрыты тестами; CLI-разбор `--tz` в `artel.py` крашится необработанным traceback без значения флага — см. замечание ниже |
| 2 (spec_writing исполняет analyst при ТЗ; run/auto; роль/скилы) | OK | `runner.step_role`, `auto.cmd_auto`, `roles.yaml` — покрыты тестами (`RunAnalystTest`, `AutoAnalystTest`) |
| 3 (выход SPEC по шаблону, guard на переходе) | OK | Регрессия существующей AC-механики T017/T023 подтверждена тестом и живым прогоном guard |
| 4 (батч вопросов, эскалация, второй батч только после ответа) | OK | `fsm.cmd_advance` проверяет `QUESTIONS.md` до статуса SPEC; второй батч структурно блокирован `escalated` вне `STATE_ROLE`/`step_role` — подтверждено тестами |
| 5 (spec_gate без изменений) | OK | `cmd_approve` для `spec_gate` не тронут diff'ом |

## Замечания

- major — `orchestrator/artel.py:141-142` — `"new": lambda: catalog.cmd_new(rest[0], tz_path=(rest[rest.index("--tz") + 1] if "--tz" in rest else None))` — если Оператор набирает `new "название" --tz` без пути к файлу (флаг последним аргументом или без значения), `rest.index("--tz") + 1` выходит за границы списка и роняет CLI необработанным `IndexError: list index out of range` вместо понятного сообщения — воспроизведено вручную (`python3 -c "...('new','Тест','--tz')..."` → `UNHANDLED: IndexError`). Это разрывает конвенцию, которую сам же diff вводит для соседнего случая (`catalog.cmd_new`: нечитаемый путь ТЗ отдаёт чистый `sys.exit` с причиной, а не трейсбек) — новый код `artel.py` под тем же требованием 1 должен вести себя так же. Тестами этот путь не покрыт (в `CmdNewTzTest` есть только «путь не читается», а не «флаг без значения»). Предложение: валидировать наличие значения после `--tz` до вызова `cmd_new` и отдавать `sys.exit` с понятной причиной (по образцу остальных отказов в этом файле/модуле).

## Вердикт

changes_requested — один major: `orchestrator/artel.py:141-142`, необработанный
`IndexError` на `new "..." --tz` без значения флага (см. замечание выше).
Всё остальное по SPEC T025 реализовано корректно и покрыто тестами;
`python3 -m unittest discover -s tests` — 499/502 (3 падения в
`tests/test_multitarget.py::RoleEnvTest`, файл вне diff'а этой задачи,
падения из-за реального `~/.gitconfig` окружения ревью, не из-за
изменений T025 — не блокируют); `python3 scripts/guard.py --all` — ок
(62 файла).
