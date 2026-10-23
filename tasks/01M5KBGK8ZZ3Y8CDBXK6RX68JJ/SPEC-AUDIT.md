---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/test_suite_run.py."
spec_sha: 704140af877b1e9f6f955319f486d34a7a19cd4e
schema_version: 5
---

# SPEC-AUDIT: Тест argv гейта полного набора не зависит от имени интерпретатора

## ТЗ и SPEC
- ТЗ треб. 1 → SPEC треб. 1 / AC-1, AC-2, AC-3: перенесено дословно (литерал,
  одна подмена на метод, `assertEqual` всего argv, докстринг с двумя
  мутациями); импорт `stack` из фактов ТЗ перенесён в треб. 1.
- ТЗ треб. 2 → SPEC треб. 2 / AC-4, AC-5: перенесено; «на текущем коде теста
  — красный» уточнено как «на коде `tests/test_suite_run.py` до требования
  1» — точнее ТЗ, смысл тот же.
- ТЗ треб. 3 → SPEC треб. 3 / AC-6: перенесено.
- ТЗ треб. 4 → SPEC треб. 4 / AC-7: «остальные методы … остаются зелёными»
  вынесено в «Не входит» (SPEC.md:132) со ссылкой на полный набор пульта —
  допустимо: зелёный полный набор держит автогейт. AC-7 добавляет сверх ТЗ
  «добавлены только новые тесты требований 2 и 3 и импорт `stack`»
  (SPEC.md:108-110) — см. отклонение 3.
- Мандат и матрица неослабления ТЗ (TZ.md, «Меняемое поведение существующих
  тестов») в SPEC не продублированы, а отосланы к ТЗ с верной оговоркой, что
  гейт читает мандат только из ANSWER-n (SPEC.md:141-150). Раздела SPEC
  «Меняемое поведение» нет — верно: смена «вызов функции → список-литерал»
  не скалярная (docs/operator-gates.md:115-123).
- Бюджет: ТЗ $10, SPEC $25 (SPEC.md:8) — расхождение объяснено, но
  обоснование ошибочно — отклонение 1.
- «Не входит» ТЗ перенесено полностью (SPEC.md:118-134).
- ANSWER-n.md в каталоге документов нет; решений Оператора на гейте SPEC в
  брифе нет.

## Факты против кода
Подтверждено:
- `tests/test_suite_run.py:331` `class GateArgvTest(TmpRootTest)`, метод
  `:333`, подмена `acceptance.subprocess.run` `:341`, ожидание через
  `acceptance._pytest_command("tests")` вне подмены `:345-346`.
- `orchestrator/acceptance.py:37` `_pytest_command`, `:61-67` — интерпретатор
  из `stack.pytest_python_executable()`, флаги `-p no:cacheprovider -p timeout
  -o timeout={stack.PER_TEST_TIMEOUT_SEC}` — литерал AC-1 совпадает с
  фактической командой при `command=None` (`:2578-2579`, `_head(None)` →
  `None`, `acceptance.py:127-132`).
- `orchestrator/stack.py:626` `pytest_python_executable`, `:587`
  `_main_copy_root`, `:611` вызов git с `cwd=_MODULE_ROOT`; `stack` импортирует
  `subprocess`/`sys` модулями (`stack.py:34-35`), поэтому подмена
  `acceptance.subprocess.run` перехватывает и этот git, а
  `stack.sys.executable` — подменяем; `_MODULE_ROOT` — `stack.py:49`;
  `PER_TEST_TIMEOUT_SEC` — `stack.py:95`.
- `orchestrator/config.py:123` `VENV_DIR`, `:230` `FULL_SUITE_WORKERS`.
- `TmpRootTest` не подменяет `config.VENV_DIR` (`tests/sandbox.py:90-99`,
  `:1615-1618`) и не трогает `stack._MODULE_ROOT`/`sys.executable` — внешние
  подмены теста AC-4 доживают до внутреннего `GateArgvTest`.
