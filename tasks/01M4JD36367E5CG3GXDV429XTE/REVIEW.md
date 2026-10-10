---
task: 01M4JD36367E5CG3GXDV429XTE
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: amend-tests и plank-run работают с планкой, импортирующей помощник `_pult.py`

## Фаза A — гейт плана
- Таблица покрытия полна: требования 1–4 привязаны к шагам 1–3, требование 5
  честно помечено «—» (существующие методы `tests/` не меняются: диф
  `tests/` — только новый класс `PlankRunDriftEdgesTest` и два файла лока).
- Шаги размером MR, проверяемые. Подход в зоне SPEC: `.gitignore`,
  `advance_gates/`, `plank_helper.py` не тронуты.
- «Влияние на систему» сходится с дифом (4 файла кода/тестов + карта).
  Ужесточение простого пути (сухой сбор → отказ на планке без тестов)
  вынесено в «Риски» открыто, и с путём с долгоживущими файлами и гейтом
  `in_dev` оно согласовано.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `acceptance.plank_helper_laid_out` (acceptance.py:847) кладёт помощник `_plank_helper_text` и той же ревизией, что `materialize_files`; `_cmd_amend_tests` оборачивает им оба пути (amend.py:672–680). `--from-branch` уже шёл через `plank_in_code_copy` → `materialize_from_branch`; AC-3 зелёный. Обходов нет: в тестах пути без PYTHONPATH и без exclude. |
| 2 | OK | `_is_plank_helper` исключает помощник из `_tests_snapshot` (диск) и из `_artifact_tests_snapshot` (ссылка). Снимок диска — источник и для `plank_same`, и для файлов коммита, поэтому в ссылку помощник не попадает (AC-4, AC-5 зелёные). |
| 3 | OK | `plank_run._drift_from_ref` побайтно сверяет диск с головой ссылки: ловит изменённые, новые и недостающие файлы, помощник и `__pycache__` пропускает. Отказ идёт до `plank_in_code_copy`, то есть до любой записи на диск; в тексте есть имена файлов и `amend-tests`. Если ссылку прочитать не удалось — отказ (fail-closed). |
| 4 | OK | В простом пути добавлен сухой сбор `acceptance.collect` с отказом `_refuse`, разбор маркеров красноты остался прежним. AC-8 (синтаксис) и AC-9 (красный тест) зелёные. |
| 5 | OK | Утверждения существующих методов `tests/` не менялись: диф `tests/test_plank_run_edges.py` только добавляет новый класс; `setUp` и фикстуры базового `PlankRunSandbox` не тронуты. |

Тесты. Оба долгоживущих файла несут маркер `Группа: долгоживущий` и
проверяют свойства кода, а не факты задачи. Заявки «Ловит мутацию» говорят
о наблюдаемом: отказ/проход, вызов pytest, содержимое ссылки. Два новых
метода `PlankRunDriftEdgesTest` не повторяют долгоживущие: случаи
«удалённый файл» и «только помощник и кеш байткода» долгоживущие файлы не
покрывают. Обе заявки я подтвердил временной мутацией (см. ниже).

Код решает задачу в общем виде: нет ветвлений под литералы фикстур.
Помощник берётся по глобалу `PLANK_HELPER_NAME`, а не по строке `_pult.py`.

## Замечания
Замечаний уровня blocker/major/minor нет.

Наблюдения, которые замечаниями не являются:
- `plank_run.py:93–113`: чтобы выйти из отказа «расходятся» при
  оставленном черновике, Оператору надо убрать файлы руками; текст отказа
  это прямо подсказывает. Требование 3 так и сформулировано: отказ, а не
  перезапись.
- `--from-branch` по-прежнему стирает незафиксированную правку в рабочей
  копии. SPEC это не покрывает (требование 3 только про `plank-run`), в
  PLAN это вынесено в «Предложения системе» — поддерживаю отдельной
  задачей.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний в этой итерации нет, записей прошлых итераций нет.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4JD36367E5CG3GXDV429XTE`
  — отказ «планки нет: … нет файлов test_*.py». Это ожидаемо: в
  зафиксированной планке задачи только `long_lived.sha256.txt`, а её
  свойства держат долгоживущие файлы в `tests/`.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py tests/test_plank_run_edges.py tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`
  — 21 passed, 4 subtests passed (48 с).
- `python3 -m pytest -q -p no:cacheprovider tests/test_amend*.py tests/test_plank_helper.py tests/test_01m41r4y*_plank_run.py tests/test_01m41w15*_plank_run_role.py`
  — 78 passed, 35 subtests passed (4 мин 16 с).
- Временные мутации `orchestrator/plank_run.py` (после каждой код
  возвращён `git checkout`, `git status` чистый):
  - `set(disk) | set(fixed)` → `set(disk)`: красный
    `test_deleted_plank_file_is_drift`;
  - снят фильтр помощника `rel != acceptance.PLANK_HELPER_NAME`: красный
    `test_helper_and_bytecode_alone_are_not_drift`;
  - снят фильтр `_is_plank_file` в `_draft_files` (кеш байткода): красный
    `test_helper_and_bytecode_alone_are_not_drift`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строки `built_at_sha` — расхождений нет, карта свежая (регенерацию
  откатил).
- CI коммита e803b034 — зелёный (16 проверок, из пакета).

## Предложения системе
- Пакет ревью/миссия велят прогнать планку через `plank-run`, но у задач,
  где вся планка — это `long_lived.sha256.txt`, команда отвечает отказом
  «планки нет». Стоит, чтобы `plank-run` в таком случае гонял долгоживущие
  файлы из перечня лока либо говорил прямо, что планка состоит только из
  перечня (`orchestrator/plank_run.py`).
