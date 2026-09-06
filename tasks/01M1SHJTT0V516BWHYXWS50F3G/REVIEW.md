---
task: 01M1SHJTT0V516BWHYXWS50F3G
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: автогейт приёмки — критерий «существующие tests/ зелёные» исполняется по CI

## Замечание к пакету ревью (диагностика перед вердиктом)

Ревью-пакет не смог показать `SPEC.md`/`PLAN.md` этой задачи (искал их
в КОДОВОЙ ветке, а не в артефактной, где они реально живут) и построил
инкрементальный diff от `1630619d` — коммита «подтяжка main», сделанного
ДО того, как разработчик закрыл замечания итерации 1. Из-за этого diff
пакета оказался забит содержимым ДВУХ чужих задач
(`01M1SAA2AZX3ERQ779QJ5TS9J4` — раздел «Причина возврата» в brief.py,
`01M1SCQ6WZHMQVK1AHP9F392JZ` — регрессия №15 в fsm_advance.py), которые
попали в эту ветку последующей подтяжкой main, и не имеет отношения к
предмету ревью — тот же класс, что уже отмечали ревью T082/T087/
01M1SCQ6WZHMQVK1AHP9F392JZ (итерация 4).

Восстановил фактический материал для ревью из рабочего каталога и git
напрямую:
- `tasks/01M1SHJTT0V516BWHYXWS50F3G/{SPEC,PLAN,REVIEW}.md` — прочитаны
  с диска (материализованы из головы артефактной ветки).
- `git diff --stat main...task/01m1shjtt0v516bwhyxws50f3g-avtogeyt-priyomki-kriteriy-sus`
  — 8 файлов зоны (`docs/codebase-map.md`, `orchestrator/acceptance.py`,
  `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`,
  `scripts/guard.py`, `tests/test_acceptance.py`,
  `tests/test_fsm_autogate.py`, `tests/test_guard_schema.py`) — это и
  есть фактический предмет ревью, совпадает с заявкой PLAN.md
  («Контекст» эскалации).
- `git log --oneline --all --grep=01M1SHJTT0V516BWHYXWS50F3G` — вся
  история задачи: `1d8a1b6b` (реализация требований 1-6), `5d841e89`
  (закрытие R1-F1/F2/F4), далее только подтяжки main и автокоммиты
  ANSWER/journal — `git diff 5d841e89..HEAD --stat -- <8 файлов зоны>`
  показывает изменения ТОЛЬКО в `orchestrator/fsm_advance.py` (143
  строки — регрессия №15, пришла подтяжкой main, не код этой задачи);
  остальные 7 файлов зоны не менялись с `5d841e89`.

## Фаза A: проверка плана

