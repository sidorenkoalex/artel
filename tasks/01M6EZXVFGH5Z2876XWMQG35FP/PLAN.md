---
task: 01M6EZXVFGH5Z2876XWMQG35FP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab Б2.3-3: строки doctor проекта и forge-probe по ветке или коммиту

## Подход
- Развилка в `project_entry_checks` (`orchestrator/doctor/project_checks.py`):
  `gitlab = doctor.forge.ci_by_pipeline(name)` выбирает путь GitLab строк
  `ci-pull-request`, `base-protection`, `token`, `ci-token`;
  `human = doctor.targets.merged_by_project_people(entry)` добавляет новые
  строки `project-ci-file-no-paths-`, `project-submodules-` (после прежних),
  а `component_checks` — `project-ci-reruns-<имя>-<компонент>`. Литералов
  хостинга/`merge_gate` в модуле нет; прежние функции GitHub не меняются —
  строки артели и `github` + `operator` идут тем же кодом (треб. 15).
- Поле `http_status: int | None = None` в `forge.Protections`,
  `PipelineStatus`, `BranchPipeline` (последним полем — позиционные вызовы
  прежние). В `gitlab_adapter` код берётся только из `Reply.status`
  помощником `_failed_status(reply)` (не 2xx — код, иначе `None`);
  `_read_all` и `_pipeline_findings` возвращают его дополнительным
  элементом; тексты `reason` не меняются. Отказ чтения заданий даёт код и
  при красном конвейере (ANSWER-1 п. 3).
- Свой минимальный разборщик блочного YAML для `.gitlab-ci.yml` в
  `project_checks.py` (треб. 12): отображения, блочные списки (`- …`,
  включая `- ключ: …`), скаляры в кавычках и без, простые потоковые
  `[…]`/`{…}`; якоря/ссылки, теги, многострочные скаляры, `---`, табуляция
  в отступе, нестыкующийся отступ — исход «не разобран: строка N: …».
  Прочие ключи пропускаются (ANSWER-1 п. 2).
- Оценка `workflow:rules` (треб. 6): выражения `if` — свой разбор
  (переменная, строка, `/рег/`, `==`, `!=`, `=~`, `!~`, `&&`, `||`, скобки);
  неподдержанное `if` и `changes`/`exists` у сработавшего правила — `warn`
  «правило может сработать» (ANSWER-1 п. 4 вместо `skip` SPEC); `include:` без
  локального `workflow:rules` — `warn` «.gitlab-ci.yml не разобран: include».
- Перезапуски (треб. 9): задание `ci_job`, слитое по `extends` (глубокое
  слияние отображений, как GitLab), `retry` — своё/унаследованное/из
  `default:`; `retry: {max: N}` при N > 0 — находка (ANSWER-1 п. 2); скрипты
  (свои и из `default:`) и `variables` — `targets.RERUN_FLAGS`/
  `RERUN_PLUGINS` тем же разбором, что `targets._rerun_argument`, плюс
  установка `pytest-rerunfailures`. `include:` без находки — `warn`
  «не разобран: include» (перезапуск мог прийти из подключённого файла).
- Подмодули (треб. 10): `.gitmodules` читается разбором текста (без
  процесса); https на хосте записи — проба `gitcmd.in_repo(клон,
  "ls-remote", адрес)`; ssh на том же хосте и чужой хост — `warn`
  (ANSWER-1 пп. 1, 4); относительный адрес — от `url` записи.
- `forge-probe --ref|--sha` (треб. 13) — разбор флагов в `_forge_probe_args`,
  оба вместе — отказ с подсказкой.

## Шаги
1. `forge.py`, `gitlab_adapter.py`: поле `http_status` и его проведение.
2. `project_checks.py`: развилка, строки GitLab (3, 5, 6, 7, 14), разборщик
   файла CI, новые строки 8–10.
3. `artel.py`: `forge-probe --ref|--sha`.
4. Юнит-тесты `tests/test_doctor_gitlab_ci_file.py` (свойства вне
   долгоживущих файлов задачи: ssh/чужой хост/относительный адрес
   подмодуля, `include`, неподдержанное `if`, `changes`, `$CI_PIPELINE_SOURCE`,
   `retry: {max}`, 403 заданий при `failed` конвейере), карта кода.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 1 |
| 5 | 2 |
| 6 | 2 |
| 7 | 2 |
| 8 | 2 |
| 9 | 2 |
| 10 | 2 |
| 11 | 2 |
| 12 | 2 |
| 13 | 3 |
| 14 | 2 |
| 15 | 2 |

## Влияние на систему
- Затрагивается только `doctor` по записям внешних проектов и
  диагностическая команда `forge-probe`; FSM, гейты и инвариант 41 не
  меняются (строка перезапусков только читает файл). Сторож ac9 и его
  `EXEMPT` не трогаются — выбор пути через `forge.ci_by_pipeline` и
  `targets.merged_by_project_people`.
- Новое поле dataclass — со значением по умолчанию, прежние конструкторы и
  чтения полей не меняются; сигнатуры закрытых помощников адаптера
  меняются только внутри модуля.
- Откат — revert merge-коммита задачи.

## Риски
- Разборщик YAML неполон намеренно: необычная, но корректная форма файла
  даёт `warn` «не разобран», не ложный `ok`.
- Регулярные выражения GitLab (RE2) сверяются модулем `re` Python — для
  поддержанного подмножества (якоря, классы, экранирование) совпадают.

## Проверка
- `python3 -m pytest` долгоживущих файлов задачи (39 + 9 + 4 — зелёные),
  `tests/test_doctor_gitlab_ci_file.py` (22), смежных модулей doctor/forge/
  gitlab и сторожа ac9 (458 — зелёные); `plank-run` — 1 passed.
- Временная мутация (`retry: {max}` не читается; `include` в строке
  перезапусков пропущен) — оба сторожа покраснели, код возвращён.
- Строка перезапусков без файла CI — `skip` по SPEC (ANSWER-1 «нет файла
  CI — warn» прочитан как строка правил workflow, где SPEC тоже `warn`).

## Предложения системе
- Bash шага роли отказывает в heredoc с `{…'` и в `ls`/`wc`/`cp` — правку
  крупного блока пришлось делать инструментом Edit; в миссии стоит назвать
  доступный набор команд.
