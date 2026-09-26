---
task: 01M3FQ2V77QNK95Z599DM124QN
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Гейт неослабления тестов: удалённые, переименованные и ослабленные тесты отказывают на in_dev -> verifying и на гейте мержа

# ТЗ: Гейт неослабления тестов: удалённые, переименованные и ослабленные тесты отказывают на in_dev -> verifying и на гейте мержа

Источник: строка бэклога П2 от 26.09 «Гейт неослабления тестов в пульте»
(docs/backlog.md). Принцип целостности (ADR-0002, CLAUDE.md,
docs/invariants.md шапка): ослабить, отключить, заскипать или удалить
тест может только Оператор через ADR; для роли это blocker в ревью.
Сегодня принцип держится текстом и вниманием ревьюера, а на гейте мержа
сессия Оператора сверяет удалённые тесты и их число руками. Задача вне
линии провайдеров.

Факты (origin/main a24d78fc):
- Переход in_dev -> verifying: orchestrator/fsm_advance.py::in_dev
  (:469-545) зовёт гейты по одному через обёртки `_xxx_gate_refuses`;
  каркас — orchestrator/advance_gates/_base.py (`GateRefusal(action,
  detail, hint)`, `_run_gates` пишет журнал «переход отклонён: …» и
  останавливается на первом отказе). Гейт заявки мутации —
  orchestrator/advance_gates/review.py::_mutation_claim_gate (:175):
  база `gitcmd.diff_base(branch)` (merge-base с origin/main, не пин),
  файлы `gitcmd.diff_names(base, branch)` (двухточечный `--name-only`,
  без `-M`/`--name-status`), отбор `tests/test_*.py` верхнего уровня,
  сравнение base/head через guard.test_functions_without_mutation_claim
  (ast). Удалённый в head файл теста гейт сегодня МОЛЧА пропускает
  (`test_file_deleted_in_head_is_skipped`, review.py:223-253) — это и
  есть дыра: удаление файла тестов проходит переход без отказа.
- Гейт мержа: orchestrator/fsm_merge_gate.py::_protected_path_diff_gate
  (:44) — первый гейт `_cmd_approve_merge_gate` (:891), тот же
  diff_base/diff_names, при нарушении эскалация (`set_state escalated`),
  при молчании git — fail-open (обоснован докстрингом).
- Готовые узлы: guard.TEST_METHOD (scripts/guard.py:173, регулярка
  `def test_`), guard._collect_test_functions (:590, ast, модуль и
  классы, узлы с decorator_list), guard.test_functions_without_mutation_claim
  (:608 — образец сравнения base/head), dry_run.py:69 (TEST_METHOD по
  gitcmd.show). Распознавания @unittest.skip/skipIf/expectedFailure или
  pytest.mark.skip в пульте нет.
- Мандат Оператора в ANSWER: advance_gates/zones.py — строка-префикс
  «Расширение зон разрешено:» в tasks/<id>/ANSWER-n.md на ветке, с
  защитой от подделки ролью (`_answer_commit_is_role_step_autocommit`:
  автокоммит шага роли мандатом не считается, настоящий — коммит
  команды answer «<id>: ANSWER-n — ответ Оператора»). Это готовый
  механизм разрешения Оператора для гейта.
- Защищённые пути (config.PROTECTED_PATHS:632): docs/invariants.md и
  tests/test_invariants.py в списке; правка — приложением к PLAN.
  Инварианта о неослаблении tests/ в первой таблице нет; мета-инвариант
  «ослабление любой защиты — только Оператором через ADR» — во второй
  таблице. Последний номер — 37 (номер 36 занят дважды: строки 66-67).
- Тесты гейтов: tests/test_mutation_claim_gate.py (sandbox
  TaskIdSchemaConnTmpRootTest, подмена gitcmd.diff_base/diff_names/show/
  ls_tree_files через mock.patch.object, проверка колонки detail в
  steps), tests/test_fsm_advance_gate_smoke.py (журнал и stdout
  байт-в-байт), tests/test_protected_paths_gate.py.

