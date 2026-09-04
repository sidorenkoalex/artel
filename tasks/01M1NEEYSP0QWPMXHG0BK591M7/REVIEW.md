---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: review
author_role: reviewer
status: changes_requested
iteration: 2
schema_version: 3
---

# REVIEW: Предупреждение при чужом живом lease (pause, release)

## Фаза A: проверка плана
- Покрытие требований (таблица PLAN.md) — полное, все 5 требований отображены на шаги, требование 5 корректно закрыто как «не входит». Без изменений с итерации 1.
- Шаги 1-4 — проверяемые единицы разумного размера, не микрооперации.
- `git diff fc6b2ebf HEAD -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md` — единственное изменение PLAN.md с итерации 1 это добавление разделов «Предложения системе»/«Эскалация» про инфраструктурный гейт лока `acceptance_tests/` (`__pycache__` в автокоммите test_author). Разделы «Подход»/«Шаги» — без изменений ни на символ.
- Из этого следует: замечание R1-F1 по плану («Подход» описывает намеренную проверку hostname, код её не делает — план и код разошлись) остаётся в силе без изменений — см. «Замечания» и реестр ниже.
- Раздел «Эскалация» в PLAN.md — инфраструктурный гейт `in_dev -> review`, не содержание SPEC/кода; задача снова в review, значит гейт пройден (видимо, `amend-tests`); к предмету ревью не относится, отдельно не разбирается (как и в итерации 1).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (предупреждение до выполнения, pause/release, держатель+возраст heartbeat) | Частично | Без изменений с итерации 1. Для lease на ЭТОМ host — реализовано, AC-1/AC-3 зелёные. Для lease на ДРУГОМ host (легитимный случай — колонка `hostname`, `cmd_pause_now`, `catalog._lease_holder_suffix`) поведение сломано в обе стороны — R1-F1, воспроизведено повторно на текущем коде (см. «Проверено исполнением»). Роль/шаг не печатаются — R1-F2, тоже без изменений. |
| 2 (свой/мёртвый-протухший lease — без предупреждения) | OK | Без изменений, `foreign_live_lease` корректна для однохостового случая, AC-4/AC-5 зелёные. |
| 3 (дубль в журнал тем же API, identity держателя) | OK | Без изменений, AC-6 зелёный. |
| 4 (read-only команды не предупреждают) | OK | Без изменений, AC-7 зелёный. |
| 5 (approve/reject/budget/kill/answer не меняются) | OK | Без изменений — эти файлы вне диффа. |

## Замечания

