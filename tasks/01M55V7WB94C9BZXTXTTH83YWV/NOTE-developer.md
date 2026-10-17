# Записка developer

## Выяснено
- Схема: `ci._project_context(repo)` — (ctx, отказ) по пути клона: is_artel(path) → артель; путь под `repo_context.projects_root()/<имя>/` с не-артельным именем → `repo_context.resolve(имя)` (None → отказ Н-4); иначе артель (в т.ч. config.ROOT).
- `ci.gh(repo=<url>)`: для `gh api` — `GH_REPO` в env (разбор https/scp `_owner_and_name`), без `--repo`; для `gh run/pr` — `--repo` как было.
- Внутренние вызовы у артели — прежняя форма (без repo=) через `_project_kwargs`.
- Вызывающие (`ci_rerun.py`, `fsm_merge_gate.py`) передают `**ci._repo_kwargs(workspace.task_repo(task_id))`.
- Код закоммичен WIP-чекпоинтом 6fe01626. Шаг 2: тесты затронутых модулей (164) и долгоживущий файл зелёные, планка 4/4.
- suite-run №1 оборван пределом 1500 с при load average ~80: 67 «новых упавших» без сообщения pytest в 67 разных несвязанных файлах — недобежавшие при обрыве, не дефект ветки.

## Не сработало
- `ls`/`rm` в Bash недоступны; `-n 4` у pytest — воркеры падают.
- `suite-run --failed` отказал: идёт прогон гейта другой задачи.

- Настоящий красный: tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py::MergeGateStepsOnCloneTest::test_ac5_external_project_skips_the_artel_steps — url проекта в песочнице = локальный путь к bare, наш отказ «вид адреса не разобран» → CI неизвестен → гейт мержа ждёт → не done. На main работал только из-за дефекта (gh шёл к артели).

## Где остановился
- PLAN status: escalate, вопрос — amend-tests теста 01M42 (дефолт) или исключение для локального пути/file://.
- Ещё 2 красных того же класса: test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py::ExternalMergeTest::test_ac12_* (sandbox make_project_repo → url file:///nonexistent/<имя>). Полный набор после ответа надо перегнать: другие тесты на make_project_repo могут падать так же.

## Чего не хватило
- Машина перегружена — полный набор не укладывается в предел.