- Сценарий треб. 2 на прежнем теле статически красный: внутри подмены ответ
  «1 passed in 0.1s» (returncode 0) → `_main_copy_root` = рабочая копия
  (`stack.py:620-623`), venv там нет → `/fake/bin/python`; ожидание вне
  подмены — настоящий git → `<временный главный>/.artel/venv/bin/python3`.
  После треб. 1 внутренний тест подменяет функцию целиком — зелёный. Живой
  прогон в шаге не выполнен (одноразовый скрипт требовал подтверждения).
- `orchestrator/advance_gates/test_integrity.py:1074` `_answer_mandate` — мандат
  только из ANSWER-n.md; `skills/code-revision.md:11-12` — команда
  `.artel/venv/bin/python -m pytest …`.

Не подтвердилось:
- SPEC.md:151-154: «$25 — пол калибровки, класс „до 5 критериев и до 3 файлов
  зоны“ — ближайший уровень таблицы». У SPEC 7 критериев и 1 файл зоны;
  `budget.recommended_budget_usd` (`orchestrator/budget.py:198-215`) по
  `config.BUDGET_CALIBRATION_TABLE` (`orchestrator/config.py:644-650`) даёт
  уровень (40.0, 10, 4) → $40. $25 < $40·2/3 → `budget.calibration_warning`
  (`budget.py:218-230`) выдаст «рамка ниже калибровки» на гейте SPEC.
- SPEC.md:118-124: «неизменность [orchestrator/config.py, tests/sandbox.py …]
  держит гейт зон пульта (зона задачи — один файл)». Гейт зон к зонам задачи
  добавляет `config.COMMON_ZONES` (`orchestrator/advance_gates/zones.py:274`),
  а это `orchestrator/config.py`, `docs/codebase-map.md`, `tests/`, `roles.yaml`
  (`orchestrator/config.py:814-815`). Правку `orchestrator/config.py` и
  `tests/sandbox.py` гейт зон пропустит; держит их только ревью. Для
  `orchestrator/acceptance.py`/`stack.py` и вызывающих утверждение верно.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да (поведение: argv под подменой равен литералу) | `run_full_suite` добавляет `-vv`/вывод в файл в прогон гейта, меняет порядок `-n`/`-p xdist` или путь `tests` |
| AC-2 | да (ast: докстринг метода) | докстринг называет только одну мутацию — текстовая проверка, слабая, но это требование к документации |
| AC-3 | да (мутация `_pytest_command` + прогон метода) | удалён `-p timeout`, `-p no:cacheprovider` или `-o timeout=…`, переставлены флаги общей части |
| AC-4 | да | тест отсутствует, гоняет не `GateArgvTest`, или подменяет сверх названного (например, саму функцию выбора интерпретатора снаружи) — последнее ловит AC-5 |
| AC-5 | да (подмена тела `GateArgvTest.test_gate_call_argv_unchanged` прежним телом и прогон теста AC-4) | тест AC-4 зелёный при любом теле — не воспроизводит условие ревизии |
| AC-6 | да | `run_full_suite`/`_pytest_command` ставит первым `"python3"` или `sys.executable` в обход `stack.pytest_python_executable` |
| AC-7 | да (диф ветки по методам файла) | правка/удаление прочих методов `tests/test_suite_run.py` |

Замечание к AC-7 — отклонение 3.

## Зоны
- `zones: tests/test_suite_run.py` покрывает треб. 1-3. Регенерация карты
  (`docs/codebase-map.md:9403-9411` — секция файла получит импорт `stack`)
  входит в `COMMON_ZONES` — отдельной зоны не требует.
