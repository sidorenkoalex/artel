---
task: 01M4S0JVB85W9TY1ESGNBH97FP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Карточки знаний — формат, хранение, проверка формы, doc-commit (К-4а)

## Подход

Новый модуль `orchestrator/knowledge_cards.py` с публичным интерфейсом
требования 17 (`SYSTEM`/`PROJECT`, восемь кодов `REFUSAL_CODES`, исходы
`CARDS`/`NOT_SET_UP`/`REFUSED`, `SAMPLE`, frozen `Card`/`Refusal`/
`KindRead`/`QueryRefusal`, `check_text`, `read_cards`, `match`) плюс два
служебных помощника для `doc-commit`: `is_card_file(rel)` и
`refusal_text(refusal)` (строка отказа с файлом/карточкой/полем/строкой/
кодом/подробностью для вывода команды).

Ключевые решения:

1. **Порядок проверки формы** (`check_text`): сначала `yamlmini.mapping`
   (сбой — «файл не разобран»), затем построчный проход `_line_pass`
   (неизвестный раздел, отступ ≠ 0/2/4, повтор ключа на отступе 2 и поля
   на отступе 4; ключ строки — текст до первого `:` с обрезкой пробелов,
   ровно как у `yamlmini`), затем значения: раздел `cards`, предел числа
   карточек, по карточкам в порядке файла — форма ключа, отображение,
   неизвестное поле, обязательные `where`/`rule`/`why`, значения полей,
   предел размера. Проход заодно отдаёт номера строк ключей и полей — их
   несут отказы значений. Пределы читаются из `config` в момент вызова.
2. **Чтение `knowledge/` пульта** — `_read_main`: нет `.git` в
   `config.ROOT` (ни каталогом, ни файлом — `Path.exists()`) — «не
   заведён»; `gitcmd.in_repo(ROOT, "ls-tree", "--name-only", MAIN_BRANCH,
   "--", rel)` — `None`/ненулевой код — «git не ответил», пусто — «не
   заведён»; затем `gitcmd.show`. Так читаются системный файл и проектный
   файл артели (`knowledge/<имя>.yaml`).
3. **Чтение проектного файла внешнего проекта** — `_read_disk`:
   `repo_context.projects_root()`; `NO_AREA` — «не заведён» до любого
   обращения к диску; `os.lstat` — нет файла — «не заведён»; ссылка или не
   обычный файл — «файл не прочитан» (FIFO не открывается); путь по
   `resolve(strict=True)` обязан равняться `projects_root().resolve() /
   <проект> / knowledge / <имя>` (каталог знаний-ссылка в чужой проект или
   наружу — отказ); чтение `os.open(O_NOFOLLOW|O_NONBLOCK)` + `fstat`,
   строгий UTF-8.
