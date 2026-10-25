---
task: 01M5T79C5GFJGQ9XCTH8W0PDFQ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/gitcmd.py, orchestrator/acceptance.py, orchestrator/brief.py, orchestrator/reference_cache.py, orchestrator/tz_check.py, orchestrator/advance_gates/outcome_integrity.py, tests/
budget_usd: 40
---

# SPEC: Скорость пульта, git 3: чтения git из клона проекта и рабочей копии — через orchestrator/gitcmd.py

## Контекст
Очередь скорости, решение Оператора от 24.10.2026: git 1, 5 и 2 уже смержены. Задача git 3 нужна для git 4 — памяти чтений git в контексте команды пульта (~12–16 % вызовов). Память можно повесить только на одну точку запуска git, а семь чтений сейчас идут мимо `orchestrator/gitcmd.py` прямым `subprocess` (сверка 25.10, пин 7e0c636c). Сама git 3 скорости почти не даёт: это перенос без смены поведения.

Чтения мимо `gitcmd` (номера мест ниже — эти):
1. `orchestrator/acceptance.py::suite_tree_hash`, вложенная `git()` — `read-tree`/`add -u`/`rm --cached`/`write-tree` через `subprocess.Popen(["git", "-C", <root>, …])` + `communicate(timeout=15)`, своё окружение `GIT_INDEX_FILE`; истечение срока → `None`; `OSError` запуска не ловится и выходит из `suite_tree_hash` (`acceptance.py:2944`, `Popen` вне `try`).
2. `orchestrator/brief.py::_clone_git` — `ls-tree -z`, `show`; вывод байтами; срок `config.CORE_REFERENCE_GIT_TIMEOUT_SEC`; истечение срока или `OSError` → `(None, "git не ответил (<имя исключения>)")`.
3. `orchestrator/reference_cache.py::branch_commit` — `rev-parse --verify --quiet`; срок `config.CORE_REFERENCE_GIT_TIMEOUT_SEC`; истечение срока → `(None, "git не ответил (TimeoutExpired)")`.
4. `orchestrator/reference_cache.py::_list_tree` — `ls-tree -r -l -z`, потоковое чтение `Popen` порциями `LISTING_CHUNK` с пределом `config.CORE_REFERENCE_MAX_LISTING_BYTES` и остановкой по остатку дедлайна; перебор предела → `_Failure(OVER_LIMITS, …)`, истечение срока при чтении → `_Failure(DEADLINE, "срок исчерпан на ls-tree")`; `OSError` или `TimeoutExpired`, поднятые при запуске процесса, → `_Failure(SOURCE_FAILED, "ls-tree: <имя исключения>: <текст>")` (`reference_cache.py:355-356`), не `DEADLINE`.
5. `orchestrator/reference_cache.py::_cat_blobs` — `cat-file --batch`, вход байтами; срок — остаток дедлайна; истечение срока → `_Failure(DEADLINE, "срок исчерпан на cat-file")`.
6. `orchestrator/tz_check.py::_git`/`_git_ok` — `ls-tree`, `show`, `grep`, `rev-parse`; вывод байтами; срока нет.
7. `orchestrator/advance_gates/outcome_integrity.py::_added_lines` — `diff … -M -U0`; вывод байтами; срока нет.

В `gitcmd` уже есть `git`, `in_repo`, `carpentry` (своё окружение, вход, байтовый вывод) и `pult_env`. Срока (`timeout`, `TimeoutExpired`) и потокового чтения с пределом в нём нет.

Выбор, который ТЗ (требование 2) оставило аналитику: потоковое чтение с пределом байт и остановкой по сроку становится функцией `gitcmd`. Чтение порциями, предел и остановку по сроку ведёт `gitcmd`, а `_list_tree` переводит её исход в свои `_Failure`. Тогда у git 4 одна точка запуска и для потокового чтения.

Как места видны подменам тестов сейчас (решение Оператора на гейте SPEC 26.10 — эту видимость перенос сохраняет): места 1 и 4 идут через `subprocess.Popen` и шпиону `SpyRun` (`tests/sandbox.py:1284`; `TmpRootTest` ставит его на глобальный `subprocess.run`, `sandbox.py:1682`) не видны. Места 2, 3, 5, 6, 7 идут через глобальный `subprocess.run` и видны и `SpyRun`, и шпионам `subprocess.run` существующих тестов (`tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py:236-250`, `tests/test_outcome_gate_module.py:2525` — последний обращается к атрибуту `outcome_integrity.subprocess`).

