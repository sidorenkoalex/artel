---
task: 01M5R45M0FQB2WVRHYBRF81JM6
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Скорость пульта, git 5: пакетное чтение документов в read_tree и один rev-parse в suite_tree_hash

# Скорость пульта, git 5: чтение документов задачи одним пакетом и один `rev-parse` в снимке дерева набора

## Факты

Решение Оператора 24.10.2026 (дословно): «Заводи рекомендованный набор: быстрая задача по full_suite_lock и doctor_duration сейчас, задачи по git 1, 5, 2, 3, 4 — по очереди между волнами; шаблон песочниц и подделку pytest — отложить.» Повод — исследование вызовов git в командах пульта 24.10 (шпион процессов на 9c0e8b8c, то есть подмена запуска процессов, считающая каждый вызов git): тест `merge_outcome_gate` делает 1332 вызова git; по оценке исследования эта задача снимает около 60 из них. Сверено с origin/main bb6e426e; файлы `orchestrator/acceptance.py`, `orchestrator/gitcmd.py`, `tests/sandbox.py`, `orchestrator/amend.py`, `orchestrator/retro.py` на пине 09ded609 и на origin/main совпадают, `orchestrator/artifact_branch.py` различается — в нём ссылки по именам функций.

- `orchestrator/artifact_branch.py`, `read_tree(task_id)`: возвращает {путь: текст} всех файлов `tasks/<id>/` ссылки документов задачи. Порядок: `task_repo` — при `_NO_REPO` пустой словарь без git; `gitcmd.ls_tree_files(branch, "tasks/<id>")` (`git ls-tree -r --name-only refs/artifacts/<id> -- tasks/<id>`, `orchestrator/gitcmd.py:761`), `None` превращается в пустой список; затем на каждый путь `gitcmd.show(branch, rel)` (`git show refs/artifacts/<id>:<путь>`, `orchestrator/gitcmd.py:611`); файл с `text is None` пропускается. Итого 1 + N вызовов git, и каждый вызов заново разрешает имя ссылки: если ссылка сдвинулась во время чтения, словарь собирается из двух разных коммитов.
- Свойства прежнего чтения, проверенные на git 2.50.1 (временный репозиторий в scratchpad):
  - текст получается текстовым режимом `subprocess` (кодировка по умолчанию, строгая): `\r\n` и одиночный `\r` превращаются в `\n`; байты не в UTF-8 дают `UnicodeDecodeError`, `gitcmd.show` отвечает `(None, "не прочитан: …")`, файл выпадает из словаря; файл с нулевыми байтами, но в UTF-8, входит как есть;
  - `ls-tree` без `-z` берёт в кавычки пути с не-ASCII символами и табуляцией (`"tasks/T/\320\270\320\274\321\217.md"`); `show` с таким путём отказывает (`fatal: path … does not exist`) — такие файлы прежний `read_tree` пропускает;
  - символическая ссылка (режим 120000) читается как текст цели ссылки;
  - запись подмодуля (режим 160000): `git show <rev>:<путь>` печатает коммит с diff, если этот коммит есть в репозитории, иначе отказывает;
  - `git show <rev>:<путь>` не применяет `textconv` из `.gitattributes`, `git cat-file --batch` — тоже.
