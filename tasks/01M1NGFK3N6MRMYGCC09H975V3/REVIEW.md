---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 4
---

# REVIEW: Канарейка v2 (часть 2): привязка пина к зелёной канарейке, триггер doctor, откат пина

## Служебное замечание к ревью-пакету

Пакет заявляет диапазон «от sha предыдущего вердикта (`8c8d6456`) до
HEAD» и показывает пустой diff — HEAD ветки САМ равен этому sha, кода с
момента вердикта итерации 3 (`approved`, тем же коммитом `8c8d6456`)
никто не менял. Это не «нечего ревьюировать»: предыдущая попытка сдать
шаг была отклонена явно («вердикт REVIEW.md итерации 3 уже учтён — жду
новый прогон ревьювера с iteration: 4»), то есть система требует
повторного прогона ревьювера над ТЕМ ЖЕ кодом — судя по коммиту
`d38820bc` («зелёная задача на merge_gate устаревает молча — нужен гейт
свежести перед мержем»), это и есть тот самый гейт свежести: код не
менялся, но раз ревью уже было один раз «использовано», нужен новый
вердикт поверх актуального HEAD.

Раз пакет не даёт диффа для проверки, содержимое подтверждено прямым
чтением кода и прогоном тестов (см. «Проверено исполнением»), с особым
вниманием к тому, что коммит `8c8d6456` сам по себе — merge-коммит
подтяжки origin/main с конфликтами ИМЕННО в зонах этой задачи
(`orchestrator/artel.py`, `orchestrator/canary.py`, `orchestrator/
doctor.py`, `docs/codebase-map.md` — см. сообщение коммита). Это
единственный код-коммит этой задачи после `cd852e84` (HEAD итерации 3
на момент её вердикта) — разрешение этого конфликта и есть фактический
предмет итерации 4, не «ничего не изменилось».

## Фаза A: гейт плана

`PLAN.md` дополнен разделом «Возврат — подтяжка после 01M1TKP269 и
разреза doctor», подробно объясняющим причину возврата (ветка отстала
от main на 445+ коммитов, три зоны задачи независимо переписаны) и три
содержательные правки, потребовавшиеся при разрешении конфликта:
разрез `doctor.py` → пакет `orchestrator/doctor/` (перенос
`check_canary_trigger` в `canary_pool.py`), адаптация verdict-логики
`_run_one_task` под ADR-0015 (`_drive_task` больше не возвращает
маркер исхода — `verifying` теперь проходится синтетически,
`_pass_verifying`, не убивает задачу) и, как следствие, отказ от
критерия «дошла до merge_gate/verifying» в пользу уже смерженного
`_needs_diagnostics`. Раздел — проверяемая единица разумного размера
(один merge-коммит, три точечные правки под конфликт, не «сделать всё
разом»). Подход не конфликтует с конвенциями: адаптация под изменения
main, не пересмотр требований SPEC по существу (раздел явно это
утверждает и я проверил построчно — см. ниже). Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`pin-update` отказывает без свежего зелёного прогона) | OK | `orchestrator/pin.py` этим merge-коммитом не тронут вовсе (`git diff cd852e84..8c8d6456 -- orchestrator/pin.py` — пусто); гейт (строки 37-51) на месте, читает `config.CANARY_MAX_MERGES_SINCE_GREEN` и `canary.merges_since_last_green_run`. |
| 2 (`doctor` — триггер `kind=trigger` по тому же порогу) | OK | Пережил разрез `doctor.py` → пакет: `check_canary_trigger` перенесён дословно в `orchestrator/doctor/canary_pool.py:133-183`, зарегистрирован в `orchestrator/doctor/__init__.py:127-128` и вызван в `orchestrator/doctor/cli.py:53`; арифметика и порог не изменились. |
| 3 (`pin --to <sha>`/`pin --to` — откат, main не трогается) | OK | `orchestrator/artel.py` — `"pin": lambda: _cmd_pin(rest)` (диспетчер) и докстринг `pin --to [<sha>]` сохранены сквозь merge (диф файла — только несвязанные добавления `venv-sync`/`note`/переставленный `verifying`, не задевающие `pin`). |
| 4 (каждый откат — отдельная запись журнала) | OK | `pin.cmd_pin_to`/`_refuse_rollback` не тронуты merge-коммитом (пин.py вне диффа). |

