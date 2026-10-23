---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/sandbox.py, tests/test_suite_run.py."
spec_sha: 51d194fda2418d2880960feb3d835b591a2ff1d8
schema_version: 5
---

# SPEC-AUDIT: Тест argv гейта полного набора не зависит от имени интерпретатора

## ТЗ и SPEC
- ТЗ треб. 1 → SPEC треб. 1 / AC-1, AC-2, AC-3: перенесено дословно (одна
  подмена `acceptance.stack.pytest_python_executable` на метод, литерал,
  `assertEqual` всего argv, докстринг с двумя мутациями); импорт `stack` из
  фактов ТЗ — в треб. 1.
- ТЗ треб. 2 → SPEC треб. 2 / AC-4, AC-5: перенесено; «на текущем коде теста —
  красный» уточнено как «на коде `tests/test_suite_run.py` до требования 1» —
  смысл тот же.
- ТЗ треб. 3 → SPEC треб. 3 / AC-6: перенесено.
- ТЗ треб. 4 → SPEC треб. 4 / AC-7, AC-8: «остальные методы не правятся» —
  AC-7 (теперь ровно по ТЗ, с допуском новых тестов/помощников/импортов);
  «код пульта не меняется» — AC-8; «остаются зелёными» вынесено в «Не входит»
  (держит полный набор пульта) — допустимо.
- Решения Оператора на гейте SPEC №1 (23.10, круг 1) все отражены:
  1) `budget_usd: 40` (SPEC frontmatter), обоснование в «Материалах»;
  2) новый AC-8 «дифф вне `tests/test_suite_run.py` и `docs/codebase-map.md`
  пуст», утверждение «держит гейт зон» заменено на «гейт зон их правку не
  остановит — неизменность держит AC-8» («Не входит», п.1);
  3) AC-7 ослаблен до ТЗ. Прежние отклонения 1–3 прошлого аудита сняты.
- Мандат и матрица неослабления ТЗ в SPEC не продублированы, а отосланы к ТЗ
  с верной оговоркой, что гейт читает мандат только из ANSWER-n. Раздела
  «Меняемое поведение» нет — верно: «вызов функции → список-литерал» — не
  смена скалярного литерала.
- «Не входит» ТЗ перенесено полностью. Требований сверх ТЗ/решений нет.
- ANSWER-n.md в каталоге документов нет (каталог: TZ, SPEC, PASSPORT,
  SPEC-AUDIT, записка) — мандата пока нет, см. вердикт п.1.

## Факты против кода
Подтверждено (рабочий каталог):
- `tests/test_suite_run.py:331` `class GateArgvTest(TmpRootTest)`, метод
  `:333`, подмена `acceptance.subprocess.run` `:341-342`, ожидание через
  `acceptance._pytest_command("tests")` вне подмены `:345-346`; импорта
  `stack` в файле нет (`:16-17`) — требуется треб. 1.
- `orchestrator/acceptance.py:37` `_pytest_command`, `:61-67`: голова
  `[stack.pytest_python_executable(), "-m", "pytest"]`, хвост `-p
  no:cacheprovider -p timeout -o timeout={stack.PER_TEST_TIMEOUT_SEC}` —
  литерал AC-1 совпадает с фактической командой.
- `orchestrator/stack.py:587` `_main_copy_root`, `:610-612` git с
  `cwd=_MODULE_ROOT`; `:620-623` относительный ответ «1 passed in 0.1s»
  резолвится от `_MODULE_ROOT`, родитель — сама рабочая копия → venv нет →
  `sys.executable`; `:626` `pytest_python_executable`, порядок поиска
  `:640-644`. Сценарий треб. 2 на прежнем теле статически красный
  (`/fake/bin/python` против `<временный главный>/.artel/venv/bin/python3`),
  после треб. 1 — зелёный (функция подменена целиком).
- `orchestrator/config.py:644-650` — 8 AC, 1 файл зоны → уровень (40.0, 10, 4)
  → `budget.recommended_budget_usd` (`orchestrator/budget.py:198-215`) = $40;
  утверждение SPEC о калибровке верно.
- `orchestrator/config.py:814-815` `COMMON_ZONES` содержит
  `orchestrator/config.py` и `tests/` — исправленное утверждение SPEC верно.
- `orchestrator/advance_gates/test_integrity.py:1074` `_answer_mandate` —
  мандат только из ANSWER-n.md.
- `skills/code-revision.md:12` — запуск `.artel/venv/bin/python -m pytest`.