- Вызывающие `read_tree`: `orchestrator/amend.py:121` (`_materialize_tests_if_missing`), `:145` (`_materialize_spec_if_missing`), `:449` (`_artifact_tests_snapshot`, кодирует текст обратно в UTF-8); `orchestrator/retro.py:265` (`_artifact_branch_files` → `build_done`, `build_killed` — строки «Суть» и «Приёмочные тесты»). Все ждут словарь, пустой словарь — «ссылки нет или git не ответил». `tests/test_retro.py:169` подменяет `artifact_branch.read_tree` по имени — имя и сигнатура должны остаться.
- Лёгкие песочницы подменяют `gitcmd.show` и `gitcmd.ls_tree_files` чтением с диска (`tests/sandbox.py:2177`–`2181`, `disk_backed_show` `:821`, `disk_backed_ls_tree_files` `:850`; так же вручную ещё около 25 файлов тестов), а `rev-parse --verify` для `refs/artifacts/` в них отказывает (`_ABSENT_REF_PREFIXES`, `tests/sandbox.py:1268`; `fake_git` `:1453`, `SpyRun` — там же ниже). Через `cmd_kill` и слияние (`retro.build_killed`/`build_done`) лёгкие песочницы доходят до `read_tree` и сейчас получают файлы с диска. Если новое чтение обойдёт эту пару, содержимое RETRO в этих песочницах изменится.
- Образец пакетного чтения уже есть: `orchestrator/reference_cache.py` (`_cat_blobs`, один `cat-file --batch`, разбор ответа `<oid> <тип> <размер>` / `missing`). Запуск процесса с входом есть в `gitcmd.carpentry(repo, args, env, *, input=None, text=True)` (`orchestrator/gitcmd.py:339`); `gitcmd.git`/`gitcmd.in_repo` вход не принимают.
- `orchestrator/acceptance.py:2905`, `suite_tree_hash(root, *, ref="HEAD", base=False, worktree=True)` → sha дерева или `None`: `rev-parse --show-toplevel` (`:2909`), сверка с `root`; при `worktree=True` — `ls-files --others`, затем второй `rev-parse --path-format=absolute --git-path index` (`:2924`) и копия индекса. Один вызов `git rev-parse --show-toplevel --path-format=absolute --git-path index` печатает обе строки (проверено). Вызывающие: `acceptance.py:3250`, `:3309`, `:3423`, `:3424` (`worktree=False`), `orchestrator/suite_run.py:592` (`worktree=False`); все ловят `OSError`, `ValueError`, `TypeError`, `AttributeError`, `TimeoutExpired`.
- Тексты ошибок: ни `read_tree`, ни `suite_tree_hash` их не возвращают и в журнал не пишут (причина отказа `gitcmd.show` отбрасывается, снимок отвечает `None`).
- Сверка существующих тестов на точный перечень или число вызовов git (поиск по `ls-tree`, `cat-file`, `--show-toplevel`, `--git-path`, `read_tree`, `suite_tree_hash`, заглушкам `gitcmd.git`/`in_repo`/`subprocess.run` и спискам вызовов): ни один тест не проверяет перечень или число вызовов git внутри `read_tree` или `suite_tree_hash`. Проверено и правки не требует:
  - `tests/test_01m4s24963r9h18an2xdp6r15b_cache.py:297`–`331`, `:505`, `:551` — считает `ls-tree`/`cat-file`, но для `reference_cache`, не затрагивается;
  - `tests/test_amend.py:160` — заглушка `ls-tree`/`show` для `amend._branch_tests_snapshot`, не `read_tree`;
  - `tests/test_retro_corpus.py:53` — заглушка `in_repo` для `retro_corpus._retro_entry`;
  - `tests/test_review_package_map.py:78`, `tests/test_review_package.py` (заглушка `ls-tree`) — пакет ревью, не `read_tree`;
  - `tests/test_kill_cleanup.py:476` (все `ls-tree` отказывают во время `cmd_kill`) и `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py:174` (то же через `subprocess.run`) — при требовании 1в исход прежний: пустой словарь;
  - `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py:440`, `:545` — отказ `ls-tree` только для файлов блокировки, путь `tasks/<id>` под условие не попадает;
  - `tests/test_retro.py:169`, `tests/test_acceptance.py:448`, `tests/test_task_component_places.py:270`, `tests/test_01m4begqavvwchfcw6bebb0xvt_ci_acceptance.py:84`, `:242` — подменяют саму `read_tree`/`suite_tree_hash` целиком;
  - лёгкие песочницы с `disk_backed_show`/`disk_backed_ls_tree_files` (`tests/sandbox.py:2177`, `tests/test_invariants.py:223`, `tests/test_auto_cycle.py:246`, `tests/test_task_id_prefix_regression.py:163` и другие) — при требовании 1а идут прежним путём; проверок строк «Суть»/«Приёмочные тесты» в них нет (такие проверки есть только в песочницах с настоящим git: `tests/test_retro_artifact_branch_reads.py`, `tests/test_snapshot_closing_outcome.py`, `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py:536`, `tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py:2545`) — они и служат сторожами равенства.
- Перечень правок существующих тестов, требующих мандата Оператора: пуст.
- Параллельно идут волны сведения тестов; их ТЗ требуют повторить таблицу мутаций «до», если подтяжка main изменила `orchestrator/` — изменение этой задачи это вызовет.

## Требования

