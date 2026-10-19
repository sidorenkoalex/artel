---
task: 01M5AA5TS90RDJ2AFXB882WTPD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: G2б-1 — долгоживущие файлы компонента по шаблону `long_lived`, строка группы и «Ловит мутацию:» у файлов с меткой `AC-<n>: `

## Подход
Новое поведение включается только признаком профиля `Profile.long_lived_template`
(непустой — пара выведена из шаблона компонента). Явная пара, `test_profile` и
артель идут прежним путём: везде, где разбор зависит от шаблона, правило планки
для долгоживущих файлов передаётся как `None` (`project_profile.long_lived_rule`),
а источники трассируемости — строками, как раньше.

- `targets.py`: снят отказ «после G2б»; форма шаблона (`_long_lived_shape_error`:
  `<id>`/`<name>` ровно по разу в последнем сегменте, `<dir>` ≤ 1 раза целым
  сегментом, непустой корень, сверка последнего сегмента с масками `tests` у
  правила-метки повторами `_mask_segment_matches`/`is_pytest_command` без
  импорта guard/acceptance); порядок «форма → шаблон или пара → наличие»; новый
  текст «нет ни шаблона long_lived, ни пары …». Производная пара
  (`long_lived_pair`) дописывается только в копию, которую отдают `load`/`target`
  (`_with_long_lived_pairs`); `check` словарь не меняет, проверка вида
  `template` к паре не применяется.
- `project_profile.py`: поле `long_lived_template` (compare=False) из
  `_with_component_fields`; `long_lived_example` зовёт новую
  `guard.long_lived_example`; `long_lived_hint` — пример у профиля из шаблона,
  иначе прежняя склейка префикса и «<имя>.py»/«*.py»; `long_lived_rule`.
- `guard.py`: `<dir>` в `is_long_lived_test_path` (сегменты не с точки);
  `long_lived_example`; `plank_file_group(source, labelled)` — у файла с меткой
  строка группы из `first_comment` без ведущей « * », тексты с местом «в первом
  комментарии файла» (у Python — побайтно прежние); `rule` в
  `group_line_errors_from_files`, `acceptance_test_files` (добавляет тестовые
  файлы с меткой), `long_lived_plank_errors` (+ `example`),
  `long_lived_errors_from_files` (статика файла с меткой —
  `_labelled_long_lived_errors`: «tasks/» и id задачи по строкам текста,
  «Ловит мутацию:» в комментарии над вызовом `_comment_above`); новая
  `long_lived_group_errors` (строка группы долгоживущих + отказ «не файл с
  меткой AC-<n>: и не Python …») — общая для гейта перехода и `preflight`
  (заменила дублированный в обоих инлайн-разбор `plank_file_group`, тексты
  Python прежние); `plank_test_names` поверх `_test_calls` (строка головы).
- Гейты: `_tests_writing_test_groups_gate` и `preflight._groups` — по правилу
  планки проекта; `_tests_writing_long_lived_gate` и `preflight._long_lived` —
  `long_lived_group_errors` + статика с `long_lived_rule`; трассируемость —
  пары (путь, текст) у профиля из шаблона (`fsm_advance.tests_writing`,
  `preflight._traceability`), `rule` в `scan_ac_content` у
  `fsm._tests_writing_ac_state` и `guard.acceptance_traceability_errors`.
- `amend.py`: только отказ `_refuse_labelled` в обоих режимах до любой записи
  (файл с меткой в снимке планки до/после правки либо на голове/в правке;
  долгоживущий с меткой у профиля из шаблона).
- Подсказки: `runner.py` и `role_prompt.py` берут `Profile.long_lived_hint`,
  пункт 2а — пояснение `<каталог>`, если шаблон несёт `<dir>`.

## Шаги
1. `targets.py` + `project_profile.py`: форма шаблона, производная пара на
   чтении, `long_lived_template`, `long_lived_hint`, `long_lived_rule`; вход
   подслучая G1а приведён к годной форме (`tests/test_<id>_<name>.py`).
2. `guard.py`: правило имени с `<dir>`, пример пути, разбор группы и статика
   файлов с меткой, `long_lived_group_errors`, `rule` в функциях групп и
   трассируемости.
3. Гейты выхода из `tests_writing`, `fsm`, `preflight` — те же функции guard в
   телах перехода и в предпроверке (сторож требования 9 зелёный без правки).
4. `amend.py` — отказ G3б; `runner.py`/`role_prompt.py` — подсказки.
5. Свой тест `tests/test_long_lived_template_shape.py` (свойства вне
   долгоживущих файлов задачи), регенерация карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 4 |
| 5 | 2, 3 |
| 6 | 2, 3 |
| 7 | 2, 3 |
| 8 | 4 |
| 9 | 2, 3 (гейт зон, чекпоинт, перечень, `plank-run` — через `Profile.is_long_lived` без правки их модулей) |
| 10 | 1–4 (явная пара/`test_profile`/артель — `long_lived_template` пуст, прежние пути) |
| 11 | 5 + долгоживущие файлы задачи |

## Влияние на систему
- Рубежи не ослабляются: у файлов с меткой добавлены проверки строки группы и
  статики, которых раньше не было (гейт групп и долгоживущих видел только
  Python); у артели, `test_profile` и явной пары разбор и тексты прежние —
  закреплено тестами AC-13 долгоживущих файлов задачи.
- Гейт групп теперь читает тестовые файлы с меткой по правилу планки у любого
  проекта с компонентами-метками (требование 5): `.test.jsx` планки без строки
  группы, раньше молча проходивший, отказывает. Связанные наборы
  (`plank_rule`, `component_plank_layout`, `report_outcome`, preflight) зелёные.
- Сторож предпроверки: из тел перехода и из `preflight.py` ушла
  `guard.plank_file_group`, в обоих появилась `guard.long_lived_group_errors`;
  множества совпадают, файл сторожа не тронут, приёмочный тест AC-14 зелёный.
- `targets.load`/`target` отдают копию записи (с парой у компонентов с
  шаблоном); `check` чужих записей и `core_reference` не задеты.
- Откат — revert коммита задачи.

## Риски
- `preflight._groups` фильтрует вход правилом планки (как автокоммит): у
  проекта только с компонентами-метками `test_*.py` планки — посторонний файл
  и в предпроверке, как уже было на переходе после автокоммита.

## Предложения системе
- Сторож предпроверки сверяет только три тела перехода — помощники, которые эти
  тела зовут, вне его поля (`tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`
  `TRANSITION_BODIES`); дублированный текст отказа группы долгоживущих жил в
  двух местах именно поэтому — вынесен в guard этой задачей.
