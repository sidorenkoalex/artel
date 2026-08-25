---
task: T030
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 2
---

# REVIEW: Команда version

## Фаза A (гейт плана)

PLAN.md покрывает все 7 требований SPEC таблицей соответствия, шаги —
проверяемые единицы (модуль+тесты / регистрация в CLI / прогон
проверок), подход соответствует паттерну `doctor.cmd_doctor`/
`budget.cmd_budget`. Расширение условия показа `__doc__` на `-h`/
`--help` обосновано и не конфликтует с существующими тестами (проверено
grep'ом по `tests/` — упоминаний `-h`/`--help` в существующих тестах нет).
План сам по себе не конфликтует с конвенциями. Единственная проблема —
в исполнении шага 3 (регенерация карты), см. блокер ниже.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (команда `version`) | OK | `orchestrator/artel.py:171` — зарегистрирована в таблице команд |
| 2 (пин CLI из конфига) | OK | `orchestrator/version.py:10,14` — `config.CLI_VERSION_PIN` |
| 3 (фактическая версия, способ как в `doctor.cli_version()`) | OK | `orchestrator/version.py:11` — прямой вызов `doctor.cli_version()`, второй regex не заведён |
| 4 (версия схемы) | OK | `orchestrator/version.py:16` — `guard.SUPPORTED_SCHEMA_VERSION` |
| 5 (пометка при расхождении) | OK | `orchestrator/version.py:17-19` — печатается только когда `installed is not None and installed != pin` |
| 6 (не меняет конфиг/БД/git) | OK | Только чтение констант и `subprocess.run` внутри `doctor.cli_version()`; юнит- и приёмочные тесты подтверждают отсутствие побочных эффектов снимком файлов и git-статусом |
| 7 (видна в `--help`) | OK | `orchestrator/artel.py:81,117,147` |

AC-1..AC-7 — все 12 тестов (`tests/test_version.py` + `tasks/T030/acceptance_tests/test_version.py`) прогнаны локально, зелёные. Полный набор юнит-тестов (`python3 -m unittest discover -s tests`) — 569 тестов, 3 падения в `test_multitarget.RoleEnvTest`, но они падают и на `main` (проверено переключением ветки) — окружение (реальная git-identity пульта вместо ожидаемой в тесте), к T030 не относится.

## Замечания

- **blocker** — `docs/codebase-map.md:2` (built_at_sha) — коммит
  `a0fdfa2` меняет `orchestrator/artel.py` и `orchestrator/version.py`
  и добавляет `tests/test_version.py`, но регенерированная карта в этом
  же коммите зафиксировала `built_at_sha: 15cc67583eeb...` — sha
  РОДИТЕЛЬСКОГО коммита (T030 приёмочные тесты), а не текущего. Это
  структурно ожидаемо (коммит не может нести свой собственный sha —
  тот же довод в `.github/workflows/ci.yml:66-68`), но именно поэтому
  джоб `codebase-map` на main после мержа СРАВНИВАЕТ `built_at_sha` с
  HEAD и ищет изменения `orchestrator/*.py`/`scripts/*.py`/`tests/*.py`
  между ними: я прогнал этот же diff вручную —
  `git diff --name-only 15cc67583eeb... HEAD -- 'orchestrator/*.py' 'scripts/*.py' 'tests/*.py'`
  — возвращает ровно `orchestrator/artel.py`, `orchestrator/version.py`,
  `tests/test_version.py`. После мержа в main джоб «Карта кодовой базы
  генерируется и свежа» упадёт с «карта стухла» — тем же классом, что
  уже дважды ловили после T028 (`656eec2`) и T029 (`eb3368a`), и именно
  этот повтор `eb3368a` пытался предотвратить правилом в скиле
  разработчика («регенерируй тем же коммитом»). Правило по факту не
  достигает цели: регенерация «тем же коммитом» структурно не может
  дать актуальный `built_at_sha` для *этого же* коммита. PLAN.md
  прямо ссылается на это правило («иначе CI-джоб свежести красит main
  после мержа») — заявленная цель шага 3 не достигнута.
  Предложение: перед мержем добавить отдельный коммит, регенерирующий
  `docs/codebase-map.md` уже ПОСЛЕ `a0fdfa2` (тогда `built_at_sha` =
  `a0fdfa2`, и diff до HEAD этого коммита по *.py путям окажется
  пустым) — тем же приёмом, что `656eec2` и `eb3368a`. Точечно
  правку кода это не касается, только `docs/codebase-map.md`.

## Вердикт

changes_requested — единственное замечание: добавить коммит, регенерирующий `docs/codebase-map.md` так, чтобы `built_at_sha` совпадал с последним коммитом, меняющим `orchestrator/*.py`/`scripts/*.py`/`tests/*.py` (см. блокер выше). Реализация команды `version` и её тесты — без замечаний, все AC покрыты и проверены прогоном.