## Требования

1. Все семь мест запускают git через функции `orchestrator/gitcmd.py`. В модулях `orchestrator/acceptance.py`, `orchestrator/brief.py`, `orchestrator/reference_cache.py`, `orchestrator/tz_check.py`, `orchestrator/advance_gates/outcome_integrity.py` не остаётся прямого запуска git через `subprocess` (`subprocess.run`, `subprocess.Popen`). Локальные обёртки модулей (`acceptance._launch`, `acceptance._run_capture`) для этих мест не используются. Импорт `subprocess` в `orchestrator/advance_gates/outcome_integrity.py` сохраняется (его читает `tests/test_outcome_gate_module.py:2525`); запрет касается запуска git, не импорта.
2. В `gitcmd` добавляется то, чего этим местам не хватает, без смены их поведения:
   - срок выполнения. Истечение срока — именованный отказ, по которому вызывающий отличает истечение срока от прочих отказов; `subprocess.TimeoutExpired` наружу из `gitcmd` не выходит;
   - потоковое чтение вывода с пределом байт и остановкой по сроку (для места 4). Процесс git останавливается и при переборе предела, и при истечении срока. Перебор предела, истечение срока и ненулевой код возврата — три различимых исхода;
   - байтовый вывод и байтовый вход;
   - своё окружение (`GIT_INDEX_FILE` места 1) — равноценной функцией `gitcmd` на `subprocess.Popen` со сроком 15 с и теми же аргументами (`-C <root>`). `gitcmd.carpentry` для места 1 не используется (у неё нет срока, вместо `-C` — `cwd`, и она идёт через `subprocess.run`, который перехватывает `SpyRun`).
3. Поведение семи мест не меняется:
   - те же аргументы git;
   - тот же репозиторий (`-C <клон>` или рабочая копия);
   - то же окружение (маркер `pult_env` и, у места 1, `GIT_INDEX_FILE`);
   - те же значения срока: 15 с у места 1, `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` у мест 2–3, остаток дедлайна у мест 4–5. У мест 6–7 срок не появляется;
   - те же коды отказа и тексты причин, в том числе при истечении срока и при отказе запуска (`OSError`) там, где место его сейчас ловит. У места 1 `OSError` запуска по-прежнему выходит исключением из `suite_tree_hash` (не `None`). У места 4 `TimeoutExpired` при запуске процесса по-прежнему даёт `_Failure(SOURCE_FAILED, "ls-tree: TimeoutExpired: …")`, не `DEADLINE`;
   - то же число процессов git (тесты считают процессы шпионом `subprocess.Popen`).
4. Под каждой подменой существующих тестов результат каждого из семи мест тот же, что до переноса. Подмены:
   - `mock.patch.object(gitcmd, "git", fake_git)` (`tests/sandbox.py:2173` и десятки файлов `tests/`) и заглушки `gitcmd.in_repo`, `gitcmd.show`, `gitcmd.ls_tree_files` в `tests/sandbox.py::LightTransitionSandbox`. Перенос идёт через функции `gitcmd`, которые эти подмены не задевают, либо в PLAN по коду доказано, что ни один такой тест не исполняет перенесённое место;
   - шпион глобального `subprocess.run` `tests/sandbox.py::SpyRun` (отвечает фейковым sha на `write-tree`/`hash-object`, `sandbox.py:1375`) и шпионы `subprocess.run` существующих тестов. Места 1 и 4 не переходят на путь, который перехватывает `SpyRun`. Места 2, 3, 5, 6, 7 остаются на пути, который видят `SpyRun` и шпионы `subprocess.run`, как сейчас; путь места 7 остаётся видимым подмене `outcome_integrity.subprocess.run` (`tests/test_outcome_gate_module.py:2525`).

   Тихое изменение поведения существующих тестов — дефект.
5. Новый долгоживущий тест-сторож отдельным файлом задачи в `tests/` (по образцу `tests/test_invariants.py::CarpentryGitCallsGoThroughGitcmdTest`, без правки `tests/test_invariants.py`). Он проверяет, что в пяти модулях требования 1 нет прямого запуска git через `subprocess`; сам импорт `subprocess` он не запрещает.

