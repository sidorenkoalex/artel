# Записка developer

## Выяснено
- Прямой вызов гейта (планка) передаёт `acc_tdir` = каталог `acceptance_tests` черновика, переход — `run_cwd/tasks/<id>`; гейт принимает обе формы (`_task_plank_dir`).
- `covered` в планке — строки `AC-<n>`; переход передаёт `{f"AC-{n}"}`. Долгоживущие файлы при прямом вызове гейт читает из диффа кодовой ветки (ключевой `long_lived_paths=None`).
- Общий разбор записей по критериям — `advance_gates/acceptance.py` (`criterion_files`, `record_criterion`, `file_records`); гейт — в `advance_gates/tests_writing.py`.
- Новый гейт сломал метод G2б-1 `test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py::Ac5LabelledLongLivedFlowTest::test_ac5_checkpoint_manifest_verification_and_zones` (нет перехода гейта SPEC, отчёт без тестов критериев) — подготовка метода приведена к механике, утверждения не тронуты (PLAN, шаг 8).

## Не сработало
- `pytest -n` на нескольких файлах tests/ — conftest роняет воркеры; гонять серийно.
- heredoc `cat >> … <<EOF` с `{…'…}` в Bash отклонён песочницей — дописывать файлы через Edit.

## Где остановился
Готово, PLAN.md `status: ready`. Долгоживущие файлы задачи, планка (5/5), тесты затронутых модулей зелёные; suite-run №1: 6152 прошли, 1 провал (метод выше) → после правки `--failed` №2 зелёный.

## Чего не хватило
- Что полный набор знает тест G2б-1, ведущий `pult-vitest` в `in_dev` без опоры SPEC, — SPEC его не назвал; нашёл только suite-run.
