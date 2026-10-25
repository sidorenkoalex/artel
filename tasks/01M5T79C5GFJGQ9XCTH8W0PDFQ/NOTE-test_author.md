# Записка test_author — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- Планка: `_places.py` (шпион `subprocess.Popen` с «запускателем» — файлом первого кадра вне subprocess.py; поддельный процесс FakeProc: первый communicate/wait со сроком → TimeoutExpired; трассировка `exceptions_in` — дошёл ли TimeoutExpired до кадра места; репозиторий-фикстура), `test_routing.py` (AC-1, AC-7, AC-9), `test_failures.py` (AC-4, AC-5, AC-6, AC-8), `test_existing_tests.py` (AC-2 «test_invariants.py не тронут», AC-3). Долгоживущий сторож AC-2 — `tests/test_01m5t79c5gfjgq9xcth8w0pdfq_git_guard.py` (разбор ast пяти модулей + образцы прежних семи мест + случайные входы с зерном).
- На коде до задачи: планка 24 failed / 70 passed, сторож 5 failed / 13 passed — красные только из-за отсутствия переноса (запускатель не gitcmd.py, TimeoutExpired ловится в кадре места, сторож находит строки acceptance:2944, brief:552, reference_cache:299/352/410, tz_check:151, outcome_integrity:581).
- Проверено временным стабом (gitcmd.read_raw/popen_env/stream + перевод мест; откачен `git checkout --`): планка 94/94 и сторож зелёные; мутация «без kill» у места 1 даёт красный test_ac4_place1. preflight: все проверки пройдены.
- Строки AC-3 → методы: cache.py :296/:323/:334/:510 SourceReadingTest, :971 StatesTest; external_brief :538/:554 UnreadConventionsTest; batched_reads::test_ac5_suite_tree_hash_runs_one_rev_parse; test_outcome_gate_module::test_unexpected_header_is_prepare_refusal; explicit_repo::GitcmdWithoutRepoOnlyFromAllowListTest::test_ac8_….

## Не сработало
- Bash шага не даёт `cat`/`ls`/`rm`, `$VAR` и составные команды; скрипты — файлом, удаление — через python.
- В PATH шага нет /bin: фейковый git-скрипт зовёт /bin/sleep и /usr/bin/yes по абсолютному пути.

## Где остановился
- Шаг завершён: планка и сторож написаны и проверены, preflight пройден.

## Чего не хватило
- Что SpyRun отвечает отказом на `rev-parse --verify refs/heads/*` (место 3 под ним и до переноса даёт «ветки main нет») — выяснено только прогоном.
