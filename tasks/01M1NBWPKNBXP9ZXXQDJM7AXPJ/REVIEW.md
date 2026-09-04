---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 3
---

# REVIEW: Сверка свежести ветки против main артели на origin

## Фаза A: гейт плана

PLAN.md на ветке задачи (21028 байт, sha256=367b9f39…d990518 —
совпадает с ревью-пакетом байт-в-байт) добавил шаг 6 (описание правки
R2-F1/R3-F1 по ANSWER-2) поверх шагов 1-5 предыдущих итераций; таблица
покрытия требований 1-5 → шаги 1-3 не тронута и остаётся полной. Шаг 6
— единица размера MR (два точечных замечания одного ревью-цикла), не
микрооперация и не «сделать всё». Подход не меняется и не конфликтует
с архитектурой. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (сверка/подтяжка против origin, не пина) | OK | `fsm._origin_main_sha`/`_pull_main_or_escalate` (fsm.py:130-316); AC-1/AC-4 зелёные. |
| 2 (гейт `merge_gate` ждёт CI циклом на пути "fresh" после push) | OK | `fsm_merge_gate.py` — `("wait", branch)` вместо разового опроса; AC-5/AC-7 зелёные. |
| 3 (расхождение пина не влияет ни на что, кроме `doctor`) | OK | Ранний `return "fresh"` при вырожденной `_origin_main_sha` (fsm.py:269-273) до `commits_behind`/`merge`; `doctor.py`/`pin.py` diff'ом не задеты. |
| 4 (существующие тесты зелёные, расширены не переписаны) | OK | R2-F1 закрыт: все 11 новых/изменённых тестовых методов этой ветки несут докстринг-заявку `Ловит мутацию: …`, каждая называет конкретную правдоподобную мутацию и наблюдаемое расхождение (проверено построчным чтением всех 11, см. «Проверено исполнением»). 1391/1391 `tests/`, 92/92 целевых, 9/9 приёмочных — зелёные. |
| 5 (remote/репозиторий из конфигурации target'а) | OK | `_origin_main_source` (fsm.py:130-162); AC-10 (`TargetSourcedRemoteTest`) зелёный. R3-F1 закрыт: `_auto_resolve_map_conflict` принимает `source_branch` параметром, `source`/`source_branch` в `_pull_main_or_escalate` вычисляются до первой точки использования, литерал `config.MAIN_BRANCH` в четырёх пользовательских/журнальных сообщениях (fsm.py:116,278,300,308-309) заменён на `source_branch` — остаточных вхождений в тексте эскалаций/коммитов не осталось (`grep -n "MAIN_BRANCH" orchestrator/fsm.py` — только строка 157, self-target литерал по дизайну, и строка 268, честный fallback на случай `source is None`, обе легитимны). |

## Замечания

(пусто — 0 blocker/major/minor)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R2-F1 | accepted | tests/test_branch_freshness_gate.py и ещё 4 файла | Ни один новый/изменённый тест этой ветки не нёс докстринг-заявку `Ловит мутацию: …` | Ревьювер не мог сверить чувствительность теста с конкретной заявленной мутацией (Фаза B п.3) | Проверено: коммит `a5daedbe` добавил строку `Ловит мутацию: …` во все 11 перечисленных методов; каждая заявка сверена построчно с телом теста (мутация правдоподобна, наблюдаемое свойство соответствует реальным `assert*` теста, не пересказывает имя метода) — принято |
| R3-F1 | accepted | orchestrator/fsm.py:116,278,300,308-309 | Три эскалационных сообщения и коммит авторазрешения конфликта карты несли литерал `config.MAIN_BRANCH` вместо `source_branch` | Вводящий в заблуждение текст эскалации/журнала для гипотетического внешнего target'а | Проверено: коммит `a5daedbe` — `_auto_resolve_map_conflict` принимает `source_branch` параметром (используется в commit-сообщении, fsm.py:116); `source`/`source_branch` в `_pull_main_or_escalate` вычисляются сразу после `target_name`, до `_origin_main_sha`; литерал заменён во всех четырёх местах; единственный вызывающий код (`_pull_main_or_escalate`) обновлён тем же коммитом — принято |

R1-F1 и R1-F2 (итерация 1) уже `accepted` с итерации 3 — не повторяю
(кумулятивное правило, восстановимы из git-истории файла). Реестр
закрыт целиком: записей со статусом, отличным от `accepted`, не
осталось — гейт `review -> verifying` пропустит этот вердикт.

## Вердикт

approved — 0 blocker/major/minor. Оба замечания предыдущей итерации
(R2-F1 major, R3-F1 minor) исправлены по существу и проверены прямым
чтением кода/тестов, не только доверием к пометке `fixed` разработчика.

## Проверено исполнением

- На входе рабочее дерево несло непроиндексированные удаления всего
  `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` (тот же прецедент, что в
  предыдущих итерациях) — восстановлено `git checkout --
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/`, `git status` после — чисто.
- `git log --oneline --all -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/REVIEW.md`
  — найден фактический коммит фикса `a5daedbe` («правка R2-F1/R3-F1
  ANSWER-2»), следующий за реальным коммитом reviewer-вердикта итерации
  3 (`15077afc`, содержимое байт-в-байт совпадает с REVIEW.md
  «прошлая итерация» ревью-пакета). Sha «предыдущего вердикта» из
  описи пакета (`00e32aaf...`) снова не существует в репозитории
  (`git cat-file -t` — fatal) — тот же класс проблемы, что и в
  итерации 3; обойдено тем же приёмом (поиск по `git log --all`).
- `git show a5daedbe --stat` — коммит-фикс трогает ровно
  `orchestrator/fsm.py`, 5 тестовых файлов (`tests/
  test_branch_freshness_gate.py`, `tests/test_ci_status_kind_gate.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py`, `tests/
  test_invariants.py`, `tests/test_merge_gate_ci_wait.py`) и артефакты
  задачи (PLAN.md/REVIEW.md) — ничего сверх ANSWER-2 («Реестр закрыть
  по леджеру, ничего сверх»).
- `git show a5daedbe -- orchestrator/fsm.py` прочитан целиком —
  `_auto_resolve_map_conflict(conn, task_id, wt_path, source_branch)`,
  вычисление `source`/`source_branch` поднято перед `base =
  _origin_main_sha(...)` (fsm.py:267-269, до раннего `return "fresh"`
  — не нарушает R1-F1: `_origin_main_source` — чистое чтение
  конфигурации/константы, без git-вызовов, безопасно вызывать до
  проверки `base`), все четыре места (116, 282→278, 300, 308-309)
  используют `source_branch`.
- `git show a5daedbe -- tests/...` прочитан целиком — все 11 методов
  из прежнего R2-F1 несут добавленную строку `Ловит мутацию: …`;
  выборочно сверены тела трёх методов (`test_advance_pulls_main_and_
  advances_when_acceptance_green`, `test_freshness_check_never_
  defaults_base_to_local_pin`, `test_advance_treats_origin_fetch_
  failure_as_fresh`) построчным чтением `tests/
  test_branch_freshness_gate.py:250-400` — заявленная мутация в
  докстринге в каждом случае соответствует реальным
  `assertIn`/`assertNotIn`/`assert_not_called` теста.
- `grep -n "MAIN_BRANCH" orchestrator/fsm.py orchestrator/
  fsm_merge_gate.py` — в `fsm.py` из user/journal-текста литерал
  полностью выведен (остались только строка 157 — self-target
  литерал по дизайну ANSWER-1, и строка 268 — fallback на случай
  `source is None`, обе не относятся к R3-F1); `fsm_merge_gate.py`
  вне зоны правки (её собственный `_origin_main_sha` — про main
  артели, не тронут этой задачей).
- `grep -n "_auto_resolve_map_conflict" tests/
  test_fsm_map_conflict_autoresolve.py orchestrator/*.py` — тест не
  зовёт функцию напрямую (только через `_pull_main_or_escalate`),
  единственный вызывающий код обновлён под новую сигнатуру тем же
  коммитом — смена параметра не сломала этот файл без его правки, как
  и заявляет PLAN.md.
- `python3 -m unittest tests.test_branch_freshness_gate
  tests.test_fsm_map_conflict_autoresolve tests.test_gitcmd_branch_reads
  tests.test_merge_gate_ci_wait tests.test_ci_status_kind_gate
  tests.test_invariants tests.test_fsm_merge_gate_done_snapshot -v` —
  92 теста, `OK`.
- `python3 -m unittest discover -s
  tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests -p "test_ac*.py" -v`
  — 9 тестов (AC-1..AC-9), `OK`.
- `python3 -m unittest discover -s tests -q` (лог сохранён в файл,
  чтобы не потерять итоговую строку под шумом print'ов тестов) — `Ran
  1391 tests in 171.031s / OK`, exit 0.
- `python3 scripts/codebase_map.py` (регенерация) — diff с
  закоммиченным `docs/codebase-map.md` отличается ТОЛЬКО строкой
  `built_at_sha`; рабочее дерево возвращено `git checkout --
  docs/codebase-map.md`.
- `git diff a5daedbe 469518a7 -- tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/` —
  пусто: между коммитом фикса и текущим HEAD ветки задачи (после
  промежуточного глючного автокоммита `102e763c`, стёршего ~11934
  строк по 141 файлам, включая чужие задачи, и восстановившего их же
  следующим мержем main `469518a7` — тот же класс дефекта, что уже
  отмечен в «Предложения системе» прошлой итерации, здесь
  самоисправился, финальное состояние идентично коммиту фикса) task-
  директория и реализация не изменились.
- Хеши `SPEC.md` (8838 байт, sha256=01120c78…56ca0315) и `PLAN.md`
  (21028 байт, sha256=367b9f39…d990518) на рабочем дереве совпадают с
  описью ревью-пакета байт-в-байт.

## Предложения системе

(пусто — наблюдение о регрессии автокоммита уже зафиксировано в
REVIEW.md итерации 3; в этом заходе она не повторилась, глюк
`102e763c`/`469518a7` тот же класс, но самоисправился следующим же
коммитом до попадания в ревью)
