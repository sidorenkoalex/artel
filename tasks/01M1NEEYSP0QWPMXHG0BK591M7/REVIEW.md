---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Предупреждение при чужом живом lease (pause, release)

## Фаза A: проверка плана
- Покрытие требований (таблица PLAN.md) — полное, все 5 требований отображены на шаги, требование 5 корректно закрыто как «не входит».
- Шаги 1-4 — проверяемые единицы разумного размера, не микрооперации.
- Подход (единый хелпер `lease.foreign_live_lease`/`warn_foreign_live`, вызов в начале тел `cmd_pause`/`cmd_release`) не конфликтует с конвенциями; переиспользует существующие `store.lease_row`/`liveness._age_seconds`/`liveness._pid_alive` вместо копипасты.
- Раздел «Эскалация» в PLAN.md касается инфраструктурного гейта `in_dev -> review` (лок `acceptance_tests/` с `__pycache__`), не содержания SPEC/кода — задача уже находится в review, значит гейт пройден (видимо, штатным `amend-tests`); к предмету этого ревью (соответствие SPEC, корректность кода) отношения не имеет, поэтому не разбирается отдельно как блокер ревью.
- Замечание по плану: раздел «Подход» описывает поведение адресуемости pid чужого lease («печатать нужно только то, что действительно проверено с этой машины... чужой host с непроверяемым pid — не «адресуем»»), но фактическая реализация в `orchestrator/lease.py::foreign_live_lease` НЕ проверяет hostname вовсе — см. «Замечания» ниже (R1-F1). План и код разошлись.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (предупреждение до выполнения, pause/release, держатель+возраст heartbeat) | Частично | Для lease на ЭТОМ host — реализовано и подтверждено приёмочными тестами AC-1/AC-3. Для lease на ДРУГОМ host (легитимный, документированный в этой же кодовой базе случай — `hostname` в `leases`, `cmd_pause_now`, `catalog._lease_holder_suffix`) поведение сломано в обе стороны — см. R1-F1. Роль/шаг не печатаются вовсе (SPEC: «если известны») — см. R1-F2. |
| 2 (свой/мёртвый-протухший lease — без предупреждения) | OK | `foreign_live_lease` корректно возвращает `None` для своей сессии и для мёртвого/протухшего чужого lease на ОДНОМ host — покрыто AC-4/AC-5/юнит-тестами. |
| 3 (дубль в журнал тем же API, identity держателя) | OK | `store.journal(..., session_id=row["session_id"])` — держатель, не текущая сессия; AC-6 подтверждает. |
| 4 (read-only команды не предупреждают) | OK | `status`/`log`/`show`/`doctor` не тронуты, AC-7 зелёные. |
| 5 (approve/reject/budget/kill/answer не меняются) | OK | Файлы `fsm.py`/`budget.py`/`cleanup.py`/`answer.py` в диффе не фигурируют (`git diff --stat` подтверждён). |

## Замечания

- major — `orchestrator/lease.py:128-149` (`foreign_live_lease`) — функция проверяет адресуемость pid БЕЗ сравнения `row["hostname"]` с `socket.gethostname()`, хотя PLAN.md («Подход») явно описывает намерение обратное («чужой host с непроверяемым pid — не адресуем, предупреждения не будет») и все три существующих места этой же кодовой базы, решающие ровно ту же задачу («живой ли чужой lease»), это различение делают: `orchestrator/catalog.py:194-197` (`_lease_holder_suffix`), `orchestrator/lease.py:73` (`acquire`), `orchestrator/pause.py:190-192` (`cmd_pause_now`, третий путь деградации — явный отказ именно ПОТОМУ, что «lease адресует процесс на ДРУГОМ host»). Воспроизведено (вставка `leases` для `T001` вручную, `foreign_live_lease(conn, "T001", "sess-current")`):
  - lease на чужом host с `pid=os.getpid()` (совпадает с реально работающим ЛОКАЛЬНЫМ процессом чисто по числу) → функция возвращает строку как «живую» — предупреждение напечатается для lease, чью реальную живость мы физически не проверяли (ложное срабатывание, коллизия pid между хостами вероятна на практике: контейнеры/systemd часто дают низкие pid).
  - lease на чужом host со свежим heartbeat и pid, не совпадающим ни с одним локальным процессом (типичный случай ДЕЙСТВИТЕЛЬНО работающей на другой машине сессии) → функция возвращает `None` — предупреждение НЕ печатается, хотя это ровно тот сценарий из «Контекст» SPEC (другая сессия активно ведёт задачу), причём для межмашинного случая even более вероятный, чем однохостовый.
  Итог: для кросс-хостового lease (штатный, поддерживаемый режим этой системы — колонка `hostname` существует именно для него) предупреждение почти всегда МОЛЧИТ там, где обязано сработать, и может ложно сработать в редких коллизиях pid. Предложение: перед `liveness._pid_alive` в `foreign_live_lease` проверять `row["hostname"] == socket.gethostname()`; при несовпадении host — решить явно (тем же приёмом, что уже есть в кодовой базе: либо трактовать как «жив» по умолчанию, как `_lease_holder_suffix`/`acquire`, либо как отдельный кейс с честной пометкой «host не проверен», как `cmd_pause_now`) — но не звать `_pid_alive` вслепую по чужому pid.