PLAN.md обновлён разделом «Эскалация» (снята решением ANSWER-3 —
регрессия №15 смержена, мост не нужен) и «Расширение зон» (мандат
ANSWER-1, одна строка `orchestrator/fsm_advance.py`). Покрытие
требований 1-6 таблицей плана не изменилось с итерации 1 и остаётся
полным. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (маркер `ci` в guard) | OK | Без изменений с итерации 1 — подтверждено повторно (`scripts/guard.py:167`, тесты `CiMarkerTraceabilityTest`). |
| 2 (автогейт исполняет `ci` по CI головы кодовой ветки) | OK | Без изменений с итерации 1 (`orchestrator/fsm_autogate.py:83-93`, `t["branch"]`, не артефактная — проверено тестом `test_ci_marker_queries_the_code_branch_not_the_artifact_branch`). |
| 3 (`ci` только для формулировки про существующие tests/) | OK | Без изменений — `ci_marker_wording_ok`. |
| 4 (сводка ручного гейта показывает `ci` вместе с результатом CI) | OK | Было «реализовано не так» в итерации 1 (фиктивный AC-9 из-за незаякоренного `AC_MARKER`) — теперь исправлено R1-F2, воспроизвёл лично (см. «Проверено исполнением»): `acceptance_traceability_errors`/`scan_acceptance_tests` на планке этой же задачи больше не находят AC-9. |
| 5 (`skills/test-authoring.md`) | OK | Приложение к PLAN не изменилось; `git apply --check` на чистом дереве пройден мной независимо повторно. |
| 6 (существующие тесты guard/автогейта зелёные) | OK | Было «без новых тестов» в итерации 1 (R1-F1) — теперь 12 новых тестовых методов в постоянном наборе (`tests/test_guard_schema.py`, `tests/test_fsm_autogate.py`, `tests/test_acceptance.py`); весь прогон 248/248 зелёный. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py, orchestrator/fsm_autogate.py, orchestrator/acceptance.py | PLAN обещал юнит-тесты на пометку `ci` в постоянном наборе — не было ни одного | будущая правка могла сломать fail-closed поведение требований 2/3/5 незамеченной | Прочитал все 4 новых класса (`CiMarkerTraceabilityTest`, `AcMarkerLineAnchorTest` в tests/test_guard_schema.py; `CiMarkerConditionTest` в tests/test_fsm_autogate.py; `SummaryCiCriteriaTest` в tests/test_acceptance.py) — 12 методов, каждый с докстрингом/заявкой на конкретную мутацию, сверены с реальным поведением кода. Прогнал `python3 -m unittest tests.test_guard_schema tests.test_fsm_autogate tests.test_acceptance tests.test_ci_status tests.test_acceptance_tests_flow tests.test_guard_zones tests.test_guard_split_signals tests.test_guard_extraneous_acceptance_files` — 248/248 зелёных. Закрыто целиком. |
| R1-F2 | accepted | scripts/guard.py:167 (`AC_MARKER`) | незаякоренный regex матчил буквальный текст пометки внутри докстрок как настоящую пометку — сводка показывала фиктивный AC-9 | AC-6 не выполнялся на практике для планки этой же задачи | `AC_MARKER` заякорена на начало строки (`^`, `re.M`). Воспроизвёл лично: `guard.acceptance_traceability_errors(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"))` → `[]` (было: ошибка про фиктивный AC-9); `python3 scripts/guard.py tasks/01M1SHJTT0V516BWHYXWS50F3G/{SPEC,PLAN,REVIEW}.md` → «GUARD: ок»; полный прогон 8 приёмочных тестов задачи (`tasks/01M1SHJTT0V516BWHYXWS50F3G/acceptance_tests/`) — 8/8 зелёных, включая AC-1/AC-2/AC-6, которые в итерации 1 были красны на реальной планке. Закрыто. |
| R1-F3 | accepted | acceptance_tests/test_ac7_ac8_manual_markers.py:18 | AC-8 сформулирован про класс «существующие tests/ зелёные», но помечен `manual`, не `ci` | не блокирует, наблюдение для ретро | Разработчик отклонил с обоснованием: `acceptance_tests/` этой задачи залочен после `tests_writing` (tasks/T023), правка чужого файла вне прав developer без отдельного мандата. Обоснование выдерживает критику — `manual` валидная пометка по SPEC, дефекта в коде нет, сам ревьювер итерации 1 отметил пункт необязательным наблюдением, не требованием. Принимаю отказ. |
| R1-F4 | accepted | scripts/guard.py:538 (`traceability_errors_from_content`) | пометка `ci` не требовала причины в guard, в отличие от skip/escalate | «# AC-n: ci» без причины проходил бы guard молча | Ветка `kind in ("skip", "escalate")` расширена до `("skip", "escalate", "ci")`. Проверил тестом `test_ci_marker_without_reason_is_rejected` (tests/test_guard_schema.py) — отказывает тем же сообщением, что skip/escalate. `manual` осознанно не тронут (предсуществующий пробел, не объём этой задачи, задокументировано как наблюдение) — согласен с этим ограничением объёма. Закрыто. |