### Разбор merge-коммита `8c8d6456` (единственный код-коммит этой итерации)

Проверил построчно каждую из зон задачи:

- `orchestrator/pin.py`, `orchestrator/store.py` (схема/`insert_canary_run`) —
  диффом merge-коммита не задеты вовсе (`git diff cd852e84..8c8d6456 --
  orchestrator/pin.py` пуст; `store.py` содержит только несвязанные
  изменения main — колонки `main_sha`/`verdict` и `green_canary_runs`/
  `latest_green_canary_run` на месте).
- `orchestrator/doctor.py` → `orchestrator/doctor/` — конфликт
  «modify/delete», PLAN.md документирует разрешение (взят пакет
  `origin/main` целиком, `check_canary_trigger` перенесён в
  `canary_pool.py`). Подтвердил чтением: функция на месте
  (`canary_pool.py:133`), тот же текст алерта для дедупа (REVIEW.md
  итерации 1, R1-F2 — «пора перепрогнать: artel.py canary --k 1»),
  тот же порог `config.CANARY_MAX_MERGES_SINCE_GREEN`, вызов
  `doctor.alerts.raise_alert(conn, None, "trigger", "canary", ...)`
  дедупится через `store.open_alert_exists` (`alerts.py:104`).
- `orchestrator/canary.py` — три хунка конфликта. Проверил вручную
  (`git show 2126e6ab`/чтение файла целиком): `_drive_task` вернулась к
  сигнатуре `-> None` (ADR-0015 переставил `verifying` перед
  ревьювером — `state == "verifying"` теперь ведёт через
  `_pass_verifying`, не убивает задачу); verdict в `_run_one_task`
  (canary.py:1001) вычисляется как `"green" if not
  _needs_diagnostics(normal_outcome, mismatch) else "red"`, где
  `normal_outcome = metrics["kill_note"] == "штатно"` (canary.py:984) —
  штатный kill сегодня достижим только на `merge_gate`
  (`_kill_at_verifying` недостижима из `_drive_task`, оставлена
  нетронутой только ради чужой залоченной планки
  `tasks/01M1SC3Y20YBTTJVQDJBF2NDQW/acceptance_tests/
  test_canary_report_kill_reason.py`, что PLAN.md прямо оговаривает).
  Это эквивалентно исходному определению ANSWER-1 п.2 («зелёный», если
  задача дошла до merge_gate/verifying и убита штатно ИМЕННО там, и
  маркер эскалации совпал), просто выражено через уже существующую в
  main пару `_kill_outcome_note`/`_needs_diagnostics`, а не через
  собственный маркер возврата — не ослабление и не пересмотр критерия
  по существу.
- `docs/codebase-map.md` — перегенерирован тем же merge-коммитом
  (`git show 8c8d6456 --stat -- docs/codebase-map.md` — 362/121 строк).
  Перезапустил `python3 scripts/codebase_map.py` — диф только в строке
  `built_at_sha` (не дефект, конвенция), откатил (`git checkout --
  docs/codebase-map.md`).
- Защищённые пути (`.github/`, `gates.yaml`, `roles.yaml`, `templates/`,
  `skills/`) — ни один коммит этой задачи (`77378ee2`, `9c55cd47`,
  `2126e6ab`) их не касается (`git show --stat <sha> -- .github
  gates.yaml roles.yaml templates skills` — пусто для всех трёх); диф
  `.github/workflows/ci.yml` в `git show 8c8d6456 --stat` — часть
  merge-контента origin/main (чужая, уже смерженная работа), не
  авторская правка этой задачи.

## Замечания

Нет — 0 blocker/major/minor. Единственный код-коммит этой итерации —
merge-коммит подтяжки main; разрешение конфликтов в зонах задачи
(`canary.py`, `doctor.py`→пакет, `artel.py`) сохраняет контракт SPEC
1-4/AC-1..AC-7 дословно, подтверждено построчным чтением и прогоном
целевых юнит- и приёмочных тестов.

## Реестр замечаний

