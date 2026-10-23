# Записка test_author — 01M5K11D3284ZZGRHN39FGQVF2

## Выяснено
- Планка: `acceptance_tests/test_push_server_retry.py` (AC-1..AC-14, разовый) и `acceptance_tests/test_ac9_existing_test_untouched.py` (AC-9: `tests/test_artifact_ref_sync.py` не в `changed_paths()`). Долгоживущих файлов нет.
- Ответ `git push` подменяется на уровне `gitcmd.git` (по `strip_dash_c`, остальной git — настоящий, `AutoOriginSandbox`); пауза — `mock.patch.object(artifact_branch, "time", TimeWithSleep(...), create=True)`. Классификация видна по началу детали «push артефактной ветки FAILED» после `commit_files` (путь `_send`).
- AC-7/AC-14 дополнительно подменяют `PUSH_SERVER_RETRY_ATTEMPTS` случайным 2..5 — константа должна читаться в момент вызова, не дефолтом аргумента.
- AC-9 запускает существующий `SendAfterCommitTest.test_refusal_…` через `unittest.defaultTestLoader.loadTestsFromName`.
- Стаб реализации: все 19 тестов зелёные, стаб откачен (`git checkout`).

## Не сработало
- Долгоживущий файл в tests/: guard запрещает импорт `orchestrator.artifact_branch`/`gitcmd` в долгоживущих (`scripts/guard.py::_GIT_MODULES`, признак «git-модуль») — предмет задачи, поэтому всё ушло в разовую группу.

## Где остановился
- plank-run: 11 failed / 8 passed (краснота ожидаемая), preflight — все проверки пройдены.

## Чего не хватило
- Что `artifact_branch` целиком запрещён в долгоживущих, выяснилось только по preflight; в скиле сказано лишь «ни gitcmd/artifact_branch» среди фактов задачи.
