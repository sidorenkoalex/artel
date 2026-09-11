---
task: 01M287TPG0HAVXS8CHBCY679WN
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: `answer` для задачи в `in_dev` (мандат на расширение зон), `zones-extend`, `amend-tests --from-branch`

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`answer` в `in_dev`/`review` по маркеру) | реализовано, замечание R1-F1 | AC-1/AC-2/AC-3 покрыты и зелены (`orchestrator/answer.py:100-120`), но команда становится новым штатным каналом, которым РОЛЬ, ведущая свой же шаг `in_dev`/`review`, может сама себе выдать мандат — см. R1-F1 |
| 2 (`zones-extend`) | реализовано, замечание R1-F1 | AC-4/AC-5/AC-6 покрыты и зелены (`orchestrator/answer.py:147-190`); тот же риск самоавторизации, что и требование 1 — общий класс, одно замечание |
| 3 (`amend-tests --from-branch`) | OK | AC-7/AC-8/AC-9 покрыты и зелены (`orchestrator/amend.py:59-63,309-391`); PLAN сознательно не гоняет pytest перед сдвигом лока и явно объясняет почему — защитимое чтение SPEC, критериям не противоречит |
| 4 (существующие тесты зелёные, без правки ассертов) | OK | `tests/test_answer*.py`/`tests/test_amend*.py`/`tests/test_zones_gate.py` — только добавления классов, ни один существующий ассерт не тронут (проверено диффом и прогоном, 62/62 зелёных) |
| 5 (доки обновлены) | OK | `docs/operator-session.md`/`docs/operator-gates.md` описывают новый штатный путь вместо ручного трёхшагового обхода, текст соответствует реализации |

## Замечания

- **blocker** — `orchestrator/answer.py:114-120` (новая ветка `_cmd_answer` для `in_dev`/`review`) и `orchestrator/answer.py:147-190` (`cmd_zones_extend`/`_cmd_zones_extend`) — обе новые команды принимают мандат «от Оператора» БЕЗ проверки, что вызов пришёл не из окружения самой роли, ведущей этот же шаг. До этой задачи `answer` работал только для `escalated` — состояния, в котором сессия роли уже закончилась (эскалация останавливает шаг), поэтому у роли физически не было работающего процесса, способного вызвать команду за себя. Эта задача открывает `answer`/`zones-extend` именно для `in_dev`/`review` — состояний, в которых процесс роли (developer/reviewer) АКТИВНО выполняется и по конфигурации шага (`orchestrator/runner.py:665-681`, `role_cmd()`) получает `--permission-mode acceptEdits` и белый список `--allowedTools "Bash(git:*),Bash(python3:*)"` — то есть безусловное, без подтверждения человека, право выполнить ЛЮБУЮ команду `python3 ...`, включая `python3 orchestrator/artel.py`. Курируемый слой роли (`docs/reference/role-home/claude/settings.json`) запрещает только `init`, `doctor --restore` и связанное с расшифровкой пула канарейки — записи, закрывающей `answer`/`zones-extend`, нет. Итог: developer на своём шаге `in_dev` может выполнить `python3 orchestrator/artel.py zones-extend <свой же id> <любой путь>` (или `answer <свой же id> <файл-со-строкой «Расширение зон разрешено: ...»>`, написанный им самим) и сам себе выдать «мандат Оператора» на расширение зон — то же верно для reviewer на шаге `review`. Кодовая база уже один раз находила и чинила ровно этот класс атаки для соседнего механизма: `orchestrator/fsm_advance.py:654-676` (`_answer_commit_is_role_step_autocommit`, докстринг явно ссылается на R2-F1 — «именно так developer мог бы подложить себе поддельный ANSWER-n.md с маркером мандата в СВОЁМ ЖЕ шаге in_dev») и для расшифровки пула канарейки применена симметричная двухуровневая защита — `permissions.deny` в `settings.json` ПЛЮС независимая проверка в коде `runner.in_role_environment()` (`orchestrator/canary.py:317`, докстринг `runner.py:571-580` прямо называет её «вторым, независимым от permissions.deny рубежом»). Эта задача вводит новый класс команд той же чувствительности (Оператор дистанционно расширяет зону/права задачи) и не применяет к нему ни один из двух уже существующих в кодовой базе рубежей защиты. SPEC/PLAN нигде не рассматривают и не отклоняют этот сценарий явно (раздел «Не входит» SPEC его не упоминает).
  Предложение: добавить в `_cmd_answer` (ветка `in_dev`/`review`) и в `_cmd_zones_extend` отказ по образцу `canary.py:317` — `if runner.in_role_environment(): sys.exit(...)`, и синхронно завести в `docs/reference/role-home/claude/settings.json` запись `permissions.deny` для `Bash(python3 orchestrator/artel.py answer:*)`/`Bash(python3 orchestrator/artel.py zones-extend:*)` (этот файл вне заявленных zones задачи — оформить как приложение unified-диффом к PLAN, тем же путём, каким скил велит проводить правки защищённых путей, либо через саму штатную процедуру `zones-extend`, которую эта задача и вводит). Если Оператор считает риск приемлемым (например, потому что реальные шаги роли сегодня физически не имеют повода вызывать `artel.py` и это гипотетический, не наблюдавшийся класс) — это решение Оператора по ADR, не молчаливое умолчание кода.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/answer.py:114-120, orchestrator/answer.py:147-190 | `answer` (ветка `in_dev`/`review`) и `zones-extend` не проверяют `runner.in_role_environment()` — роль, ведущая свой же шаг `in_dev`/`review`, технически может вызвать команду за «Оператора» и сама себе выдать мандат на расширение зон | самоавторизация роли: developer/reviewer расширяет себе зону без реального участия Оператора, обходя именно тот класс атаки, для которого в кодовой базе уже есть прецедент защиты (canary, `_answer_commit_is_role_step_autocommit`/R2-F1) | добавить проверку `runner.in_role_environment()` в обеих новых точках (по образцу `canary.py:317`) и параллельную запись в `permissions.deny` курируемого слоя роли, либо явное решение Оператора принять риск |

