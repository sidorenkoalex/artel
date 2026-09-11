---
task: 01M28NX0M2WTVC38XVN75N01XD
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: kill при живом цикле — отказ с подсказкой stop, ликвидация только с --yes

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (kill без `--yes` при живом lease отказывает, ничего не меняет) | OK | `cleanup._live_cycle_holder`/`_live_cycle_role`/`_refuse_live_cycle` (orchestrator/cleanup.py:141-207); отказ вызывается ДО `lease.run_locked`, подтверждено тестами AC-1 |
| 2 (kill `--yes` при живом lease — прежнее полное поведение + журнал) | OK | orchestrator/cleanup.py:225-231; AC-2 тесты зелёные |
| 3 (kill без флага при отсутствии живого lease — как раньше) | OK | `live_role is None` пропускает guard целиком; AC-3 тесты зелёные |
| 4 (подсказка «дальше:» называет обе команды на гейте/ожидании зоны) | OK | `config._BOTH_COMMANDS` дописан в `AUTO_STOP["spec_gate"/"acceptance"/"merge_gate"/"escalated"]` и `AUTO_STOP_ZONE_WAIT`; AC-4/AC-5 тесты зелёные |
| 5 (`docs/operator-session.md` несёт абзац «stop против kill») | OK | docs/operator-session.md:172-181; AC-6 тест зелёный |
| 6 (`tests/test_kill_cleanup.py`/`tests/test_detached_cycle.py` зелёные без правки) | OK | `git diff 6d65b9f0..HEAD --stat` этих файлов пуст (не тронуты вовсе); оба набора зелёные при прогоне |

## Замечания

(пусто — единственное замечание прошлой итерации закрыто, см. реестр)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_kill_live_cycle_refusal.py:39,46,54,62,71,94,108,139,150 | новые тестовые методы (9 из 9) не несли собственного докстринга с заявкой «Ловит мутацию: …» — у части классов заявки не было вовсе, у остальных она была общая на класс, не на сценарий | ревьювер будущих правок не мог сверить тест с явной заявкой о том, какую порчу кода он обязан поймать | добавлен каждому из 9 методов собственный докстринг «Ловит мутацию: …»; перечитан построчно — каждый описывает конкретную порчу (какая из трёх проверок `_live_cycle_holder` убрана/инвертирована, `_live_cycle_role` отказывает безусловно, диспетчер `--yes` проглатывает/подставляет флаг по умолчанию) и наблюдаемое красное значение, не пересказывает имя метода — заявка правдоподобна и проверяема, замечание закрыто |

## Вердикт

approved — единственное замечание итерации 1 (R1-F1) исправлено и
принято. Все требования и AC SPEC покрыты и подтверждены зелёными
тестами (юнит + приёмочные), защищённые тесты `tests/
test_kill_cleanup.py`/`tests/test_detached_cycle.py` не тронуты вовсе
(diff по ним пуст), пометка `manual` на AC-7 в `test_scope_markers.py`
легальна класса «ci-covered» («зелёные» покрыто CI-джобом на каждый
пуш; «без правки утверждений» — свойство диффа, проверено ревьювером
вручную и подтверждено пустым `git diff` по обоим файлам). Побочных
изменений вне зоны задачи нет: `docs/backlog.md` и
`docs/codebase-map.md` меняются исключительно подтяжкой main (чужие
копилка-коммиты плюс легальная регенерация карты — расхождение только
в строке `built_at_sha`, перепроверено локальной регенерацией).

## Проверено исполнением

- `python3 -m unittest tests.test_kill_live_cycle_refusal
  tests.test_kill_cleanup tests.test_detached_cycle -v` — 54 теста,
  все зелёные.
- `python3 -m unittest
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac1_ac2_ac3_kill_confirmation
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac4_ac5_auto_stop_hint_names_stop_and_kill
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_ac6_operator_session_doc_has_stop_vs_kill_paragraph
  -v` — 9 тестов (AC-1..AC-6), все зелёные.
- `python3 -m unittest
  tasks.01M28NX0M2WTVC38XVN75N01XD.acceptance_tests.test_scope_markers
  -v` — 0 тестов (файл несёт только пометку AC-7 manual, зелёный с
  рождения по докстрингу файла).
- Инкрементальный diff пакета пустой (база `52a9026a` совпала с HEAD —
  известный класс из review-checklist, T087): восстановил фактическую
  базу вручную по `git log --oneline` (baseline задачи — `6d65b9f0`,
  до первого коммита разработчика `9fcc2ed3`) и прочитал полный
  `git diff 6d65b9f0..HEAD` построчно по всем затронутым файлам
  (`orchestrator/cleanup.py`, `orchestrator/artel.py`,
  `orchestrator/config.py`, `docs/operator-session.md`,
  `tests/test_kill_live_cycle_refusal.py`, `docs/backlog.md`,
  `docs/codebase-map.md`) — код не читал бегло по диффу из пакета
  (он был пуст), читал файл вручную.
- `python3 scripts/codebase_map.py` на рабочей копии — diff с
  зафиксированной `docs/codebase-map.md` только в строке
  `built_at_sha` (законное отставание); рабочее дерево возвращено
  `git checkout -- docs/codebase-map.md` после проверки, изменений не
  оставлено.
- `git diff 6d65b9f0..HEAD --stat -- tests/test_kill_cleanup.py
  tests/test_detached_cycle.py` — пусто, файлы не тронуты вовсе
  (требование 6/AC-7).

## Предложения системе

- Инкрементальный diff ревью-пакета этой итерации снова совпал с
  текущим HEAD вместо фактического коммита предыдущего вердикта (тот
  же класс, что T087, review-checklist уже предупреждает) — в этой
  задаче совпадение возникло из-за «подтяжки main» ПОСЛЕ коммита
  R1-F1 (`52a9026a` — сама подтяжка, отдельная от `15ec6324` — фикса).
  Обошёл вручную (`git log --oneline`), но это третий известный случай
  класса (T082, T087, теперь 01M28NX0M2) — стоит рассмотреть, чтобы
  пакет вычислял базу по коммиту, где REVIEW.md реально получил
  предыдущий `status`, а не по последнему коммиту с id задачи в
  сообщении.
