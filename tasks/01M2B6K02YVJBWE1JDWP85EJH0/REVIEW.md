---
task: 01M2B6K02YVJBWE1JDWP85EJH0
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Канарейка на целевом sha — pin-update без зависимости от кода пина

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (canary --k <N> [--sha <sha>], main_sha = целевой sha) | OK | `canary._resolve_target_sha`/`_sha_arg`/`_ephemeral_clone(target_sha)`/`_run_one_task` — покрыто AC-1..AC-4, проверено приёмочными тестами реальным git. |
| 2 (pin-update ищет прогон на истории `<sha>`) | OK | Гейт `pin.cmd_pin_update` не менялся (уже искал по переданному `sha`, см. докстринг pin.py) — регресс к сравнению с пином проверен `PinUpdateAcceptsGreenOnTargetShaTest` (AC-5). |
| 3 (doctor.check_canary_trigger — тот же источник sha) | OK | `check_canary_trigger` переведён на `doctor.fetch_origin_main_sha()` (тот же примитив, что и `check_pin_unpushed`, race-free `gitcmd.fetch_ref_sha` под капотом — проверил `orchestrator/gitcmd.py:466` `fetch_head_sha` → `fetch_ref_sha`). Текст называет sha (AC-7). |
| 4 (отчёт несёт sha и пометку происхождения) | OK | `_sha_label` — приоритет «код пина» подтверждён тестом на совпадение обоих условий разом (AC-8). |
| 5 (существующая планка не ослаблена) | OK | `tests/test_canary.py`/`test_pin.py`/`test_doctor.py`/`test_new_argv_parsing.py` — только новые тесты и минимальные правки существующих сигнатур/сетапа под новый источник sha (см. «Проверено исполнением»), удалённых/смягчённых assert нет. |

## Замечания

<Пустой раздел — 0 blocker/major/minor, требующих правки кода этой итерации.>

## Реестр замечаний

<Пусто — предыдущих итераций нет (это первая), новых записей в этой не заведено.>

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_canary tests.test_pin tests.test_doctor tests.test_new_argv_parsing -v` — 236 тестов, все зелёные (включая новые `ResolveTargetShaTest`, `ShaLabelTest`, `EphemeralCloneConfigRemapTest.test_checkout_uses_target_sha`, `PinUpdateRefusalMessageTest`, `CanaryTriggerCheckTest` на реальном bare `origin`).
- `python3 -m unittest discover -s tasks/01M2B6K02YVJBWE1JDWP85EJH0/acceptance_tests -p "test_*.py" -v` — 14 тестов (AC-1..AC-8), все зелёные, реальный git (не моки git-команд).
- `python3 scripts/codebase_map.py --check` — без расхождений (карта регенерирована этим же коммитом, docs/codebase-map.md).
- Прочитан код `orchestrator/canary.py` (`_resolve_target_sha`, `_sha_label`, `_ephemeral_clone`, `_run_one_task`, `cmd_canary`), `orchestrator/pin.py::cmd_pin_update`, `orchestrator/doctor/canary_pool.py::check_canary_trigger`, `orchestrator/gitcmd.py` (`fetch_ref_sha`/`fetch_head_sha`), `orchestrator/doctor/root_pin.py::fetch_origin_main_sha` — подтверждена цепочка примитивов (не осталось старого FETCH_HEAD-based пути) и корректность приоритета пометок `_sha_label`.
- Сверены защищённые пути (`.github/`, `gates.yaml`, `roles.yaml`, `templates/`, `skills/`) — не затронуты (`git diff --stat` пакета).
- Проверена ссылка на «инвариант 35» в докстринге `check_canary_trigger` — подтверждена по `docs/invariants.md:65`: инвариант ограничен `tests/**/*.py`, doctor в проде не затрагивает; утверждение в докстринге корректно.
- CI коммита 5f7955f8 — зелёный (7 проверок, по заголовку задачи).

## Предложения системе

- `orchestrator/canary.py::_resolve_target_sha` (AC-2) — явный `--sha`, ссылающийся на объект, присутствующий только на `origin`, но ещё не в локальной объектной базе `config.ROOT`, падает понятной, но недокументированной ошибкой checkout из `_ephemeral_clone` (canary.py:567-574): AC-2 запрещает `fetch` в этой ветке. Не блокер — единственный задокументированный источник значения `--sha` (подсказка `pin-update`/`doctor`, AC-6/AC-7) уже гарантирует локальное наличие объекта, т.к. `pin.cmd_pin_update` сам делает `git fetch origin <MAIN_BRANCH>` до вычисления возраста (pin.py:50). Стоит одной строкой отметить это ограничение в докстринге `_sha_arg`/usage `artel.py:688`, чтобы прямой ручной вызов `--sha` на нефетчнутом sha не удивлял оператора неочевидным отказом.