## Вердикт

`changes_requested` — закрыть R1-F1 (добавить проверку `runner.in_role_environment()` в новой ветке `_cmd_answer` и в `_cmd_zones_extend`, синхронизировать курируемый слой роли) либо получить явное решение Оператора, что риск самоавторизации роли принимается без технической защиты. Требования 3-5 и тестовое покрытие требований 1-2 нареканий не имеют — остального дорабатывать не нужно.

## Проверено исполнением

- `python3 -m unittest tests.test_answer tests.test_amend tests.test_zones_gate -v` — 62 теста, все зелёные.
- `python3 -m unittest tasks.01M287TPG0HAVXS8CHBCY679WN.acceptance_tests.test_ac1_ac2_ac3_answer_mandate_in_dev tasks.01M287TPG0HAVXS8CHBCY679WN.acceptance_tests.test_ac4_ac5_ac6_zones_extend tasks.01M287TPG0HAVXS8CHBCY679WN.acceptance_tests.test_ac7_ac8_ac9_amend_from_branch -v` — 12 приёмочных теста задачи (AC-1..AC-9), все зелёные.
- `python3 scripts/codebase_map.py --check` — карта актуальна (без вывода расхождений).
- Диф `tests/test_answer.py`/`tests/test_amend.py`/`tests/test_zones_gate.py` прочитан построчно — только добавленные классы, ни один существующий ассерт не удалён и не ослаблен.
- CI коммита 03abe3d4 — зелёный (7 проверок), по данным пакета ревью.

## Предложения системе

- Класс «новая Оператор-only команда добавлена без проверки `runner.in_role_environment()`/записи в `permissions.deny`» стоит вынести отдельным пунктом чек-листа `skills/review-checklist.md` («Безопасность») — сейчас про этот прецедент (`canary.py`) знает только код, а не скил ревьювера, и его пришлось искать вручную по кодовой базе, а не по инструкции.
