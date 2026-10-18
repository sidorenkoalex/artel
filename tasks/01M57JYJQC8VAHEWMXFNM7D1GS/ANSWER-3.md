---
task: 01M57JYJQC8VAHEWMXFNM7D1GS
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-3: ответ Оператора

## Ответы

## Ответ Оператора (уточнение мандата ANSWER-1)

Гейт неослабления называет правку помощника `PlankLongLivedSandbox.assert_runs_file` (:345-348) находкой вызывающего теста. Это та же правка, разрешённая в ANSWER-1 (расширение отрицательной проверки путём выкладки по префиксу); объём мандата не меняется.

Ослабление тестов разрешено: tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py::Ac5OwnProfileLongLivedRunTest::test_ac5_long_lived_path_runs_by_own_profile

## Матрица неослабления
Материал к мандату варианта A вопроса 1. Строка на каждое свойство.

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py::Ac5OwnProfileLongLivedRunTest::test_ac5_long_lived_path_runs_by_own_profile` — через помощника `assert_runs_file` (:345-348): запретные цели дополняются путём выкладки по префиксу | «`plank-run <id> <долгоживущий путь>` не гонит планку задачи» — `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:345-348, вызов :393 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:345-348 после правки (оба пути, по префиксу) | ок |
| `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py::PlankLongLivedSandbox::assert_runs_file` (:345-348): запретное множество целей дополняется путём выкладки | «`plank-run <id> <долгоживущий путь>` не гонит планку задачи» — :345-348 (через `Ac5OwnProfileLongLivedRunTest::test_ac5_long_lived_path_runs_by_own_profile`) | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:345-348 после правки (оба пути) + новый AC SPEC «выкладка не создаётся и путь выкладки целью не служит» | ок при условии: новый AC в SPEC |
| то же (:345-348): прежний путь `tasks/<id>/acceptance_tests` в множестве сохраняется | «цель — не каталог планки в рабочей копии» — :345-348 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:345-348 без изменения этой части | ок |
| `…::Ac6PreviousOutcomeTest::test_ac6_foreign_paths_and_plain_calls_keep_previous_outcome` :471, цель `self.ext`: ожидание `[plank]` → `[<путь выкладки>]` | «`plank-run <id>` без аргумента гонит ровно каталог планки, одной целью» — :471 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:471 после правки (`assertEqual` над всем списком) + AC-2 SPEC (отображение аргумента на путь выкладки) | ок |
| то же :480, цель `self.ext`: ожидание `[plank/<name>]` → `[<путь выкладки>/<name>]` | «`plank-run <id> <файл планки>` гонит ровно этот файл» — :480 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:480 после правки + AC-2 SPEC | ок |
| то же :471/:480, цель `ARTEL` | прежняя цель артели `tasks/<id>/acceptance_tests` — :471/:480 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:471/:480 без изменения + AC-8 SPEC (артель прежняя) | ок |
| то же :472 | «свой долгоживущий файл не в целях вызова без аргумента» — :472 | остаётся | `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py`:472 без изменения | ок |


Независимая проверка: подтверждаю — та же правка :345-348, проверенная независимым агентом 18.10 для ANSWER-1: запретных целей становится больше (прежний путь плюс путь выкладки по префиксу), assertFalse над всеми целями сохраняется.