Реестр закрыт целиком — все четыре записи предыдущей итерации переведены в `accepted`, новых записей эта итерация не заводит.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_guard_schema tests.test_fsm_autogate tests.test_acceptance tests.test_ci_status tests.test_acceptance_tests_flow tests.test_guard_zones tests.test_guard_split_signals tests.test_guard_extraneous_acceptance_files -v` — 248 тестов, все зелёные (в т.ч. новые `CiMarkerTraceabilityTest`, `AcMarkerLineAnchorTest`, `CiMarkerConditionTest`, `SummaryCiCriteriaTest`, 12 методов).
- `python3 -m unittest discover -s tasks/01M1SHJTT0V516BWHYXWS50F3G/acceptance_tests -v` — 8 приёмочных тестов задачи (AC-1..AC-6), все зелёные (в итерации 1 планка не гонялась целиком — только точечные прямые вызовы; в этой итерации прогнал файл целиком).
- `python3 scripts/guard.py tasks/01M1SHJTT0V516BWHYXWS50F3G/SPEC.md tasks/01M1SHJTT0V516BWHYXWS50F3G/PLAN.md tasks/01M1SHJTT0V516BWHYXWS50F3G/REVIEW.md` — «GUARD: ок (3 файлов)».
- `guard.acceptance_traceability_errors(Path("tasks/01M1SHJTT0V516BWHYXWS50F3G"))` (прямой вызов) — `[]`, регресс R1-F2 не воспроизводится.
- `git diff --stat main...task/01m1shjtt0v516bwhyxws50f3g-avtogeyt-priyomki-kriteriy-sus` и `git diff 5d841e89..HEAD --stat -- <8 файлов зоны>` — подтвердили фактический объём diff (8 файлов, дальнейшие изменения зоны с момента закрытия замечаний — только merge-приход `orchestrator/fsm_advance.py` из main, не код этой задачи) взамен контаминированного diff'а пакета (см. «Замечание к пакету ревью»).
- Построчно прочитан diff `main...HEAD` по всем 8 файлам зоны и оба содержательных коммита (`1d8a1b6b`, `5d841e89`) целиком — сверены с текстом PLAN.md «Подход»/«Шаги» и реестром замечаний.
- `python3 scripts/codebase_map.py`, сравнение с закоммиченной версией без строки `built_at_sha` (`git diff --stat` после регена — только строка `built_at_sha`, 1 файл) — карта свежая; откатил `git checkout -- docs/codebase-map.md`.
- `python3 -c "import ast; ast.parse(...)"` на все 4 изменённых модуля кода — парсятся; `grep` на маркеры конфликта слияния (`<<<<<<<`/`=======`/`>>>>>>>`) — не найдено.
- Проверка приложения к PLAN: скопировал unified-дифф `skills/test-authoring.md` во временный файл (удалён после проверки), `git apply --check` на чистом дереве — применяется без конфликтов.
- `git status --short` после всех проверок — только неотслеживаемый `tasks/01M1SHJTT0V516BWHYXWS50F3G/`, рабочее дерево чистое.
- Полный набор `tests/` не гонял (решение Оператора 05.09, гоняет CI на каждый пуш) — только планка задачи и юниты затронутых модулей (список выше).

## Предложения системе

- Пакет ревью для этой задачи собрал diff от sha, оказавшегося
  коммитом «подтяжка main» ДО закрытия замечаний итерации 1, — показал
  47+ файлов от двух чужих задач вместо 8 файлов реального предмета
  ревью, и не смог найти SPEC.md/PLAN.md вовсе (искал их в кодовой
  ветке, где они не живут). Тот же класс независимо отмечен в эту же
  сессию ревью `01M1SAA2AZX3ERQ779QJ5TS9J4` (итерация 2) и
  `01M1SCQ6WZHMQVK1AHP9F392JZ` (итерация 4) — три случая подряд одного
  вечера, стоит закрыть системно (сверка sha предыдущего вердикта с
  фактическим коммитом REVIEW.md в артефактной ветке, а не с историей
  кодовой ветки как есть).
