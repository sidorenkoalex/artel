---
task: T101
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 3
---

# REVIEW: Fingerprint окружения в журнале шага

## Соответствие SPEC

Пакет ревью даёт инкрементальный diff `d424d58...HEAD` (единственная
строка — `built_at_sha` в `docs/codebase-map.md`) и подаёт его как diff
«от sha предыдущего вердикта». Это неверный ориентир: реальный коммит
предыдущего approved-вердикта (итерация 2) — `1e39d9a`
(`git log --oneline -- tasks/T101/REVIEW.md`), а `d424d58` — более
поздний коммит-фикс Оператора, который пакет по ошибке принял за
«вердиктный». Это тот же класс, что уже описан в
`review-checklist`/T087 («пустой или подозрительно короткий
инкрементальный diff — повод перепроверить вручную»): между `1e39d9a`
и `HEAD` в реальности три коммита, а не один (`9578aa9` мерж
`origin/main`, несущий T094/M1; `d424d58` фикс Оператором фикстур
приёмочных; `0c8b991` регенерация карты). Всё ниже проверено по
фактическому объёму изменений (`git diff --name-only
$(git merge-base main HEAD) HEAD` и `git log 1e39d9a..HEAD`), а не по
пакетному diff'у.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `orchestrator/agent_log.py::environment_fingerprint()` не изменилась мержем — та же реализация, что в итерации 2 (сверено чтением файла на HEAD). |
| 2 (AC-2) | OK | `_tool_version_text` не изменилась: таймаут 5с, `OSError`/`TimeoutExpired` → `"недоступно: <причина>"`, без исключения наружу. |
| 3 (AC-6) | OK | Модульный кэш `_environment_fingerprint_cache` не изменился. |
| 4а (AC-4) | OK | `orchestrator/runner.py:503-505,627-629` — fingerprint по-прежнему в `detail` `"agent run started"`/`"agent run finished"`; мерж T094 добавил в файл лишь 4 строки в стороне (`git diff --stat 1e39d9a...HEAD -- orchestrator/runner.py`), мест T101 не задел. |
| 4б (AC-5) | OK | `orchestrator/fsm_advance.py:170-217` — мерж с T094 конфликтовал именно в этом файле (материализация `acc_tdir` из артефактной ветки для внешнего target, SPEC T094 требование 10); конфликт разрешён корректно — код T101 (`fingerprint = agent_log.environment_fingerprint()` + попадание в оба исхода, red/green) не потерян и не задвоен, перепроверено чтением фрагмента целиком. |
| 5 (AC-7) | OK | `orchestrator/catalog.py::cmd_log` (номера строк сдвинулись мержем, поведение то же) печатает `detail` без урезания. |
| 6 (AC-8) | OK | `git diff --name-only $(git merge-base main HEAD) HEAD` (база — точка расхождения ветки, не текущий кончик `main`, тем же приёмом, что и локед-тест) даёт: `orchestrator/agent_log.py`, `orchestrator/runner.py`, `orchestrator/fsm_advance.py`, `docs/codebase-map.md`, `tasks/T101/*`, `tests/test_acceptance_tests_flow.py`, `tests/test_agent_log.py`, `tests/test_step_cost.py` — ни одного из запрещённых путей (`store.py`, `catalog.py`, `brief.py`, `fixation.py`, `doctor.py`, `cleanup.py`, `prune.py`, `config.py`). Остальные ~80 файлов из diff `1e39d9a...HEAD` (`store.py`, `catalog.py`, `acceptance.py`, `fsm.py`, `checkpoint.py` и т.д.) принесены мержем `main` (T094/M1, смержена в main отдельно и одобрена своим ревью) — это ожидаемая подтяжка, не собственные коммиты T101, зона не нарушена. |
| 7 (AC-9) | OK | `test_ac9_coverage_manifest.py` зелёный, состав требуемых сценариев не менялся. |
| AC-10 | OK | Полный `tests/` — 1224 теста (было 1209 в итерации 2, прирост от мержа T094), все зелёные. |

## Замечания