- Защищённых путей задача не трогает; песочница ролей не расширяется.
- Утверждение о неизменности `orchestrator/config.py`/`tests/sandbox.py`
  «гейтом зон» неверно (см. «Факты против кода»; отклонение 2).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged` — ожидание: вызов → литерал | прогон гейта без флагов `suite-run`, прежний порядок — `tests/test_suite_run.py:345-346` | остаётся | тот же метод, `assertEqual` с литералом (AC-1) | ок |
| то же | общая часть команды pytest — не держит (ожидание из той же `_pytest_command`, `acceptance.py:37-67`) | появляется | тот же метод (AC-1, AC-3) | усиление |
| то же | первый элемент argv — результат `stack.pytest_python_executable` — косвенно, равенством двух вызовов `:345` | остаётся | новый тест AC-6 и литерал AC-1 | ок |
| то же | метод исполнял настоящий `pytest_python_executable` внутри `run_full_suite` (интеграция с выбором интерпретатора) — косвенно `:341-346` | переезжает | порядок поиска — `tests/test_stack.py:643-710` (`_MODULE_ROOT`, `_main_copy_root`) | ок |
| то же | вердикт метода не зависит от интерпретатора/вида копии — не держит | появляется | новый тест AC-4/AC-5 | усиление |

Строк «остаётся, не покрыто» нет. Мандат в ANSWER-n ещё не выдан: гейт
неослабления на `in_dev -> verifying` откажет без строки
`Ослабление тестов разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`
(`test_integrity.py:1074-1099`). Канал выдачи уже на гейте SPEC —
`answer` в `spec_gate` принимает мандат тестов (`orchestrator/answer.py:428-437`);
файл ответа обязан нести раздел `## Матрица неослабления` в форме
`docs/operator-gates.md:61-62` (пять столбцов, элемент мандата в «Что
меняется») и строку `Независимая проверка: <вердикт>`
(`docs/operator-gates.md:85-93`). Матрица ТЗ этой формы не имеет (другие
заголовки столбцов, без файл:строка) — её нельзя перенести в ANSWER как
есть; матрица выше — готовая форма.

## Пути обхода гейтов
- Правка `orchestrator/config.py` (например `FULL_SUITE_WORKERS`) или
  `tests/sandbox.py` пройдёт гейт зон (COMMON_ZONES), и литерал AC-1 через
  `str(config.FULL_SUITE_WORKERS)` её не заметит; держит только ревью. SPEC
  утверждает обратное (SPEC.md:124) — отклонение 2.
- Тест AC-4 с лишней внешней подменой (например,
  `acceptance.stack.pytest_python_executable`) зелёный при любом теле —
  закрыт AC-5 (красный при прежнем теле). Обхода нет.
- AC-6 можно выполнить дублем утверждения AC-1 — допустимо, свойство
  проверено.

## Вердикт
concerns. Отклонения:

1. Бюджет: SPEC.md:151-154 обосновывает $25 классом «до 5 критериев», а
   у SPEC 7 AC; `budget.recommended_budget_usd(7, 1)` = $40
   (`orchestrator/budget.py:198-215`, `orchestrator/config.py:644-650`).
   На гейте SPEC сработает «рамка ниже калибровки: $25.00 против ~$40.00»
   (`budget.py:218-230`). Решение Оператора: поднять до $40 или принять $25
   с предупреждением.
2. SPEC.md:118-124 — утверждение «неизменность держит гейт зон пульта»
   неверно для `orchestrator/config.py` и `tests/sandbox.py`: они в
   `config.COMMON_ZONES` (`orchestrator/config.py:814-815`,
   `orchestrator/advance_gates/zones.py:274`). Ни один AC не держит их
   неизменность — только ревью. Решение Оператора: принять (ревью) или
   потребовать правки SPEC (AC «диф ветки вне `tests/test_suite_run.py` и
   `docs/codebase-map.md` пуст»).
3. AC-7 (SPEC.md:108-110) «добавлены только новые тесты … и импорт `stack`»
   — строже ТЗ (TZ.md:30 запрещает только правку остальных методов) и
   может зарезать законную реализацию треб. 2: модульный помощник
   (создание репозитория с рабочей копией) или ещё один импорт
   (`tempfile`, если класс не наследует `TmpRootTest`) формально нарушат
   AC-7. Решение Оператора: читать AC-7 как «прочие методы не изменены»
   или снять вторую половину.
4. Мандат: SPEC.md:141-150 верно говорит, что мандат придёт только через
   ANSWER-n, но отсылает к гейту эскалации п.6. Мандат можно выдать уже на
   гейте SPEC (`orchestrator/answer.py:428-437`). Без этого рубеж
   `in_dev -> verifying` откажет (`test_integrity.py:1074-1099`). Матрица ТЗ
   не в форме `docs/operator-gates.md:61-62` — для ANSWER нужна матрица
   формы (см. раздел выше).