4. **`targets.yaml`**: `targets.check` проверяет необязательное поле
   `knowledge` (`_knowledge_error`): не строка, `..`-сегмент, `//`, `\`,
   префикс `./`, без `.yaml`; у `config.DEFAULT_TARGET` — ровно
   `knowledge/<имя>.yaml` и не `knowledge/system.yaml`; у прочих — ровно
   `.artel/projects/<своё имя>/knowledge/<имя>.yaml`. Имя файла —
   `targets.KNOWLEDGE_FILE_NAME` (`[A-Za-z0-9_][A-Za-z0-9_.-]*\.yaml`, один
   уровень); его же использует `knowledge_cards.is_card_file`.
   `read_cards` берёт поле через `targets.target` с перехватом
   `TargetsError` (нет файла, не разобран, запись негодна — проектных
   карточек нет).
5. **`doc-commit`**: `_doc_commit_path_refusal` пропускает
   `knowledge/<имя>.yaml` (не через `DOC_COMMIT_CONFIG_PATHS` — гейт
   полного набора не заводится); `_doc_commit_prefix` даёт `knowledge`;
   проверка формы — в `_doc_commit_request` до `_run` (общая точка
   `cmd_doc_commit` и `doc_commit_content`; на ветке отказа `fetch`
   `_build_doc_commit` не вызывается, а запись удерживается). Вид для
   проверки — `SYSTEM` у `knowledge/system.yaml`, иначе `PROJECT` (на
   форму не влияет).
6. **Циклы импорта**: `brief` импортируется внутри `_from_text`,
   `project_profile.mask_matches` — внутри `_element_matches`; верхний
   уровень модуля — только `config`, `gitcmd`, `repo_context`, `targets`,
   `yamlmini` (ни один не тянет `notes`).
7. **Защищённый путь**: `"knowledge/"` — последней записью в самом
   литерале `PROTECTED_PATHS` (19 записей). Восемь констант
   `KNOWLEDGE_CARD_*` — одним блоком в конце `config.py` с комментарием о
   лимитах класса ADR-0002.

Бюджет SPEC ($45) не переоценивается.

## Шаги

1. `orchestrator/knowledge_cards.py` — формат, проверка формы, чтение по
   видам, сверка места (требования 1–4, 7–10, 17).
2. `orchestrator/config.py` — блок констант `KNOWLEDGE_CARD_*`, запись
   `knowledge/` в `PROTECTED_PATHS` (требования 5, 11).
3. `orchestrator/targets.py` — поле `knowledge` в `targets.check`
   (требование 6).
4. `orchestrator/notes.py` — путь, префикс и проверка формы `doc-commit`
   (требование 12).
5. Тесты: смена ожидания `test_protected_test_settings.py` 18 → 19 с
   docstring (раздел «Меняемое поведение»); свой `tests/test_knowledge_cards.py`
   на свойства, не покрытые долгоживущими файлами задачи (строка отказа
   `refusal_text`, отступ 6, допуск пути `doc-commit` с формой имени);
   регенерация `docs/codebase-map.md` (требования 14, 15).
6. Приложение к `targets.yaml` (ниже) — накладывает Оператор (требование 16).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 2 |
| 5 | 2 |
| 6 | 3, 1 |
| 7 | 1 |
| 8 | 1 |
| 9 | 1 |
| 10 | 1 |
| 11 | 2, 5 |
| 12 | 4 |
| 13 | 1, 4 |
| 14 | 5 |
| 15 | 5 |
| 16 | 6 |
| 17 | 1 |

Проверено в шаге:
- долгоживущие файлы задачи (`tests/test_01m4s0jvb85w9ty1esgnbh97fp_*.py`,
  6 файлов): 50 passed, 190 subtests passed;
- планка `artel.py plank-run 01M4S0JVB85W9TY1ESGNBH97FP`: 5 passed, код 0;
- тесты затронутых модулей (`test_protected_test_settings`, `test_doc_commit*`,
  `test_notes`, `test_ci_protected_paths`, `test_protected_paths_gate`,
  `test_project_protected_paths`, профиль тестов, `model_sets`,
  `held_base`): 164 passed; красен только сторож зеркала
  `test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py` — по построению, см.
  «Риски»; с наложенным приложением он зелёный (2 passed);
- `tests/test_knowledge_cards.py`: 3 passed; каждый метод покраснел на
  своей заявленной мутации (временная правка модуля, затем возврат);
- полный набор `artel.py suite-run` №1: 5189 passed, 1 failed, 2 skipped;
  единственное падение — тот же сторож зеркала (прогон шёл «без
  приложений PLAN»: PLAN.md ещё не был в `refs/artifacts/<id>`); новых
  падений помимо него нет.

## Влияние на систему

- Поведение шагов ролей не меняется: `knowledge_cards` импортирует только
  `notes.py` (сторож `test_01m4s0jvb85w9ty1esgnbh97fp_importers.py`);
  `read_cards`/`match` никто в пакете не зовёт.
- Перечень защищённых путей только растёт на одну запись в конце
  литерала; первые 12 и порядок прежние — джоб CI `protected-paths`
  читает литерал базы, новая запись в нём видна разбору
  `protected_paths_from_source`. Существующий тест меняет одно ожидание —
  ровно то, что названо разделом SPEC «Меняемое поведение»; срез `[:12]`
  и прочие утверждения не тронуты.
- `doc-commit`: прежние пути (`docs/**`, `DOC_COMMIT_CONFIG_PATHS`) идут
  прежней веткой; рубеж окружения роли стоит первым, как прежде; гейт
  полного набора на `knowledge/` не заводится (путь вне
  `DOC_COMMIT_CONFIG_PATHS`).
- `targets.check`: запись без поля `knowledge` проверяется как прежде;
  поле с негодной формой делает весь `targets.yaml` негодным
  (`TargetsError`) — тот же класс, что и у прочих полей записи.
- Откат — revert одного merge-коммита; приложение `targets.yaml`
  откатывается отдельно Оператором (иначе сторож зеркала покраснеет, а
  поле `knowledge` у артели останется без проверки — оно станет
  неизвестным полем, которое `targets.check` не отвергает).

## Риски

- Сторож зеркала `tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py`
  в голом `pytest` рабочей копии ветки красен до наложения приложения —
  по построению (`knowledge/` есть в `config.PROTECTED_PATHS`, но ещё нет
  в `no_paths` записи `artel`). CI ветки и гейты пульта накладывают
  приложение сами (`scripts/plan_appendix_ci.py`,
  `orchestrator/appendix_tree.py`). Прочие тесты задачи от приложения не
  зависят.
- Порядок наложения с соседней задачей ТЗ-К3 (тоже правит запись `artel`
  в `targets.yaml`): это приложение не трогает конец записи (блок
  `test_profile`), контекст хунков — шапка, строка `no_paths` и пара
  `merge_gate`/`test_profile`; при расхождении `git apply` откажет явно.
- Файл карточек артели (`knowledge/artel.yaml`) после наложения
  приложения ещё не существует — `read_cards("artel")` отдаёт проектный
  вид «не заведён», не отказ.

## Приложение: targets.yaml

Применимость проверена: `git apply --check` на чистом дереве ветки —
успешно; с наложенным патчем сторож зеркала зелёный, а
`targets.target("artel")["knowledge"] == "knowledge/artel.yaml"`.

```diff
diff --git a/targets.yaml b/targets.yaml
index 5f1b8bf9..ee9bc156 100644
--- a/targets.yaml
+++ b/targets.yaml
@@ -10,6 +10,9 @@
 #   no_paths        пути целевого, которые задачам трогать нельзя
 #   project_skills  курируемый список проектных скилов (ADR-0003 3з)
 #   merge_gate      operator | target-human — кто исполняет гейт мержа (п.7)
+#   knowledge       необязательно: файл проектных карточек знаний — у artel
+#                   knowledge/<имя>.yaml, у внешнего проекта
+#                   .artel/projects/<имя>/knowledge/<имя>.yaml
 #
 # Каталог target'а (.artel/projects/<имя>/) заводит команда
 #   python3 orchestrator/artel.py target-init <имя>
@@ -30,9 +33,10 @@ targets:
     # совпадение держит сторож tests/test_01m45fk56dwmnbrka1vwm12h19_no_paths_mirror.py.
     # Зеркало внесено в main вперёд кода задачи 01M45FK56DWMNBRKA1VWM12H19
     # (решение Оператора 06.10, коммит 09256315).
-    no_paths: [gates.yaml, roles.yaml, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py, docs/adr/, CLAUDE.md, AGENTS.md, targets.yaml, models.yaml, model_sets.yaml, **/conftest.py, pyproject.toml, pytest.ini, setup.cfg, tox.ini]
+    no_paths: [gates.yaml, roles.yaml, .github/, templates/, skills/, docs/invariants.md, tests/test_invariants.py, docs/adr/, CLAUDE.md, AGENTS.md, targets.yaml, models.yaml, model_sets.yaml, **/conftest.py, pyproject.toml, pytest.ini, setup.cfg, tox.ini, knowledge/]
     project_skills: []
     merge_gate: operator
+    knowledge: knowledge/artel.yaml
     test_profile:
       command: [python3, -m, pytest]
       long_lived_dir: tests
```

## Предложения системе

- Оболочка шага роли: `cat`, `ls` недоступны в PATH Bash-инструмента
  (`command not found`), хотя `git`/`python3`/`sed`/`grep` есть — обходил
  через `python3`. Адрес: окружение `runner.role_env`/курируемый HOME —
  стоит проверить состав PATH шага.
