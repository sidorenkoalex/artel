# Записка analyst — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- ТЗ достаточно, пишу SPEC (без QUESTIONS). Выбор по `_list_tree`: потоковое чтение с пределом байт и сроком — новая функция `gitcmd` (одна точка запуска под git 4).
- Песочница `tests/sandbox.py::LightTransitionSandbox` (:2129, setUp :2173…) подменяет заглушками не только `gitcmd.git`, но и `gitcmd.in_repo` (дефолт уходит в `fake_git`), `show`, `ls_tree_files` — переносить места на `in_repo` нельзя, нужна отдельная функция (как `carpentry`).
- `TmpRootTest` подменяет `gitcmd.subprocess.run` шпионом `SpyRun` (sandbox.py:1334–1384), который отвечает фейковым sha на `write-tree`/`hash-object` (:1375). Сейчас `suite_tree_hash` и `_list_tree` идут через `Popen` и шпиону не видны; перевод их на `subprocess.run` тихо изменил бы результат под песочницей. В SPEC это требование 4 (поведенческая форма).
- Сроки сейчас: `suite_tree_hash` 15 с → None; `_clone_git`/`branch_commit` — `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` → «git не ответил (TimeoutExpired)»; `_list_tree`/`_cat_blobs` — остаток дедлайна → `_Failure(DEADLINE, «срок исчерпан на ls-tree/cat-file»)`. У `tz_check._git` и `outcome_integrity._added_lines` срока нет — и не добавляется.

## Не сработало
- Составной bash с `cd` и пайпами отклоняется правами — только одиночные команды с абсолютными путями.

## Где остановился
- SPEC написан (9 AC, budget 40 = рамка ТЗ, монолит с материалом для нарезки на 2 части), `status: ready`; guard: ок.

## Чего не хватило
- Сводки «какие функции gitcmd тесты подменяют заглушками» — собирал grep'ом по tests/.