Код (`orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `tests/test_lease.py`, `tests/test_pause.py`, `tests/test_release.py`) байт-в-байт идентичен коммиту `fc6b2ebf`, рассмотренному в итерации 1 (`git diff fc6b2ebf HEAD -- <эти файлы>` — пусто). С прошлой итерации не было ни одного коммита, трогающего эти файлы (`git log --oneline fc6b2ebf..HEAD -- <эти файлы>` — пусто). Ни одна запись реестра итерации 1 не размечена разработчиком `fixed`/`rejected` — по правилу review-checklist это не «доделано неправильно», а «не тронуто вовсе», поэтому все четыре переносятся как `open` без изменения содержания:

- major — `orchestrator/lease.py:128-150` (`foreign_live_lease`) — функция по-прежнему не сравнивает `row["hostname"]` с `socket.gethostname()` перед `liveness._pid_alive`, хотя PLAN.md («Подход») продолжает декларировать обратное намерение, а три других места той же кодовой базы (`orchestrator/catalog.py:194-197` `_lease_holder_suffix`, `orchestrator/lease.py:73` `acquire`, `orchestrator/pause.py:190-192` `cmd_pause_now`) делают это различение. Повторно воспроизведено на текущем коде: lease с чужим `hostname` и `pid=os.getpid()` (случайное числовое совпадение с реальным локальным процессом) → `foreign_live_lease` возвращает строку («ложно жив»); тот же lease с чужим `hostname` и типичным непроверяемым локально pid (реальный межхостовый случай) → возвращает `None` (предупреждение молчит там, где обязано сработать — ровно сценарий из «Контекст» SPEC). Предложение прежнее: сравнивать `row["hostname"]` перед вызовом `_pid_alive`, явно решить трактовку непроверяемого чужого host.
- minor — `orchestrator/lease.py:153-173` (`warn_foreign_live`) — по-прежнему не включает роль/шаг задачи, хотя SPEC требование 1 просит «если известны», а `runner.step_role(t)` уже используется в том же модуле-вызывателе (`orchestrator/pause.py:193`, внутри `cmd_pause_now`) — тривиально доступно и в `cmd_pause`/`cmd_release`. Не blocker (AC формулировка условная), но требование выполнено не полностью.
- minor — `orchestrator/lease.py:168-170` — формулировка предупреждения по-прежнему грамматически сбоит: «вмешательство продолжится, но она может быть активно работать над задачей». Текст читает Оператор в реальном инциденте.
- major — ни один из 13 новых/изменённых юнит-тестов по-прежнему не несёт докстринг с заявкой «Ловит мутацию: …» (skills/test-authoring.md, review-checklist требование 3), подтверждено чтением файлов напрямую (не только grep — `tests/test_lease.py:342-414` прочитаны целиком, докстрингов нет ни у одного метода класса `ForeignLiveLeaseTest`):
  - `tests/test_lease.py:342` `test_no_lease_returns_none`
  - `tests/test_lease.py:346` `test_own_live_lease_returns_none`
  - `tests/test_lease.py:353` `test_foreign_live_lease_returns_the_row`
  - `tests/test_lease.py:362` `test_foreign_stale_heartbeat_returns_none`
  - `tests/test_lease.py:370` `test_foreign_dead_pid_returns_none`
  - `tests/test_lease.py:377` `test_warn_foreign_live_prints_holder_and_heartbeat_age`
  - `tests/test_lease.py:387` `test_warn_foreign_live_journals_with_holder_session_id`
  - `tests/test_lease.py:399` `test_warn_own_live_lease_prints_nothing_and_does_not_journal`
  - `tests/test_lease.py:409` `test_warn_no_lease_prints_nothing_and_does_not_journal`
  - `tests/test_pause.py:109` `test_pause_warns_on_foreign_live_lease`
  - `tests/test_pause.py:118` `test_pause_journals_the_warning_as_an_extra_entry`
  - `tests/test_release.py:130` `test_release_warns_on_foreign_live_lease`
  - `tests/test_release.py:139` `test_release_journals_the_warning_as_an_extra_entry`
  Заявка «Ловит мутацию: hostname не сверяется» на `test_foreign_live_lease_returns_the_row` сама поймала бы R1-F1/R2-F1 — её отсутствие коррелирует с тем, что дефект не был замечен автором до ревью. Предложение прежнее: докстринг с явной заявкой к каждому из 13 методов.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/lease.py:128-150 | `foreign_live_lease` не сверяет `hostname` перед `liveness._pid_alive` — не исправлено с итерации 1, код идентичен | для кросс-хостового живого lease предупреждение почти всегда не печатается (или ложно печатается при коллизии pid) — сломан основной сценарий SPEC | сравнить `row["hostname"] == socket.gethostname()` перед `_pid_alive`, явно решить трактовку непроверяемого чужого host |
| R1-F2 | open | orchestrator/lease.py:153-173 | предупреждение не включает роль/шаг задачи — не исправлено | требование 1 («если известны») выполнено не полностью | добавить роль/шаг в `detail`, когда `runner.step_role(t)` не `None` |
| R1-F3 | open | orchestrator/lease.py:168-170 | грамматическая ошибка «может быть активно работать» — не исправлено | косметика в тексте для Оператора в реальном инциденте | поправить формулировку |
| R1-F4 | open | tests/test_lease.py:342-414, tests/test_pause.py:109-127, tests/test_release.py:130-149 | 13 юнит-тестов без докстринга «Ловит мутацию: …» — не исправлено | заявленное свойство теста не проверяемо ревью заранее | добавить докстринг с конкретной заявкой к каждому методу |

## Вердикт
changes_requested — с итерации 1 в код и тесты (`orchestrator/lease.py`, `orchestrator/pause.py`, `orchestrator/release.py`, `tests/test_lease.py`, `tests/test_pause.py`, `tests/test_release.py`) не внесено ни одного изменения: все четыре замечания (R1-F1..R1-F4) остаются в исходном виде, две из них (R1-F1, R1-F4) — major. Между итерациями PLAN.md получил только раздел «Эскалация» про несвязанный инфраструктурный гейт лока `acceptance_tests/`; похоже, что задача вернулась в review через разрешение этого гейта (вероятно `amend-tests` Оператора), а не через работу разработчика над замечаниями ревью — присутствие задачи на этом шаге не означает, что R1-F1..R1-F4 обработаны. Нужно исправить R1-F1 (major) и добавить докстринги R1-F4 (major) как минимум; R1-F2/R1-F3 minor, но дёшевы и стоит закрыть в этой же итерации.

## Проверено исполнением
- `git checkout -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/` — рабочее дерево этого запуска снова показало каталог задачи как `deleted` без staged-изменений при старте; восстановлено из HEAD (известный симптом, память `feedback_task_dir_deletion_recovery`).
- `git diff fc6b2ebf HEAD -- orchestrator/lease.py orchestrator/pause.py orchestrator/release.py tests/test_lease.py tests/test_pause.py tests/test_release.py` — пусто: код байт-в-байт идентичен коммиту, рассмотренному в итерации 1.
- `git log --oneline fc6b2ebf..HEAD -- <те же файлы>` — пусто: ни одного коммита с итерации 1.
- Повторное воспроизведение R1-F1 отдельным unittest-модулем (`tests/sandbox.TmpRootTest`, временно помещён в `tests/`, удалён после прогона): lease с чужим `hostname` и `pid=os.getpid()` → `foreign_live_lease` возвращает строку («ложно жив»); тот же lease с чужим `hostname` и pid `999999` (типичный непроверяемый межхостовый случай) → `foreign_live_lease` возвращает `None` (молчит там, где обязано сработать). Результат идентичен воспроизведению итерации 1.
- Чтение `tests/test_lease.py:342-414` целиком — докстрингов «Ловит мутацию» нет ни у одного из 9 методов `ForeignLiveLeaseTest`; `grep -n "Ловит мутацию" tests/test_pause.py tests/test_release.py tests/test_lease.py` — без совпадений.
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/ -q` — 18 passed.
- `python3 -m pytest tests/ -q` — 1365 passed, 417 subtests passed, 0 ошибок, 0 регрессов.
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md` — ок.
- `python3 scripts/codebase_map.py` (регенерация в рабочем дереве) — диф с текущим HEAD только в строке `built_at_sha`, содержимое совпадает; откачено обратно `git checkout -- docs/codebase-map.md`.

## Предложения системе
Задача вернулась на review-шаг (iteration 2) без единого коммита, адресующего замечания итерации 1 — единственное изменение между итерациями это разрешение несвязанного инфраструктурного гейта лока `acceptance_tests/` (PLAN.md «Эскалация»). Похоже, переход `in_dev -> review` не требует, чтобы предыдущий `changes_requested`-вердикт ревью был фактически обработан разработчиком — только чтобы прошли механические гейты (лок тестов, guard). Если так — стоит проверить, не пропускает ли FSM (`orchestrator/fsm_advance.py`) содержательную проверку «код с прошлой итерации ревью изменился», рискуя повторными пустыми циклами review без прогресса.
