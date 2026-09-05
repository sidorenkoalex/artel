---
task: 01M1P9RJVYHTAC087J4B2CAR44
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 3
---

# REVIEW: Инкрементальный дифф ревью после A7: база из кодовой ветки (регрессия №10)

## Соответствие SPEC

Пакет этого прогона тоже пришёл с той же болезнью, которую задача чинит:
инкрементальный diff от base sha `00e32aaf2c15059ffb72260275b29b9d2b53e8fe`
не собрался (`git diff 00e32aaf...task/... ` -> «Invalid symmetric
difference expression», объекта нет в репозитории пульта). Восстановлен
вручную тем же приёмом, что в итерации 2: найден коммит вердикта
итерации 2 — `REVIEW.md` со `status: changes_requested, iteration: 2`
существует ТОЛЬКО на task-ветке в составе WIP-чекпоинта `e610b41c`
(автокоммит оркестратора «шаг developer прерван»), текст ревью в нём
ссылается на `git diff 7d538ec1 HEAD --stat` с результатом «только
`docs/codebase-map.md` и `PLAN.md`» — это опознаёт `12852b18` как HEAD
кодовой ветки на момент вынесения вердикта итерации 2 (`43aae48c` →
`12852b18`, ровно два файла). Инкрементальный diff восстановлен как
`git diff 12852b18 HEAD` (HEAD = `cab8f1af`):

```
README.md                                  | 92 +++++++++++++++++++-----------
docs/codebase-map.md                       |  2 +-
tasks/01M1P9RJVYHTAC087J4B2CAR44/REVIEW.md | 63 ++++++++++++++++++++
tests/test_review_package.py               | 13 ++++-
```

`README.md` — не эта задача: коммит `50ed714e` («оператор: README —
состояние после A7…») уже есть в `main` (`git log --oneline main | grep
50ed714e`) — обычная подтяжка main, слитая мерж-коммитом `cab8f1af`
(`git show --stat cab8f1af` — сам мерж трогает только `README.md`,
`*.py` не затронут, регенерация карты не требовалась). `REVIEW.md` —
собственный артефакт, не код. Единственная функциональная правка со
времени вердикта итерации 2 — `tests/test_review_package.py` (докстринги
R1-F2, разбор ниже), плюс регенерация карты этим же коммитом
(`docs/codebase-map.md`, только `built_at_sha`, что не дефект —
review-checklist). Функциональный код фичи (`fixation.py`, `store.py`,
`review.py`, `alerts.py`, `runner.py`) с итерации 2 не менялся —
требования 1-3 (AC-1..AC-6) остаются подтверждены итерациями 1-2 и
регрессионным прогоном полного набора (см. «Проверено исполнением»).

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Код (`fixation.py`, `store.py`) не менялся с итерации 2. AC-1/AC-4 подтверждены полным набором тестов и приёмочными AC-1/AC-4 (зелёные). |
| 2 | OK | Код (`review.py::review_package`, ветка `elif iteration > 1`) не менялся, читал и сверен адресно (`orchestrator/review.py:296-306`) — текст называет причину («базу сравнения… определить не удалось… sha в записи не распознан»), diff остаётся полным к `config.MAIN_BRANCH`. AC-5 зелёный. |
| 3 | OK | Код (`alerts.py`, `runner.py::cmd_run`) не менялся, читал адресно (`orchestrator/alerts.py:89-106`, `orchestrator/runner.py:260-267`) — `kind=warning` заводится/закрывается по `not_collected`/`iteration>1`, как в PLAN. AC-6 зелёный. |
| 4 | OK | R1-F1 (конфликт-маркеры карты) закрыт итерацией 2 (принято, ниже без повтора). R1-F2 (докстринги `Ловит мутацию:` у `PreviousVerdictShaTest`) теперь ДЕЙСТВИТЕЛЬНО закрыт — `git diff 12852b18 cab8f1af -- tests/test_review_package.py` показывает докстринги обоих тестов дополнены литеральной заявкой `Ловит мутацию: …`, дословно совпадающей с формулировками, которые сама эта же цепочка ревью предлагала в итерации 1/2. AC-7 (`test_ac7_full_suite_green.py`, помечен `skip`) — легальный частый случай: критерий покрыт ДЕЙСТВУЮЩИМ CI-автогейтом (`fsm_autogate.py::_autogate_conditions`, прогон полного `tests/` на каждый approve), обоснование в докстринге теста явное, не «сложно замокать». |

## Замечания

Нет — 0 blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | docs/codebase-map.md:2-6 | Незакрытые git-конфликт-маркеры во frontmatter карты, закоммичены на HEAD ветки | Сломанный YAML/markdown уходил в main при мерже | Закрыто итерацией 2 (см. историю файла); не переоцениваю повторно |
| R1-F2 | accepted | tests/test_review_package.py:1277-1301 | Два теста `PreviousVerdictShaTest` без литеральной заявки `Ловит мутацию: …` в докстринге | Нарушение конвенции test-authoring — следующий ревьювер не может механически сверить тест с заявленной мутацией | Подтверждено этой итерацией: `git diff 12852b18 cab8f1af -- tests/test_review_package.py` — оба докстринга несут `Ловит мутацию: …` с конкретным сценарием и наблюдаемым свойством (не пересказ имени метода), формулировки совпадают с предложенными в итерации 1/2. `python3 -m unittest tests.test_review_package` — зелёный, полный набор — зелёный (1481/1481) |