1. `read_tree(task_id)` читает документы задачи не более чем тремя вызовами git при любом числе файлов, из одного коммита, с прежним результатом:
   а) Голова ссылки разрешается один раз (`_head`). Пустая строка (ссылки нет, git не ответил, заглушка отказала) — прежний путь целиком: `gitcmd.ls_tree_files(branch, …)` и `gitcmd.show(branch, rel)` по файлам, как сейчас. Так лёгкие песочницы с подменой этой пары читают диск по-прежнему.
   б) Голова есть — один `ls-tree -r <sha> -- tasks/<id>` с режимом, типом и oid записи (через `gitcmd.in_repo`/`_git`), затем один `git cat-file --batch` по oid всех записей-blob (через `gitcmd.carpentry` с `input`, `text=False`; прямой `subprocess` в `artifact_branch.py` не добавляется). Нет ни одной записи-blob — `cat-file` не запускается.
   в) Отказ `ls-tree` на sha — прежний путь целиком (как в 1а).
   г) Запись не-blob (подмодуль), путь в кавычках, oid с ответом `missing`, оборванный или неразобранный ответ, ненулевой код или `OSError` у `cat-file` — для затронутых путей чтение `gitcmd.show(<sha>, rel)` по одному, как раньше; путь в кавычках при этом даёт прежний отказ и выпадает из словаря.
   д) Байты blob превращаются в текст так же, как текстовый режим `subprocess.run` (та же кодировка по умолчанию, строгий режим, `\r\n` и `\r` → `\n`); ошибка декодирования — файл выпадает, остальные остаются.
   е) Результат байт в байт равен прежнему для неподвижной ссылки: тот же набор ключей в том же порядке (порядок `ls-tree`), те же тексты; `_NO_REPO` и пустой каталог — пустой словарь; имя, сигнатура и строка документации о возвращаемом значении `read_tree` не меняются; вызывающие (`amend.py`, `retro.py`) не меняются.
2. `suite_tree_hash`: первый вызов — один `git rev-parse --show-toplevel --path-format=absolute --git-path index`; первая строка — корень для прежней сверки с `root`, вторая — путь индекса для копии при `worktree=True`; второго `rev-parse` нет. Ответ не из ровно двух строк при коде 0 — прежние два вызова. Ненулевой код или `None` — `None`, как раньше. Возвращаемые значения при `worktree=True/False`, `base`, `ref` и все исходы `None` — прежние; остальной код функции и `_with_tree_db_files` не меняются.
3. Тесты — новый файл `tests/test_<id>_batched_reads.py` в стиле pytest (ADR-0027); в документации каждой функции — «Ловит мутацию:». Песочница — настоящий git (`tests/sandbox.py`, `tests/fixtures.py`). Эталон — прежняя реализация `read_tree` и прежнее начало `suite_tree_hash`, перенесённые в файл теста дословно.
   а) Равенство с эталоном для `read_tree` на нескольких деревьях ссылки: обычные текстовые файлы; вложенные каталоги; пустой каталог задачи; ссылки нет; `_NO_REPO`; файл с `\r\n` и одиночным `\r`; файл не в UTF-8; файл с нулевыми байтами; крупный файл (больше 1 МБ); символическая ссылка; путь с не-ASCII символами и с табуляцией; запись подмодуля (коммит есть и коммита нет); файлы вне `tasks/<id>/` рядом.
   б) Гонка: ссылка сдвигается на другой коммит между `ls-tree` и `cat-file` и между разрешением головы и `ls-tree` (подмена `gitcmd.carpentry`/`gitcmd.in_repo`, делающая `update-ref` перед настоящим вызовом) — результат равен полному дереву одного коммита, никогда не смеси.
   в) Счёт вызовов (подмена `gitcmd.subprocess.run`, считающая argv с `git`): `read_tree` на дереве из 1, 5 и 20 файлов — не больше трёх вызовов git; пустой каталог — без `cat-file`; ссылки нет — прежний путь; `suite_tree_hash(worktree=True)` — один `rev-parse`, при `worktree=False` — один.
   г) Отказы: `cat-file` с ненулевым кодом, `OSError`, оборванным ответом, ответом `missing` — результат равен эталону; отказ `ls-tree` на sha — пустой словарь, как у эталона.
   д) Равенство `suite_tree_hash` с эталоном: корень репозитория, подкаталог репозитория, каталог вне git, `worktree=False` с `ref`, `base=True`, неотслеживаемый файл вне `tasks/`, заглушка `in_repo`, отвечающая одной строкой.
4. Число вызовов: в PLAN — счёт вызовов git всего и по подкомандам `show`, `ls-tree`, `cat-file`, `rev-parse` на тесте `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py::Ac5ProofMismatchTest` (или его наследнике после сведения) до и после (шпион процессов во временной копии; файл тестов не меняется).
5. Существующие тесты не правятся и остаются зелёными. Перечень правок по мандату пуст; покраснел существующий тест — эскалация с его именем и причиной, не правка.