Не подтвердилось: нет. Мелочь: «Материалы» одновременно отсылают к «гейту
эскалации, п.6» и к «следующему гейту SPEC» как каналу мандата — второе
верно (решение гейта №1), первое устарело, на исполнение не влияет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да (argv под подменой равен литералу) | `run_full_suite` добавляет `-vv`/вывод в файл, меняет порядок `-n`/`-p xdist`/путь `tests` |
| AC-2 | да (ast: докстринг метода) | докстринг называет одну мутацию из двух — требование к документации |
| AC-3 | да (мутация `_pytest_command` + прогон метода) | удалён `-p timeout`/`-p no:cacheprovider`/`-o timeout=…`, переставлены флаги общей части |
| AC-4 | да | тест отсутствует, гоняет не `GateArgvTest`, не строит worktree без venv |
| AC-5 | да (прогон теста AC-4 с прежним телом метода из базы) | тест AC-4 зелёный при любом теле (лишняя внешняя подмена функции выбора интерпретатора) |
| AC-6 | да | `run_full_suite`/`_pytest_command` ставит первым `"python3"` или `sys.executable` в обход `stack.pytest_python_executable` |
| AC-7 | да (диф методов файла против базы) | правка/удаление прочих методов `tests/test_suite_run.py` |
| AC-8 | да (`plank_helper.changed_paths`/`branch_diff`) | правка `orchestrator/config.py` (`FULL_SUITE_WORKERS`), `tests/sandbox.py`, `acceptance.py`, `stack.py` |

## Зоны
- `zones: tests/test_suite_run.py` покрывает треб. 1–3; регенерация карты
  (`docs/codebase-map.md`) — в `COMMON_ZONES`, AC-8 её допускает.
- Защищённых путей задача не трогает; песочница ролей не расширяется.
- Общие зоны (`orchestrator/config.py`, `tests/`) гейт зон не держит — теперь
  держит AC-8. Отклонений нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged | прогон гейта без флагов `suite-run`, прежний порядок — `tests/test_suite_run.py:345-346` | да | тот же метод, `assertEqual` с литералом (AC-1) | сохраняется |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged | общая часть команды pytest — не держит (ожидание из той же `_pytest_command`, `orchestrator/acceptance.py:61-67`) | да, появляется | тот же метод (AC-1, AC-3) | усиливается |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged | первый элемент argv — `stack.pytest_python_executable` — косвенно, `tests/test_suite_run.py:345` | да | новый тест AC-6 и литерал AC-1 | сохраняется |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged | интеграция `run_full_suite` с настоящим выбором интерпретатора — косвенно `tests/test_suite_run.py:341-346` | переезжает | порядок поиска — `tests/test_stack.py` (тесты `_main_copy_root`/`pytest_python_executable`), код `orchestrator/stack.py` не меняется (AC-8) | сохраняется |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged | независимость вердикта от интерпретатора/вида копии — не держит | да, появляется | новый тест AC-4/AC-5 | усиливается |

Строк «остаётся, не покрыто» нет. Матрица ТЗ — в иной форме (без
файл:строка, другие столбцы); для ANSWER с мандатом годится форма выше
(`docs/operator-gates.md`).

## Пути обхода гейтов
- Правка `orchestrator/config.py`/`tests/sandbox.py` в обход гейта зон —
  закрыта AC-8.
- Тест AC-4 с лишней внешней подменой функции выбора интерпретатора — закрыт
  AC-5.
- AC-6 дублем утверждения AC-1 — допустимо, свойство проверено.
- Других путей не найдено.

## Вердикт
concerns. Отклонения:

1. Мандат на правку ожидания `tests/test_suite_run.py:345-346`
   (`GateArgvTest::test_gate_call_argv_unchanged`) ещё не выдан строкой
   ANSWER-n: в каталоге документов ANSWER-n.md нет, а гейт неослабления
   читает мандат только оттуда (`orchestrator/advance_gates/test_integrity.py:1074`).
   Решение гейта №1 обещает строку на этом гейте SPEC — без неё рубеж
   `in_dev -> verifying` откажет. ANSWER должен нести строку
   `Ослабление тестов разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged`
   и матрицу формы `docs/operator-gates.md` (готовая — раздел выше).
2. Мелочь, правки не требует: «Материалы» SPEC называют каналом мандата и
   «гейт эскалации, п.6», и «следующий гейт SPEC» — действует второе.