## Вердикт
approved — оба замечания реестра закрыты (R1-F1 подтверждён итерацией 2,
R1-F2 подтверждён этой итерацией чтением diff и прогоном тестов), новых
дефектов не найдено. Логика фичи (требования 1-4, AC-1..AC-7) не менялась
с итерации 1/2 и остаётся верной; правки этой итерации — докстринги
тестов, регенерация карты и штатная подтяжка main, ничего в зоне задачи
не сломано.

## Проверено исполнением
- `git diff 00e32aaf...task/01m1p9rjvyhtac087j4b2car44-inkrementalnyy-diff-revyu-posl` — «Invalid symmetric difference expression», base sha не резолвится (тот же класс, что описан в SPEC этой задачи); diff восстановлен вручную через `git log --oneline -15 <ветка>` и текст REVIEW.md итерации 2 (опознан HEAD `12852b18` на момент того вердикта).
- `git diff --stat 12852b18 cab8f1af` и `git diff 12852b18 cab8f1af -- tests/test_review_package.py` — единственная функциональная правка с итерации 2: докстринги `Ловит мутацию:` добавлены в оба теста `PreviousVerdictShaTest`, логика/ассерты не менялись.
- `git show --stat 50ed714e` + `git log --oneline main | grep 50ed714e` — README.md-правка уже в main, это подтяжка, не работа задачи; `git show --stat cab8f1af` — сам мерж трогает только README.md.
- `git diff --stat main...task/01m1p9rjvyhtac087j4b2car44-inkrementalnyy-diff-revyu-posl` — полный diff ветки к main: 20 файлов, ровно в границах, заявленных PLAN («Влияние на систему») — fixation.py/store.py/review.py/alerts.py/runner.py/codebase-map.md/tasks/.../tests — ничего лишнего (README.md там нет, как и ожидалось).
- `python3 -m unittest discover -s tests` — 1481 тестов, все зелёные (269.15s, полный прогон в переднем плане/фоне с ожиданием завершения).
- `python3 -m unittest discover -s tasks/01M1P9RJVYHTAC087J4B2CAR44/acceptance_tests` — 8 тестов (AC-1..AC-7), все зелёные (1.63s).
- `python3 scripts/guard.py tasks/01M1P9RJVYHTAC087J4B2CAR44/SPEC.md tasks/01M1P9RJVYHTAC087J4B2CAR44/PLAN.md tasks/01M1P9RJVYHTAC087J4B2CAR44/REVIEW.md` — GUARD: ок (3 файлов).
- `grep -rn '<<<<<<<\|=======\|>>>>>>>' docs/codebase-map.md` — пусто; `python3 scripts/codebase_map.py` (регенерация для сверки) — diff только по строке `built_at_sha`, остальное содержимое совпадает, откачено `git checkout -- docs/codebase-map.md`.
- `grep -c "def test_"` / `grep -c "Ловит мутацию"` по изменённым этой задачей тестовым файлам (`tests/test_diff_not_collected_alerts.py` — 7/7, `tests/test_git_fixation.py` — 1 новый тест из 39, несёт заявку, `tests/test_review_package.py` — 2 изменённых теста, оба несут заявку) — конвенция test-authoring соблюдена по каждому новому/изменённому тесту, не выборочно.
- Читал адресно (без этого нельзя было проверить конкретные замечания): `orchestrator/review.py` (previous_verdict_sha, review_package, package_note — сверка регэкспа `код=` и текста причины отсутствия базы требованию 2/AC-5), `orchestrator/alerts.py` (KINDS, raise_diff_not_collected_alert, close_diff_not_collected_alerts), `orchestrator/runner.py:260-267` (интеграция алерта в cmd_run), `tasks/.../acceptance_tests/test_ac5_missing_base_falls_back_with_a_reason.py` и `test_ac7_full_suite_green.py` (обоснование AC-7 skip).

## Предложения системе
- Тот же класс наблюдения, что уже зафиксирован в итерации 2 (и подтверждён предыдущими: T082/T087): base sha инкрементального diff (`00e32aaf2c15059ffb72260275b29b9d2b53e8fe`) снова не резолвился в этом же пакете — предыдущий вердикт (iteration 2) был закоммичен только на task-ветке в составе прерванного WIP-чекпоинта оркестратора (`e610b41c`), а не через обычный проход review-шага, из-за чего журнал фиксации записал не тот sha, который реально стал HEAD на момент вердикта. Отдельного действия не требует (задача сама чинит источник проблемы), но иллюстрирует, что регрессия воспроизводима даже когда «код уже исправлен» — временное окно между исправлением и тем, что журнал начинает нести `код=`, у самой этой задачи тоже было.
