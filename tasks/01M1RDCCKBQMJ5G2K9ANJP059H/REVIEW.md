---
task: 01M1RDCCKBQMJ5G2K9ANJP059H
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: объявленный стек пульта, часть 2 — CI на объявленной версии Python

## Фаза A: проверка плана

1. Покрытие требований (таблица PLAN.md «Покрытие требований») — все 4
   требования SPEC покрыты шагами 1–4; сверено построчно с текстом
   требований — соответствует.
2. Шаги 1–4 — проверяемые единицы разумного размера (константа+функция
   / скрипт / тесты / диф-приложение), не микрооперации и не «сделать
   всё разом».
3. Подход не конфликтует с конвенциями: расширение зон на
   `orchestrator/stack.py` документировано разделом «## Расширение
   зон» со ссылкой на мандат ANSWER-1 (вариант (a) обоих вопросов) —
   соответствует требованию гейта зон; протокол защищённого пути
   `.github/workflows/ci.yml` соблюдён (диф-приложение в PLAN.md, не
   прямая правка в кодовой ветке — подтверждено `git status`/diff, файл
   не менялся).

Отдельных замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (setup-python из манифеста, без литерала версии) | OK | Диф-приложение PLAN.md добавляет `actions/setup-python@v5` с версией из `python3 scripts/stack_ci.py` перед каждым python3-джобом (`guard`, `python`, `codebase-map`); литералов версии в ci.yml нет. |
| 2 (матрица min/current для `tests.test_invariants`) | OK | В джобе `python` второй `setup-python@v5` (версия из `scripts/stack_ci.py --min`) перед отдельным запуском `python3 -m unittest tests.test_invariants -v`; обе версии — из манифеста, не литералом. |
| 3 (ci.yml — защищённый путь, минимальный диф, логика в scripts/stack_ci.py) | OK | Диф в ci.yml — только вызов `python3 scripts/stack_ci.py[--min]` + `setup-python`; вся логика чтения `orchestrator/stack.py` и форматирования — в новом `scripts/stack_ci.py`. |
| 4 (stack_ci.py печатает версию, тест сравнивает с манифестом, набор `tests/` зелёный) | OK | `scripts/stack_ci.py` печатает одну строку без флагов/с `--min`; `tests/test_stack_ci.py` сравнивает вывод с `orchestrator.stack` (прогнано — зелёно, см. «Проверено исполнением»). |

## Замечания

- minor — tests/test_stack_ci.py:32-58 (`test_output_diverges_from_manifest_when_manifest_is_patched`) — тест не проверяет никакое свойство `scripts/stack_ci.py` или `orchestrator/stack.py`: он запускает скрипт как есть, затем внутри `mock.patch.object` вычисляет `expected = stack.python_version_string()` (мокнутое значение) и сравнивает с уже полученным `result.stdout` — по построению это `assertNotEqual` двух независимо вычисленных строк, одна из которых захардкожена в теле теста как `"0.0.0-diverged"`; собственный докстринг честно признаёт, что «сам тест провала не потребляет» и реальная проверка происходит в другом файле (`acceptance_tests/test_ac4_stack_ci_matches_manifest.py::test_ac4_dedicated_test_fails_when_manifest_diverges_from_script`, который действительно гоняет весь `tests.test_stack_ci` под моком и проверяет `wasSuccessful() == False`). Предложение: убрать тест из `tests/test_stack_ci.py` как не несущий сигнала о продакшен-коде (дублирует, а не усиливает уже существующую проверку в приёмочном тесте) — не blocker для этой итерации, оставляю на усмотрение разработчика.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_stack_ci.py:32-58 | Тест `test_output_diverges_from_manifest_when_manifest_is_patched` не ловит мутацию продакшен-кода — только демонстрирует, что `mock.patch.object` работает; заявка «Ловит мутацию» в докстринге сама признаёт, что реальная проверка — в другом файле. | Лишний тест в наборе не даёт ложных срабатываний и не блокирует мерж — severity minor («вкус»), закрываю сразу без цикла fixed/rejected: необязательное предложение, не требование к следующей итерации. | Опционально: удалить тест либо переписать докстринг без заявки «ловит мутацию». Не требуется для мержа. |

## Вердикт

approved

Единственное замечание (R1-F1) — minor, не блокирует мерж; SPEC
выполнен полностью (все 4 требования и все 7 AC), защищённый путь
`.github/workflows/ci.yml` не тронут напрямую и диф-приложение
проверено `git apply --check` независимо на актуальном `main`
(`77c914be`), расширение зон легитимно мандатом ANSWER-1, системная
целостность не нарушена (существующие тесты не ослаблены, новых
файлов вне заявленных зон/расширения нет, `docs/codebase-map.md`
свеж).

## Проверено исполнением

- `python3 -m unittest tests.test_stack_ci tests.test_stack -v` — 10
  тестов, все зелёные.
- `python3 -m unittest tasks.01M1RDCCKBQMJ5G2K9ANJP059H.acceptance_tests.test_ac3_stack_ci_script tasks.01M1RDCCKBQMJ5G2K9ANJP059H.acceptance_tests.test_ac4_stack_ci_matches_manifest -v`
  — 3 теста, все зелёные (AC-3, AC-4 подтверждены планкой).
- `python3 -m unittest tests.test_invariants -v` (полный модуль,
  включая `StdlibOnlyImportsInvariantTest`) — зелёный: новые файлы
  `scripts/stack_ci.py`/`tests/test_stack_ci.py` не нарушают инвариант
  «сторонних пакетов нет».
- `python3 scripts/codebase_map.py` — перегенерировал карту в рабочем
  дереве, `git diff --stat -- docs/codebase-map.md` пуст (карта в
  ветке свежая, регенерация PLAN сделана верно).
- Независимая проверка AC-5: извлёк unified-диф приложения PLAN.md
  «Приложение: диф `.github/workflows/ci.yml`» в отдельный файл,
  поднял `git worktree add --detach <tmp> main` (main @ `77c914be`,
  свежее, чем `1aed801c`, зафиксированный в PLAN.md на момент сдачи) и
  прогнал `git apply --check <файл-с-диффом>` в этом worktree —
  `APPLY_CHECK_OK`, диф применяется на актуальный main без конфликтов.
  Worktree удалён (`git worktree remove --force`) после проверки.
- Прочитано построчно фактическое содержимое `.github/workflows/
  ci.yml` в рабочем дереве — подтверждено, что из джобов, исполняющих
  `python3` (`guard`, `python`, `codebase-map`), диф покрывает ровно
  эти три и не покрывает `id-format-greplint`/`canary-guid-leak`/
  `protected-paths` (они `python3` не исполняют) — соответствует
  описанию PLAN.md «Подход».
- `git status --porcelain` в рабочем дереве — чисто, кроме
  `tasks/01M1RDCCKBQMJ5G2K9ANJP059H/` (артефакты задачи, не код).

## Предложения системе

- SPEC 01M1RDCCKBQMJ5G2K9ANJP059H требование 1 приводит пример-идиому
  `python3 -c "from orchestrator import stack; print(...)"` в скобках,
  а требование 3 того же SPEC требует выносить эту логику в отдельный
  скрипт репозитория — разработчик верно разрешил кажущееся
  противоречие (идиома описывает ЧТО читать, требование 3 — КАК
  оформить вызов в ci.yml), но формулировка требования 1 могла бы
  явно отделять «источник данных» от «буквальной команды в ci.yml»,
  чтобы будущий ревьювер не тратил цикл на разбор того же вопроса.