Все записи итераций 1-3 (`R1-F1`..`R1-F4`) — в статусе `accepted` по
состоянию на итерацию 3 (см. `REVIEW.md` итерации 3, раздел «Реестр
замечаний»: «Новых замечаний в этой итерации нет», реестр закрыт
целиком) — не повторяю, восстановимы из git-истории файла. Новых
замечаний в этой итерации (4) нет.

## Вердикт

approved — 0 blocker/major. Единственный код-коммит этой итерации
(`8c8d6456`, merge подтяжки origin/main с конфликтами в зонах задачи)
проверен построчно: `pin.py`/`store.py` не задеты вовсе; разрез
`doctor.py`→пакет корректно перенёс `check_canary_trigger` со всей
арифметикой и дедупом; адаптация verdict-логики `canary.py` под
ADR-0015 эквивалентна исходному критерию ANSWER-1 п.2, не ослабляет и
не пересматривает его. Требования 1-4/AC-1..AC-7 SPEC — реализованы
полностью, подтверждено прогоном целевых юнит-тестов и полной
приёмочной планки задачи (все зелёные). Защищённые пути этой задачей
не затронуты. `codebase-map.md` актуален с точностью до `built_at_sha`.

## Проверено исполнением

- `git rev-parse HEAD` = `8c8d645652da443b2773e376d9173c4f2abb71bf`; сверено с sha из истории отказа advance — совпадает.
- `git log --oneline cd852e84..8c8d6456` — единственный код-коммит этой итерации, merge подтяжки origin/main (56 промежуточных коммитов main, ни один не авторства этой задачи).
- `git diff cd852e84..8c8d6456 -- orchestrator/pin.py` — пусто. `-- orchestrator/doctor.py orchestrator/artel.py orchestrator/store.py` — прочитаны построчно (см. «Разбор merge-коммита» выше).
- `git show --stat 77378ee2 -- .github gates.yaml roles.yaml templates skills`, то же для `9c55cd47`/`2126e6ab` — пусто для всех трёх (защищённые пути не затронуты авторскими коммитами задачи).
- `python3 scripts/codebase_map.py` + `git diff --stat -- docs/codebase-map.md` — расхождение только в `built_at_sha`; отменено `git checkout -- docs/codebase-map.md`, в дереве не осталось.
- `python3 -m unittest tests.test_pin tests.test_canary tests.test_doctor tests.test_gitcmd_branch_reads tests.test_gitcmd_check_ignore -v` — 239 тестов, все `ok` (включая `DiffNamesTest::test_lists_changed_paths`, ранее красный по ANSWER-2, — зелёный).
- `python3 -m unittest discover -s tasks/01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests -p 'test_*.py' -v` — 15 тестов, все `ok` (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7 — по несколько сценариев каждый; AC-8 — легальный `skip`, ci-covered, обоснование не изменилось с итерации 1).
- `python3 scripts/guard.py tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md tasks/01M1NGFK3N6MRMYGCC09H975V3/PLAN.md tasks/01M1NGFK3N6MRMYGCC09H975V3/ANSWER-1.md tasks/01M1NGFK3N6MRMYGCC09H975V3/ANSWER-2.md tasks/01M1NGFK3N6MRMYGCC09H975V3/REVIEW.md` — «GUARD: ок (5 файлов)».
- Статус CI коммита `8c8d6456`, заявленный пакетом, — зелёный (14 проверок); полный набор `tests/` в этом шаге не гонял (решение Оператора 05.09, review-checklist) — CI уже подтвердил его на этом же sha.

## Предложения системе

- Пятое+ независимое подтверждение класса «якорь пакета ревью не sha
  коммита автокоммита ПРЕДЫДУЩЕГО REVIEW.md» (T082, T087, и трижды в
  этом же батче задач — см. «Предложения системе» REVIEW.md итераций 2
  и 3 этой задачи) — здесь другое проявление того же корня: якорь
  (`8c8d6456`) совпал с текущим HEAD, диф пуст, хотя предмет итерации
  (разрешение конфликта merge-коммита) реален и требовал ручной
  реконструкции через `git log`/`git diff` по конкретным файлам зоны
  задачи. Стоит явно документировать в брифе ревьювера, что «пустой
  инкрементальный diff» — не сигнал «нечего проверять», когда история
  отказа advance явно требует нового прогона.