- minor — `orchestrator/lease.py:143-149` (`warn_foreign_live`) — предупреждение не включает роль/шаг задачи, хотя SPEC требование 1 и AC-1/AC-3 просят «роль/шаг — если известны», а эта информация тривиально доступна в месте вызова (`orchestrator/pause.py::cmd_pause` уже читает `t = store.get_task(...)`, `runner.step_role(t)` уже используется в этом же модуле — `orchestrator/pause.py:193`). PLAN.md не обсуждает это упущение как сознательное решение (в отличие от вопроса адресуемости pid, которому посвящён отдельный абзац) — похоже на пропущенную часть требования, а не на осознанный трейд-офф. AC-1/AC-3 это не проверяют (текст «если известны» условный), поэтому не blocker, но стоит закрыть класс: добавить роль/шаг в `detail`, когда `runner.step_role(t)` возвращает не `None`.

- minor — `orchestrator/lease.py:151-152` — формулировка предупреждения грамматически сбоит: «вмешательство продолжится, но она может быть активно работать над задачей» («может быть активно работать» — рассогласование, нужно «может активно работать» или «может быть, активно работает»). Косметика, но текст читает Оператор в реальном инциденте — стоит поправить.

- major — тесты/test-authoring.md, скил review-checklist требует докстринг с заявкой «Ловит мутацию: …» у КАЖДОГО нового или изменённого теста; ни один из новых юнит-тестов этой задачи такой докстринг не несёт (в отличие от приёмочных тестов `tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/*.py`, где заявки аккуратно оформлены). Класс целиком:
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
  Без докстринга проверить заявленную мутацию нельзя — часть этих тестов (например, `test_foreign_live_lease_returns_the_row`, будь у него докстринг «Ловит мутацию: hostname не сверяется») сама поймала бы дефект R1-F1 выше, если бы автор действительно прогнал её через мысленный мутационный тест по этому сценарию — судя по отсутствию заявок, этого не произошло. Предложение: добавить докстринг с явной заявкой к каждому из 13 методов.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/lease.py:128-149 | `foreign_live_lease` не сверяет `hostname` перед `liveness._pid_alive`, расходится с PLAN.md и с тремя аналогичными местами кодовой базы | для кросс-хостового живого lease предупреждение почти всегда не печатается (или ложно печатается при коллизии pid) — сломан ровно тот сценарий, ради которого написан SPEC | добавить проверку `hostname == socket.gethostname()` перед `_pid_alive`, явно решить трактовку непроверяемого чужого host (по аналогии с `_lease_holder_suffix`/`acquire` или `cmd_pause_now`) |
| R1-F2 | open | orchestrator/lease.py:143-149 | предупреждение не включает роль/шаг задачи, хотя SPEC просит «если известны», а `runner.step_role(t)` доступен в месте вызова | AC не проверяет — не blocker, но требование выполнено не полностью | добавить роль/шаг в `detail`, когда `runner.step_role(t)` не `None`, либо явно задокументировать в PLAN, почему это сознательно опущено |
| R1-F3 | open | orchestrator/lease.py:151-152 | грамматическая ошибка в тексте предупреждения («может быть активно работать») | косметика в тексте, который видит Оператор в реальном инциденте | поправить формулировку |
| R1-F4 | open | tests/test_lease.py:342-409, tests/test_pause.py:109-127, tests/test_release.py:130-149 | 13 новых юнит-тестов без докстринга «Ловит мутацию: …» (требование review-checklist/test-authoring.md) | заявленное свойство теста не проверяемо ревью, риск теста-пустышки не обнаруживается заранее (см. связь с R1-F1) | добавить докстринг с конкретной заявкой к каждому перечисленному методу |

## Вердикт
changes_requested — исправить R1-F1 (major, ломает основной сценарий SPEC для кросс-хостовых lease) и R1-F4 (major, отсутствие обязательных докстрингов у новых юнит-тестов); R1-F2/R1-F3 — minor, на усмотрение разработчика, но лучше закрыть в этой же итерации заодно.

## Проверено исполнением
- `git checkout -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/` — перед прогоном тестов рабочее дерево этого воркера потеряло каталог задачи (все файлы `deleted` без staged), восстановлено из HEAD тем же приёмом, что описан в PLAN.md «Контекст» (известный симптом, см. память `feedback_task_dir_deletion_recovery`).
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/ -q` — 18 passed.
- `python3 -m pytest tests/ -q` — 1365 passed, 417 subtests passed, 0 ошибок (полный набор, регрессий нет).
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md` — ок.
- `python3 scripts/codebase_map.py` (регенерация в рабочем дереве) — диф с текущим HEAD только в строке `built_at_sha`, содержимое совпадает; откачено обратно `git checkout -- docs/codebase-map.md` (карта в ветке актуальна).
- Воспроизведение R1-F1 отдельным скриптом: вставка lease-строки с чужим `hostname` и pid, совпадающим с реальным локальным процессом (`os.getpid()`), даёт `foreign_live_lease(...)` → строка (ложно «жив»); та же строка с чужим `hostname` и заведомо непроверяемым локально pid (`999999`) при свежем heartbeat даёт `foreign_live_lease(...)` → `None` (предупреждение молчит там, где обязано сработать).

## Предложения системе