Зоны: orchestrator/artifact_branch.py, orchestrator/acceptance.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `orchestrator/artifact_branch.py` — только `read_tree` и новые закрытые помощники рядом с ней; в `orchestrator/acceptance.py` — только начало `suite_tree_hash` (вызовы `rev-parse`); в `docs/codebase-map.md` — только строки, отражающие новые помощники; в `tests/` — только новые файлы.

Только чтение: orchestrator/gitcmd.py, orchestrator/amend.py, orchestrator/retro.py, orchestrator/snapshot.py, orchestrator/suite_run.py, orchestrator/reference_cache.py, tests/sandbox.py, tests/fixtures.py, tests/test_retro.py, tests/test_retro_artifact_branch_reads.py, tests/test_kill_cleanup.py, scripts/guard.py.

Не входит: прочий код orchestrator/ вне зон; документы tasks/ задач; `materialize_task_dir` и `acceptance.materialize_from_branch` (тот же приём «`ls-tree` и `show` по файлам», отдельная задача); `gitcmd.show`, `gitcmd.ls_tree_files` и прочие примитивы `gitcmd`; лёгкие песочницы `tests/sandbox.py`; одна проверка `origin` (git 1, смержена); одна отправка документов на команду (git 2); перевод прямых вызовов git в `gitcmd` (git 3); память чтений в контексте команды (git 4); изменение `doctor`.

Бюджет: $40.

## Уточнения по независимой проверке 25.10 (обязательны; при расхождении с текстом выше действуют они)

1. Требование 1, число вызовов: при существующей ссылке и только обычных файлах (blob, путь без кавычек) — не более трёх вызовов git при любом их числе; в запасных путях 1а/1в/1г — прежнее чтение по файлам плюс один `rev-parse --verify` ссылки; при отсутствующей ссылке — два вызова вместо прежнего одного (принято).
2. Требование 1б: `git ls-tree -r <sha> -- tasks/<id>` без `-z`, `-l`, `--name-only`; строка разбирается как `<режим> SP <тип> SP <oid> TAB <путь>`.
3. Требование 1в: отказ `ls-tree` на sha, `None` или хотя бы одна строка, не разобранная по формату п. 2, — прежний путь целиком (как в 1а).
4. Требование 1б, `cat-file --batch`: через `gitcmd.carpentry` с `env=dict(os.environ)` (как `update-ref --stdin` в `_sync_local_ref`), `input` — байты `"<oid>\n"` на каждую запись.
5. Требование 1д, перевод байтов в текст: `data.decode(io.TextIOWrapper(io.BytesIO()).encoding)` (кодировка текстового режима `subprocess`), строгий режим, затем `.replace("\r\n", "\n").replace("\r", "\n")`; BOM не снимается; ошибка декодирования — файл выпадает, как прежде.
6. Требование 3г: подмена отказывает всем `ls-tree` — результат равен эталону (пустой словарь), и вызван прежний `gitcmd.ls_tree_files` по имени ссылки.
7. Требование 3а дополняется случаями: два файла с одинаковым содержимым (один oid), пустой файл, файл с BOM, `core.quotePath=false` (не-ASCII путь входит в словарь у эталона и у новой версии); при `core.quotePath=false` и пути не в UTF-8 текстовый `ls-tree` бросает `UnicodeDecodeError` в обеих версиях — сохраняемое поведение.
8. Требование 2 (`suite_tree_hash`): ответ — ровно две строки по `stdout.splitlines()`, каждая с `.strip()`; иначе прежние два вызова.
9. Тест гонки 3б проверяет только основной путь; в запасных путях гонка остаётся прежней.
10. Факт урока git 1: в лёгких песочницах прежний путь даёт на один записанный вызов git больше (`rev-parse --verify --quiet refs/artifacts/<id>`); точный перечень argv в `tests/test_review_package.py` (`CmdRunReviewPackageTest::test_developer_step_has_no_package`) через `read_tree` не проходит — оба `ls-tree … tasks/<id>` там из других читателей; не затрагивается. Моделирование 25.10: 11 файлов тестов, вызывающих `read_tree`, зелёные; 31 из 31 вызова совпали с прежней версией.
11. Ссылки: `def fake_git` — `tests/sandbox.py:1418`, `SpyRun` — :1284.