Требуется:
1. Узел сравнения tests/ ветки с базой (один модуль, например
   orchestrator/advance_gates/test_integrity.py или функция в guard):
   по `diff_base`/`diff_names` для файлов `tests/**/*.py` находит
   (а) удалённые файлы тестов (в base есть, в head нет), (б)
   переименованные (пара удалён/добавлен с совпадающим набором имён
   тестовых методов либо `git diff -M --name-status`, способ обосновать
   в SPEC), (в) в изменённых файлах — тестовые методы, исчезнувшие из
   head (по ast: guard._collect_test_functions base против head, с
   учётом класса), (г) появившиеся декораторы пропуска или ожидаемого
   провала на тестовом методе или классе (`unittest.skip*`,
   `expectedFailure`, `pytest.mark.skip*`, `xfail`) и вызовы
   `self.skipTest(`/`pytest.skip(` в теле метода, которых не было в
   base. Тесты ниже tests/ на любой глубине (сегодня гейт мутации
   смотрит только верхний уровень — здесь глубина не ограничивается,
   обосновать). Файлы планок tasks/*/acceptance_tests не входят (их
   держит лок планки).
2. Гейт на переходе in_dev -> verifying (обёртка `_xxx_gate_refuses`
   по образцу, место — рядом с гейтом заявки мутации, порядок обосновать
   в SPEC): при любой находке — именованный отказ «переход отклонён: гейт
   неослабления тестов» с перечнем «файл: что именно (удалён /
   переименован в … / метод test_x исчез / @skip на test_y)» и
   подсказкой, как получить разрешение Оператора. Пропуски как у гейта
   мутации: канарейка и внешний target. Git не ответил — отказ
   (fail-closed, как у гейта мутации).
3. Тот же узел на гейте мержа перед `_protected_path_diff_gate` или
   сразу после него: находка без разрешения — эскалация с тем же
   текстом (образец `_protected_path_diff_gate`); поведение при
   молчании git — как у соседнего гейта, обосновать.
4. Разрешение Оператора — мандат в ANSWER-n по образцу расширения зон:
   строка-префикс «Ослабление тестов разрешено:» с перечнем путей и
   имён (`tests/test_x.py`, `tests/test_y.py::Class::test_z`) и
   ссылкой на основание (ADR либо решение Оператора); засчитывается
   только коммит команды answer, автокоммит роли — нет (тот же
   `_answer_commit_is_role_step_autocommit`). Разрешённые находки
   гейт перечисляет в журнале как «разрешено ANSWER-n», не как отказ.
   Отдельно: удаление файла тестов, целиком ставшего пустым (0 методов)
   в base, отказом не считается — обосновать в SPEC.
5. Гейт заявки мутации: молчаливый пропуск удалённого файла
   (review.py:223-253) остаётся как есть по своей семантике («нечего
   проверять на заявку»), но удаление теперь ловит новый гейт — тест
   `test_file_deleted_in_head_is_skipped` не ослабляется и не
   удаляется.
6. Приложением к PLAN (защищённые пути): docs/invariants.md — новая
   строка первой таблицы (номер 38: «удаление, переименование и
   ослабление тестов tests/ без мандата Оператора отказывает на
   in_dev -> verifying и на мерже» → тест → SPEC задачи) и добавление
   гейта в перечень рубежей in_dev -> verifying (строка 67);
   tests/test_invariants.py — инвариант, если он выражается тестом
   без живого git (иначе строка второй таблицы).
7. Документация: docs/operator-session.md — пункт о гейте мержа: сверка
   удалённых и ослабленных тестов уходит в пульт; docs/operator-gates.md
   — как выдать мандат (answer с префиксом).
8. Тесты (tests/): каждая из находок (а)–(г) даёт именованный отказ с
   файлом и именем; переименование распознаётся и называется; мандат в
   ANSWER-n коммита Оператора снимает отказ ровно по перечисленным
   именам, лишняя находка — отказ; автокоммит роли с той же строкой
   мандатом не считается; канарейка и внешний target пропускают гейт;
   git не отвечает — отказ на переходе; гейт мержа эскалирует с тем же
   текстом; существующие tests/test_mutation_claim_gate.py,
   tests/test_fsm_advance_gate_smoke.py, tests/test_protected_paths_gate.py,
   tests/test_zones_gate.py зелёные, ни один не ослаблен.

Зоны: orchestrator/advance_gates/, orchestrator/fsm_advance.py,
orchestrator/fsm_merge_gate.py, orchestrator/gitcmd.py (только новые
примитивы чтения, например `--name-status -M`), scripts/guard.py (только
новые функции ast-сравнения), docs/operator-session.md,
docs/operator-gates.md, tests/.

Приложением: docs/invariants.md, tests/test_invariants.py (защищённые
пути, применяет пульт на мерже).

Только чтение (не менять): orchestrator/answer.py (мандат читается тем
же способом, что у зон — если потребуется правка answer, вопрос
расширения зон к Оператору), orchestrator/config.py, orchestrator/
store.py, docs/adr/, docs/backlog.md, tasks/*/acceptance_tests.

Не входит: оценка «ослаблен ли ассерт» по содержимому тела теста
(семантика — ревьюеру); правка гейта заявки мутации; лок планок
acceptance_tests; ретро-проверка уже смерженных задач; изменение
PROTECTED_PATHS.

Рамка: $45.