## Критерии приёмки

AC-1. В модулях `orchestrator/acceptance.py`, `orchestrator/brief.py`, `orchestrator/reference_cache.py`, `orchestrator/tz_check.py`, `orchestrator/advance_gates/outcome_integrity.py` нет вызова `subprocess.run`/`subprocess.Popen` с git. На каждое из семи мест «Контекста» есть поведенческий тест: место вызывает функцию `orchestrator/gitcmd.py`, и других запусков git при этом нет. Обёртки `acceptance._launch`/`acceptance._run_capture` для этих мест не используются.

AC-2. Долгоживущий тест-сторож — отдельный файл задачи в `tests/`, `tests/test_invariants.py` не меняется. Сторож зелёный на коде задачи. Он краснеет при возврате любого из семи мест на прямой `subprocess.run`/`subprocess.Popen` с git. Импорт `subprocess` в модулях (в том числе в `orchestrator/advance_gates/outcome_integrity.py`) сторож не запрещает.

AC-3. Существующие тесты этих мест зелёные без правки:
- `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py`, в том числе тесты у строк `:296`, `:323`, `:334`, `:510`, `:971`;
- `tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py`;
- `tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py`, в том числе `:236`, `:538`, `:554`;
- `tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py:547`;
- `tests/test_outcome_gate_module.py:2525`;
- `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py:208`.

AC-4. Истечение срока внутри `gitcmd` даёт у каждого из пяти мест со сроком прежний именованный отказ, и `TimeoutExpired` наружу не выходит. Каждое место проверяет свой тест:
- место 1, `suite_tree_hash` → `None`;
- место 2, `_clone_git` → `(None, "git не ответил (TimeoutExpired)")`;
- место 3, `branch_commit` → `(None, "git не ответил (TimeoutExpired)")`;
- место 4, `_list_tree`, срок истёк при чтении вывода → `_Failure` с кодом `DEADLINE` и причиной `"срок исчерпан на ls-tree"`; `TimeoutExpired` при запуске процесса → `_Failure` с кодом `SOURCE_FAILED` и причиной `"ls-tree: TimeoutExpired: <текст>"`, не `DEADLINE`;
- место 5, `_cat_blobs` → `_Failure` с кодом `DEADLINE` и причиной `"срок исчерпан на cat-file"`.

AC-5. Значения срока прежние: 15 с у места 1, `config.CORE_REFERENCE_GIT_TIMEOUT_SEC` у мест 2 и 3, остаток дедлайна у мест 4 и 5. Места 6 и 7 запускают git без срока, как сейчас.

AC-6. Место 4 читает вывод `ls-tree` потоком через функцию `gitcmd`:
- вывод больше `config.CORE_REFERENCE_MAX_LISTING_BYTES` даёт прежний `_Failure(OVER_LIMITS, "вывод ls-tree > <предел> байт")`, процесс git остановлен, вывод сверх предела не накапливается;
- ненулевой код возврата даёт прежний `_Failure(SOURCE_FAILED, "ls-tree <sha>: код <код>")`.

AC-7. У каждого из семи мест прежние:
- аргументы git;
- репозиторий (`-C <клон>` или рабочая копия);
- окружение (маркер `pult_env`; у места 1 — `GIT_INDEX_FILE` временного индекса);
- байтовый или текстовый тип вывода и входа;
- число процессов git, посчитанное шпионом `subprocess.Popen`.

AC-8. Отказ запуска git (`OSError`) даёт прежний исход у каждого места:
- место 1 → исключение выходит из `suite_tree_hash`, результат не `None`;
- место 2 → `(None, "git не ответил (<имя исключения>)")`;
- место 3 → `(None, "git не ответил (<имя исключения>)")`;
- место 4 → `_Failure(SOURCE_FAILED, "ls-tree: <имя>: <текст>")` (тот же исход и у `TimeoutExpired` при запуске, AC-4);
- место 5 → `_Failure(SOURCE_FAILED, "cat-file: <имя>: <текст>")`;
- место 6 → результат с кодом `127` и текстом исключения в `stderr`;
- место 7 → `_Prepare` с прежним текстом `"diff -M -U0 базы … и головы … не получен: …"`.

