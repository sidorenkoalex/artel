---
task: 01M70RZS8Q09GSHWFGANE3FHX7
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/config.py, orchestrator/project_profile.py, orchestrator/targets.py, tests/
budget_usd: 35
---

# SPEC: Защищённые пути: маски со звёздочкой в no_paths действительно защищают

## Контекст
Единая формула сверки защищённых путей `config.is_protected_path(path, protected)`
(`orchestrator/config.py:883-914`) понимает только записи `**/<имя>`,
`**/<каталог>/` и префикс. Звёздочка в другой позиции не раскрывается:
`is_protected_path("ci/dev/.env.dist", ("ci/**",))` — `False`,
`is_protected_path("vars-a.yml", ("vars*.yml",))` — `False`. Записи `no_paths`
внешних проектов (перечень — `repo_context.protected_paths`) несут маски вида
`ci/**`, `vars*.yml`, `<каталог>/**`, `<каталог>/<имя>.config.*`,
`<каталог>/.env*` — пути под ними роли сейчас не защищены. Та же семантика масок
уже есть в `project_profile.mask_matches(mask, path)`
(`orchestrator/project_profile.py:46-62`); формулы нужно свести в одну.

## Требования

1. `config.is_protected_path` для записи, содержащей `*` и не подходящей под
   прежние формы `**/<имя>` и `**/<каталог>/`, сверяет путь по семантике
   `mask_matches`: `*` — любые символы внутри одного сегмента пути, `**` — любое
   число сегментов, включая ноль; запись `<каталог>/**` покрывает пути
   `<каталог>/…` на любой глубине.
2. Реализация — в `orchestrator/config.py` без импорта модулей пульта.
   `project_profile.mask_matches` и новая проверка — одна формула:
   `mask_matches` зовёт функцию `config`, либо обе зовут общую функцию `config`;
   на одних входах ответы одинаковы.
3. Прежние формы записей (`**/<имя>`, `**/<каталог>/`, префикс) дают те же
   ответы, что на `a3b4fc004`.
4. Прочие символы шаблонов (`?`, `[…]`, `{…}`) шаблоном не считаются: запись с
   ними сверяется как прежде (префиксом).
5. Запись внешнего проекта, у которой элемент `no_paths` содержит `?`, `[` или
   `{`, — отказ загрузки записи (проверка записи в `orchestrator/targets.py`,
   `TargetsError`) с текстом, называющим поле `no_paths` и само значение: маска,
   которую формула не понимает, не должна выглядеть защитой.
6. Тесты задачи — в новом долгоживущем файле задачи в `tests/`; формула
   вызывается напрямую, перечни защищённых путей — литералы теста; настоящие
   записи `.artel/targets.yaml` главной копии тесты не читают. Каждый тест несёт
   строку «Ловит мутацию: …».
7. Существующие тесты `tests/` не меняются. Если существующий тест ждёт, что
   маска со звёздочкой не защищает путь, — эскалация с именем теста, а не правка
   теста.

## Критерии приёмки

AC-1. Запись `ci/**`: `is_protected_path` возвращает `True` для `ci/a` и
`ci/dev/.env.dist`, `False` для `cix/a` и `a/ci/b`.
Поверхность решения: orchestrator.config.is_protected_path(path: str, protected: tuple[str, ...]) -> bool
Размер проверки: малый

AC-2. Запись `vars*.yml`: `True` для `vars.yml` и `vars-a.yml`, `False` для
`a/vars-a.yml` и `vars-a.yaml`.
Поверхность решения: orchestrator.config.is_protected_path(path: str, protected: tuple[str, ...]) -> bool
Размер проверки: малый

AC-3. Запись `frontend/vite.config.*`: `True` для `frontend/vite.config.js`,
`False` для `frontend/sub/vite.config.js`; запись `frontend/.env*`: `True` для
`frontend/.env` и `frontend/.env.local`; запись `harness/**`: `True` для
`harness/a.py`.
Поверхность решения: orchestrator.config.is_protected_path(path: str, protected: tuple[str, ...]) -> bool
Размер проверки: малый

