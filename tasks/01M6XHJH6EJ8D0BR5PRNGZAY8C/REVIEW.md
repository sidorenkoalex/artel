---
task: 01M6XHJH6EJ8D0BR5PRNGZAY8C
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Метка размера у новых долгоживущих файлов и её статическая проверка на выходе из tests_writing (ADR-0032, этап 4)

## Фаза A: план
- Таблица покрытия полна: требования 1–4 → шаги 2, 1, 1+3, 5.
- Шаги — проверяемые единицы (правила / профиль / вызывающие / тест / приложения), не микрооперации.
- Подход совпадает с решением Оператора 7 (разбор `pytestmark` перенесён в `test_lint.py`, guard ссылается на него — цикла импорта нет) и с указанием Оператора на гейте SPEC (п. 1: `annotated` только у правил размера; п. 4: перечень строится только при `size_marks=True`).
- «Влияние на систему» совпадает с diff: 7 модулей зоны + новый `tests/test_size_marks_sources.py`; защищённые пути (`pyproject.toml`, `targets.yaml`, `skills/`) в ветке не тронуты — только приложения. Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `targets.py`: `PROFILE_FIELDS["size_marks"]`, в `PROFILE_OPTIONAL`; `_profile_value_error` (`targets.py:1967`) — «'<значение>', ожидается required» и для нестроковых значений; `Profile.size_marks` и в `component_profiles` (указание Оператора п. 2). |
| 2 | OK | `heavy_sandbox_names` — собирает классы всех исходников, потом замыкает до неподвижной точки (от порядка не зависит); `size_findings` — нет метки / несколько меток / не литерал / вне перечня / small / medium / large по тексту SPEC. |
| 3 | OK | Параметры `size_marks`, `sandbox_sources` у guard; `heavy` строится один раз на вызов и только при флаге (`guard.py:4449`); правила — только у Python-файлов группы «долгоживущий» без метки `AC-<n>: ` (стоят после `continue` у labelled, `guard.py:4467-4487`); исключение залоченных — `_size_rules_apply`; `lint_base` теперь передаётся на `amend.py:317` в обоих режимах (рабочая копия — голова кодовой ветки, `--from-branch` — `_locked_long_lived_texts`); текст отказа по форме SPEC. |
| 4 | OK | Приложения 1–3 в PLAN совпадают с SPEC дословно. |

## Замечания
- minor — `orchestrator/advance_gates/tests_writing.py:525`, `orchestrator/preflight.py:265` — `guard.sandbox_sources_from_dir(...)` читает модули песочниц с диска при любом профиле, в том числе без `size_marks`. Перечень не строится (guard не вызывает `heavy_sandbox_names` без флага), так что указание Оператора п. 4 соблюдено, но это лишнее чтение файлов. `amend._sandbox_sources` то же самое делает только при включённом правиле. Предложение (на вкус): читать только при `size_marks_required(profile)`. Блокером не считаю — на поведение не влияет.
- Наблюдение для Оператора (не замечание разработчику): правило среднего файла срабатывает на любой строковый литерал, оканчивающийся на `artel.py`, в аргументах вызова `subprocess`. Пример: `subprocess.run(["git", "add", "orchestrator/artel.py"])` в `medium` даёт «дочерний artel.py или pytest в среднем файле», хотя дочернего `artel.py` здесь нет (проверено прогоном). Так требование 2 и написано («в любом узле … литерал, оканчивающийся на `artel.py`»), то есть код SPEC соответствует. Если при включении у артели пойдут ложные срабатывания, их стоит поправить следующим этапом.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/advance_gates/tests_writing.py:525; orchestrator/preflight.py:265 | модули песочниц читаются с диска и без `size_marks` | лишнее чтение файлов на каждом вызове; поведение то же | minor, на вкус: читать только при включённом правиле; на вердикт не влияет |

## Вердикт
approved — blocker и major нет. Требования 1–4 реализованы так, как написано в SPEC. Указания Оператора на гейте учтены: разбор `pytestmark` для прежних входов не изменился, `AnnAssign` читается только правилами размера, `lint_base` на `amend.py:317` берётся того же режима, что вызов. Существующие тесты не изменены и не ослаблены: в `tests/` добавлен только новый файл.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6xhjh6ej8d0br5prngzay8c_size_rules.py tests/test_size_marks_sources.py tests/test_01m6xhjh6ej8d0br5prngzay8c_size_gate_paths.py` — 94 passed за 48.5 с (3 предупреждения `PytestUnknownMarkWarning`: метку регистрирует приложение 1 после мержа).
- `artel.py plank-run 01M6XHJH6EJ8D0BR5PRNGZAY8C` — отказ «планки нет: нет файлов test_*.py». Разовых файлов у задачи нет, все критерии держат два долгоживущих файла из перечня лока (прогнаны выше).
- Временная мутация в памяти (подмена `guard._size_rules_apply` на «любой файл из `lint_base` освобождён»): `test_ac7_locked_without_mark_exempt_with_mark_checked` и `test_ac9_locked_with_mark_not_skipped` — RED, мутация AC-9 «залоченный файл с меткой пропускается» ловится. Файл пробы удалён `task-rm`.
- Проба `size_findings` на `subprocess.run(["git", "add", "orchestrator/artel.py"])` в `medium` — нарушение (см. наблюдение выше).
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` — расходится только `built_at_sha`, карта свежая; рабочая копия возвращена (`git checkout -- docs/codebase-map.md`, статус чистый).
- CI коммита 609a7856 (HEAD) — зелёный, 16 проверок (из пакета).

## Предложения системе
- `plank-run` у задачи без разовых файлов отвечает «отказ — планки нет». Для задачи, у которой все критерии держат долгоживущие файлы, это штатный случай, а слово «отказ» читается как сбой. Стоит отвечать отдельной строкой «разовых файлов нет; долгоживущие: …» (`orchestrator/artel.py plank-run`).