AC-9. Под каждой подменой из требования 4 результат каждого из семи мест тот же, что до переноса:
- `gitcmd.git` → `fake_git` и заглушки `gitcmd.in_repo`/`show`/`ls_tree_files` песочницы `LightTransitionSandbox`: перенесённое место не уходит в эти заглушки (альтернатива — доказательство в PLAN по коду, что ни один тест под этой подменой место не исполняет);
- шпион глобального `subprocess.run` (`SpyRun`): места 1 и 4 не переходят на путь, который он перехватывает (под `SpyRun` `write-tree` места 1 не получает фейковый sha);
- места 2, 3, 5, 6, 7 остаются на пути, который видят `SpyRun` и шпионы `subprocess.run`, как сейчас; место 7 видно подмене `outcome_integrity.subprocess.run`.

## Оценка объёма и деление

Сработавшие сигналы:
- в зоне 6 модулей и `tests/` — порог 5 превышен;
- `budget_usd` = 40 при пороге $30.

Прогноз диффа мал: по месту — десяток–три десятка строк, в `gitcmd` — две-три функции, плюс один файл сторожа и тесты AC-4/AC-6/AC-8.

**Обоснование монолита** (материал для решения Оператора). Технически перенос режется по модулям: часть 1 — функции `gitcmd` со сроком и потоковым чтением вместе с местами 3–5 (`reference_cache.py`); часть 2 — места 1, 2, 6, 7. Доводы против деления:
- сторож AC-2 одним файлом охватывает все пять модулей. В части 1 он был бы красным до мержа части 2, либо его пришлось бы делить на два файла с последующей сшивкой;
- git 4 (память чтений) нужна вся семёрка мест в одной точке, а частичный перенос ей ничего не даёт;
- деление удваивает постоянную цену задачи (analyst, аудит, test_author, ревью — ~$14 на часть), что сравнимо со всей задачей.

Рамка ТЗ — $40; ставка не выше её. Если Оператор предпочтёт нарезку — две части в порядке выше: «часть 1, без зависимостей», «часть 2, после части 1».

## Не входит

- `orchestrator/checkpoint.py:1941` `_main_copy_status`: намеренно вне `gitcmd.git` — не должен попадать в сверяемую тестами последовательность вызовов шага.
- Клоны канарейки `orchestrator/canary.py:1189–1208`.
- `orchestrator/stack.py:383`, `:611` и `orchestrator/agent_log.py:48` — проверки версии и корня главной копии.
- `orchestrator/plank_helper.py`: копируется в планку как `_pult.py` и по контракту не импортирует `orchestrator`.
- `orchestrator/doctor/project_checks.py:448`.
- `gitcmd.check_ignore`.
- `scripts/` — там отдельные процессы.
- Память чтений git — это задача git 4.
- Правка существующих тестов: любая такая правка — эскалация до SPEC с перечнем тестов и предлагаемой правкой, мандат даёт только Оператор. Раздела «Меняемое поведение» нет.
- Только чтение: `tests/sandbox.py`, `tests/test_invariants.py`, `docs/invariants.md`, `orchestrator/config.py`.
- Срок для мест 6 и 7 не добавляется — у них его сейчас нет (требование 3).
- Полный набор `tests/` зелёный — эту проверку держит пульт.

## Материалы

- ТЗ: `tasks/01M5T79C5GFJGQ9XCTH8W0PDFQ/TZ.md`.
- Образец сторожа: `tests/test_invariants.py::CarpentryGitCallsGoThroughGitcmdTest` (`:1879`).
- Песочница: `tests/sandbox.py::LightTransitionSandbox` — подмены `gitcmd.git`, `in_repo`, `show`, `ls_tree_files`; `tests/sandbox.py::SpyRun` (`:1284`, ответы на плотницкие команды `:1370–1379`) — подмена `gitcmd.subprocess.run` в `TmpRootTest`.
- Существующая функция со своим окружением: `orchestrator/gitcmd.py::carpentry` (`:339`) — для места 1 не годится (требование 2).
- Аудит SPEC и решения Оператора на гейте SPEC 26.10: `tasks/01M5T79C5GFJGQ9XCTH8W0PDFQ/SPEC-AUDIT.md`, «Вердикт» пп. 1–6.
- Явный репозиторий у примитивов `gitcmd`: `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py:208` (AC-3) — касается и новых функций `gitcmd`.