(нет новых замечаний по коду — три коммита после итерации 2 это: мерж
`main`/T094-M1 с корректно разрешённым конфликтом в
`orchestrator/fsm_advance.py`; механическая правка Оператора двух
файлов-обвязки приёмочных тестов T101 под ULID (`_driver_agent_step.py`,
`_sandbox.py` — `TASK = "T001"` хардкод заменён на возврат
`catalog.cmd_new(...)`/`capture_new_task_id(...)`, тот же класс фикса,
что `T094: чиню фикстуры test_agent_log/test_step_cost под ULID`; это
обвязка песочницы, не сам тест — покрытие не ослаблено, `git show
d424d58` проверен построчно); и регенерация `docs/codebase-map.md`
(только `built_at_sha`, содержимое не изменилось — перепроверено
локальным прогоном `scripts/codebase_map.py`).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:204 (`_pull_main_or_escalate`) | Третий вызов `acceptance.run`, вне буквальной зоны AC-5/AC-8 | Диагностическая цель требования 1 не достигается в сценарии подтяжки main — задокументированное ограничение | Принято ревьювером в итерации 2, статус не менялся. Перепроверено в этой итерации: `fsm.py:204` по-прежнему не тронут, `acceptance.run` вызывается по-прежнему ровно в двух местах кодовой базы (`grep -n "acceptance\.run(" orchestrator/*.py` → `fsm_advance.py:193`, `fsm.py:204`). |

## Вердикт
approved — все требования SPEC выполняются на фактическом HEAD ветки
(AC-1..AC-10), зона соблюдена (проверено правильной базой сравнения,
`merge-base main HEAD`, а не подставным diff'ом из пакета), полный
набор тестов зелёный (1224/1224). Три коммита после итерации 2 не
добавляют нового кода в зону T101 сверх подтяжки уже одобренной ветки
T094 и мелкой мех. правки обвязки приёмочных, необходимой, чтобы ветка
вообще собиралась после этой подтяжки.

## Проверено исполнением
- `git log --oneline -- tasks/T101/REVIEW.md` — найден реальный коммит
  предыдущего вердикта (`1e39d9a`, итерация 2, approved); диапазон,
  данный в пакете (`d424d58...HEAD`), оказался короче реального на два
  содержательных коммита (мерж main + фикс фикстур Оператором).
- `git log --oneline 1e39d9a..HEAD` и `git diff --stat 1e39d9a...HEAD`
  — три коммита, 88 изменённых файлов путей.
- `git merge-base main HEAD` + `git diff --name-only <база> HEAD` —
  собственная зона T101: `orchestrator/agent_log.py`,
  `orchestrator/runner.py`, `orchestrator/fsm_advance.py`,
  `docs/codebase-map.md`, `tasks/T101/*`,
  `tests/test_acceptance_tests_flow.py`, `tests/test_agent_log.py`,
  `tests/test_step_cost.py` — без запрещённых путей (AC-8).
- Чтение `orchestrator/fsm_advance.py:170-217` (разрешённый конфликт
  мержа) и `orchestrator/runner.py:498-505,620-632` — fingerprint
  на месте в обоих журнальных событиях агентного шага и в обоих
  исходах прогона приёмки, код по сути не изменился с итерации 2.
- `git show d424d58 -- tasks/T101/acceptance_tests/_driver_agent_step.py tasks/T101/acceptance_tests/_sandbox.py` — фикс Оператора мех.: id теперь берётся из возврата `cmd_new`/`capture_new_task_id`, тест-обвязка, не тестовые сценарии.
- `python3 -m unittest tasks.T101.acceptance_tests.test_ac10_full_suite_stays_green tasks.T101.acceptance_tests.test_ac1_ac4_ac6_agent_step_available tasks.T101.acceptance_tests.test_ac2_agent_step_missing_and_timeout tasks.T101.acceptance_tests.test_ac3_agent_step_outcome_unaffected tasks.T101.acceptance_tests.test_ac5_acceptance_run_fingerprint tasks.T101.acceptance_tests.test_ac7_log_command_shows_fingerprint tasks.T101.acceptance_tests.test_ac8_change_zone_restricted tasks.T101.acceptance_tests.test_ac9_coverage_manifest -v` — 15 тестов, все зелёные (Ran 15 tests, OK; включая AC-8 zone restriction на фактическом текущем HEAD).
- `python3 -m unittest discover -s tests` — Ran 1224 tests, OK (AC-10; прирост с 1209 в итерации 2 — тесты T094, принесённые мержем main).
- `python3 -m scripts.guard tasks/T101/SPEC.md tasks/T101/PLAN.md tasks/T101/REVIEW.md` — «GUARD: ок (3 файлов)».
- `grep -n "acceptance\.run(" orchestrator/*.py` — по-прежнему ровно два вызова (`fsm_advance.py:193`, `fsm.py:204`); R1-F1 остаётся корректно описанным.
- Локальный прогон `python3 scripts/codebase_map.py` и `git diff docs/codebase-map.md` — отличие только в строке `built_at_sha` (карта содержательно свежая); изменение отменено (`git checkout -- docs/codebase-map.md`), рабочее дерево чистое.

## Предложения системе
- Сборка «инкрементального diff-пакета» для ревью в этой итерации
  взяла не тот sha «предыдущего вердикта» — не коммит, где
  `REVIEW.md` реально получил свой предыдущий `status: approved`
  (`1e39d9a`), а более поздний коммит Оператора (`d424d58`), из-за
  чего показанный diff пропустил мерж main и фикс фикстур целиком.
  Класс уже описан в `review-checklist`/T087, но конкретный вариант
  здесь другой: взятый sha лежит МЕЖДУ настоящим вердиктом и HEAD (а
  не совпадает с HEAD и не предшествует настоящему вердикту). Стоит
  чинить сборку пакета так, чтобы sha «предыдущего вердикта» находился
  по последнему коммиту, менявшему `status` в `REVIEW.md` на нужное
  значение для завершённой итерации (например
  `git log -S'status: approved' -- tasks/<id>/REVIEW.md`), а не
  эвристикой, уязвимой к промежуточным коммитам между вердиктом и HEAD.
