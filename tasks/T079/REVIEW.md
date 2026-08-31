---
task: T079
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 5
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: B1b: GitHub-адаптер, Draft-MR и состояние verifying

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (Draft MR на первый вход в in_dev, один на цикл) | OK | Не тронуто этой итерацией; закрыто и подтверждено в итерациях 2-3. |
| 2 (undraft на входе в merge_gate) | OK | Не тронуто этой итерацией. |
| 3 (merge — побочный эффект локального push, не API-вызов) | OK | Не тронуто этой итерацией. |
| 4 (verifying между review и acceptance) | OK | Не тронуто этой итерацией; эскалация закрыта в итерации 3 через ADR-0009 Оператора (`docs/adr/0009-verifying-route.md` присутствует). |
| 5 (четыре исхода статуса CI в verifying) | OK | Не тронуто этой итерацией. |
| 6 (потолок ожидания → escalated) | OK | Не тронуто этой итерацией. |
| 7 (красный CI не выталкивает автоматически) | OK | Не тронуто этой итерацией. |
| 8 (reject расширен на verifying) | OK | Не тронуто этой итерацией. |
| 9 (механизм периодического вызова advance вне объёма) | OK | Не тронуто этой итерацией. |

`git diff 26ca4f3..HEAD -- orchestrator/ tests/` пуст: эта итерация не
трогает ни одной строки функционального кода или тестов (подтверждено
командой в «Проверено исполнением»). Единственная содержательная
правка diff-статистики пакета — `docs/codebase-map.md` (регенерация,
закрывающая единственное major-замечание итерации 4). `tasks/T079/
PLAN.md` получил только текстовую запись итерации 4 (журнал работы,
не код).

`docs/roadmap.md` в diff-статистике пакета присутствует, но это не
правка этой ветки: файл идентичен текущему `main` (`git diff
main...HEAD --stat` вообще не содержит `docs/roadmap.md`) — в diff от
устаревшей базы пакета (`26ca4f3`) он всплывает только потому, что
merge-коммит `6311782` («подтяжка main») подтянул более свежий `main`,
где эта правка (`ac5efcb`, отдельный не-T079 коммит с решением
Оператора по дебрендизации, подтверждено `git merge-base main HEAD` ==
`ac5efcb` и `git branch --contains ac5efcb` == `main`) уже была. Не
замечание — тот же класс явления, что итерация 4 уже разбирала для
`orchestrator/{ci,config,fsm,runner}.py` из T082: файл вне `no_paths`
(AC-14 явно называет только `gates.yaml`, `roles.yaml`, `targets.yaml`,
`.github/`, `templates/`, `skills/`, `docs/invariants.md`,
`tests/test_invariants.py`, `CLAUDE.md`), содержимое не расходится с
main — то есть ни AC-14 не нарушен, ни объём задачи фактически не
расширен.

## Замечания

Замечание итерации 4 (major, `docs/codebase-map.md` не регенерирован
после слияния main — карта откатилась к версии main и потеряла раздел
`orchestrator/github_adapter.py`) закрыто: карта на HEAD (`6311782`)
регенерирована заново тем же шагом («T079: регенерация codebase-map
после слияния main», коммит `2ab206c`) и сверена построчно с текущим
кодом — расхождение отсутствует, кроме строки `built_at_sha`
(исключаемой CI-джобом `codebase-map` из сравнения, см. «Проверено
исполнением»). Раздел `orchestrator/github_adapter.py` и обе тестовые
ссылки (`tests/test_github_adapter.py`, `tests/test_fsm_draft_mr_
reentry.py`) на месте.

Новых замечаний нет.

## Вердикт

approved — единственное замечание итерации 4 (устаревшая
`docs/codebase-map.md` после слияния main) закрыто регенерацией и
подтверждено построчной сверкой; функциональный код этой итерацией не
менялся. Все требования SPEC (1-9) и критерии приёмки (AC-1..AC-14)
выполнены; полный юнит-сьют и локед `acceptance_tests` зелёные; T052/
T053 (мьютекс и три исхода провала merge) не задеты; AC-14 (диапазон
путей) подтверждён заново.

## Проверено исполнением

- `git log --oneline -8`, `git status --short` — дерево чистое, HEAD
  `6311782df6efd22e05d20118ab0b17118c938af1`.
- `git merge-base main HEAD` → `ac5efcb47565265caf65eb12e0c06c1a5b7ba979`;
  `git branch --contains ac5efcb` → `main` и текущая ветка задачи —
  подтверждено, что `ac5efcb` («роадмап: Д1 — дебрендизация», решение
  Оператора 31.08) — коммит main, попавший в ветку задачи только через
  слияние, не собственная правка этой ветки.
- `git diff main...HEAD --stat` — 31 файл, все в `orchestrator/`,
  `tests/`, `tasks/T079/` и `docs/codebase-map.md`; `docs/roadmap.md`
  в списке НЕТ (файл идентичен main).
- `git diff HEAD...main --stat` — единственное расхождение в обратную
  сторону: новый файл main `docs/audits/roadmap-audit-prompt-v6-
  complex.md` (134 строки, не относится к T079; ветка задачи отстаёт
  от текущего кончика main на один документ-коммит — некритично, эта
  задача не обязана подтягивать main до последнего коммита).
- `python3 scripts/codebase_map.py` (регенерация на месте) → `git diff
  --stat -- docs/codebase-map.md` — 1 строка изменена; `git diff --
  docs/codebase-map.md` показывает единственный изменённый хунк — саму
  строку `built_at_sha` (старое значение указывало на коммит
  `26ca4f3`, регенерация проставила текущий HEAD `6311782` — ожидаемо,
  CI-джоб `codebase-map` эту строку из сравнения исключает). Сразу
  после проверки — `git checkout -- docs/codebase-map.md`, рабочее
  дерево вернулось к чистому состоянию (`git status --short` — пусто).
- `python3 -m unittest discover -s tests` — **1099 тестов, 0 красных,
  0 ошибок** (то же число, что в итерации 4 — регресса нет).
- `cd tasks/T079/acceptance_tests && python3 -m unittest discover -s .
  -p "test_*.py"` — **19/19 зелёные** (AC-1..AC-14, включая AC-4).
- `python3 -m unittest tests.test_merge_lock tests.test_advance_guard
  tests.test_fsm_draft_mr_reentry` — зелёные (T052/T053 не задеты,
  AC-13; Draft MR на всех точках входа — не регрессировало).
- `python3 scripts/guard.py --all` — «GUARD: ок (292 файлов)».
- `git diff main --stat -- gates.yaml roles.yaml targets.yaml .github/
  templates/ skills/ docs/invariants.md tests/test_invariants.py
  CLAUDE.md` — пусто: ни один путь `no_paths` target `artel` веткой не
  тронут (AC-14 подтверждён заново).
- `git diff 26ca4f3..HEAD -- orchestrator/ tests/` — пусто: подтверждает
  утверждение PLAN.md итерации 4 «функциональный код этой итерацией не
  менялся».
- `ls docs/adr/ | grep 0009` → `0009-verifying-route.md` присутствует —
  подтверждает закрытие эскалации итерации 1/3 по требованию 4
  (`review -> verifying` в один вызов `advance` при уже-зелёном CI).

## Предложения системе

Пусто — предложение итерации 4 (регенерировать карту после `git merge`
из main, если merge задел `orchestrator/`/`scripts/`/`tests/` с любой
стороны, отдельным шагом после разрешения конфликтов) актуально и
подтверждено этой же итерацией как рабочий приём: разработчик применил
его буквально (`2ab206c`), проблема не повторилась.