AC-4. Прежние формы: для записей `**/conftest.py`, `**/.claude/`, `.github/`,
`CLAUDE.md` ответы функции на наборе путей равны ответам функции на `a3b4fc004`
— ожидания записаны в тесте литералами (ловит изменение прежних форм).
Поверхность решения: orchestrator.config.is_protected_path(path: str, protected: tuple[str, ...]) -> bool
Размер проверки: малый

AC-5. Одна формула: на одном наборе масок со звёздочкой и путей (не меньше 30
пар, включая крайние случаи — пустой сегмент `**` в начале, середине и конце
маски, `*` в начале и конце сегмента, путь глубже и мельче маски)
`project_profile.mask_matches(mask, path)` и `config.is_protected_path(path,
(mask,))` дают одинаковый ответ.
Поверхность решения: orchestrator.project_profile.mask_matches(mask: str, path: str) -> bool; orchestrator.config.is_protected_path(path: str, protected: tuple[str, ...]) -> bool
Размер проверки: малый

AC-6. Критерий подключения: гейт зон на переходе `in_dev -> verifying` в
песочнице проекта, чья запись несёт `no_paths: [ci/**]`, отклоняет дифф ветки
задачи, меняющий `ci/dev/x`, отказом о защищённом пути, называющим `ci/dev/x`;
при отказе состояние задачи в БД не меняется. Проверяется настоящий гейт через
команду пульта, не функция (ловит место сверки, обходящее формулу).
Размер проверки: средний

AC-7. Загрузка/проверка записи внешнего проекта с `no_paths: [a?.yml]` и,
отдельно, с `no_paths: [a[bc].yml]` отказывает `TargetsError`, текст которого
содержит имя поля `no_paths` и значение (`a?.yml` либо `a[bc].yml`); запись с
`no_paths: [ci/**]` проходит без отказа. Записи — литералы теста, не
`.artel/targets.yaml` главной копии.
Поверхность решения: orchestrator.targets.check(name: str, entry: dict) -> None | исключение TargetsError(текст)
Размер проверки: малый

## Оценка объёма и деление

Сработавший сигнал: `budget_usd` ≥ $30 (значение $35 — рамка ТЗ; критериев 7,
файлов зоны кода 3 плюс `tests/`).

Обоснование монолита (материал Оператору): смена — одна формула в
`config.is_protected_path` плюс сведение к ней `project_profile.mask_matches` и
отказ загрузки непонятных масок в `targets.py`. Отказ `targets.py` без новой
формулы отбросил бы лишь часть непонятных масок, оставив `*`-маски незащищёнными;
новая формула без сведения `mask_matches` снова развела бы две копии правила
(требование 2). Части по отдельности мержимы, но каждая — с ровно той дырой,
которую закрывает задача; объём (одна функция и одна проверка поля) делить
незачем.

## Не входит

- Правка записей проектов: маски записей начнут защищать сами, Оператор сверяет
  `doctor` после мержа.
- `config.PROTECTED_PATHS` артели и его зеркало `no_paths` в `targets.yaml`.
- Правка `docs/invariants.md`: если описание формулы там расходится с новым
  поведением — роль пишет это в «Предложения системе».
- `.artel/targets.yaml` главной копии (настоящие записи — тесты их не читают) и
  каталог `.github/` (только литерал прежней формы в AC-4); оба не правятся.
- Правка модулей только для чтения: `orchestrator/repo_context.py`,
  `orchestrator/doctor/project_checks.py`, `scripts/guard.py`,
  `scripts/ci_protected_paths.py`.
- Смена существующих тестов `tests/` (требование 7).

## Материалы

- ТЗ: `tasks/01M70RZS8Q09GSHWFGANE3FHX7/TZ.md`; строка копилки `e895cc3e6`
  (приоритет 1).
- Формула: `orchestrator/config.py:883-914`; маска профиля:
  `orchestrator/project_profile.py:46-62`; проверка записи:
  `orchestrator/targets.py:971` (`check`), `TargetsError` — `:232`.
- Гейт зон: `orchestrator/advance_gates/zones.py:37-44`
  (`_protected_paths_touched`).
- Замечание к прочтению требования 1: запись `**/<остаток>`, у которой в
  остатке есть `*` (например `**/*.env`), прежней формой `**/<имя>` не
  считается (прежняя форма сравнивает имя буквально и такой путь не покрывала)
  — она идёт по семантике `mask_matches`, что и требует AC-5.
