---
task: 01M5ENWB2XHZFRNQ3Q3PZSAH2T
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G5а: документы knowledge компонента в брифе ролей внешнего проекта

# G5а: документы `knowledge` компонента в брифе ролей внешнего проекта

## Факты

Задача волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, «Решение» п. 11 — документы `knowledge` компонента идут в бриф). Решения Оператора 21.10: G5 делится на G5а (эта задача) и G5б; обе ведутся параллельно с G3а-2б-1 (общих файлов нет); документы `knowledge` — дополнение к `CLAUDE.md` и `AGENTS.md`, не замена; предел — 20 файлов на элемент-каталог.

**Граница задачи одной фразой:** новое поведение — только у задачи с профилем из записи `components:`, у единственного компонента которой есть поле `knowledge`; у артели, у записи `test_profile` и у компонента без `knowledge` бриф всех ролей прежний побайтно.

- Поле `knowledge` компонента принимается схемой (`orchestrator/targets.py:98`, вид `repo_paths`), но нигде не читается; у `Profile` поля `knowledge` нет, `_with_component_fields` его не копирует (`orchestrator/project_profile.py`, только чтение) — поля компонента берутся из `project_profile.components(target)[0].fields`. Не путать с полем записи `knowledge` (`orchestrator/targets.py:124`, `KNOWLEDGE_FIELD` — файл карточек знаний `knowledge_cards`), которое задача не меняет.
- Конвенции внешнего проекта — фиксированный список `orchestrator/brief.py:44` (`PROJECT_CONVENTIONS = ("CLAUDE.md", "AGENTS.md")`); чтение — `orchestrator/brief.py:550` (`_read_project_conventions`: `ls-tree <sha>` корня без пути — пути в подкаталогах ему не видны; `show` коммита базы; пометка «текст не в UTF-8»); куски — `orchestrator/brief.py:586` (`_project_conventions_parts`; пометки «файла нет» и «конвенции проекта не прочитаны» с записью журнала; подпись куска «<файл> (корень ветки <base> проекта <target>)»).
- Вызовы: developer — `orchestrator/brief.py:1050`, аудитор SPEC — `orchestrator/brief.py:1120`, аналитик — `orchestrator/brief.py:1421`, test_author — `orchestrator/brief.py:1459`; пакет ревьювера — `orchestrator/review.py:941` (оформление куска — `_conventions_component`, `orchestrator/review.py:205`). Сборщики брифов зовёт `orchestrator/role_prompt.py` (зона G5б, здесь только чтение). Файл `review.py` в зонах G3а-2б-1, здесь только чтение: правка внутри `_project_conventions_parts` доходит до пакета без правки `review.py`.
- Предел размера на файл действует у developer и аудитора SPEC (`_manifest_component`, `config.CONTEXT_FILE_MAX_BYTES`) и в пакете ревьювера (`review.artifact_part`); у аналитика и test_author (`_journal_component`) предела нет.
- Запись с несколькими компонентами до G3б отклоняет `decide` (`MULTI_COMPONENT_PENDING`): у записи sled (два компонента) `knowledge` до G3б не действует.

## Требуется

1. **Документы `knowledge`.** Если `project_profile.decide(target).profile` взят из записи `components:` (`from_components`) и у её единственного компонента (`project_profile.components(target)[0]`) есть поле `knowledge`, `_project_conventions_parts` после прежних кусков `PROJECT_CONVENTIONS` (побайтно прежних, включая пометки) добавляет куски элементов `knowledge` по порядку записи, пропуская пути, уже показанные выше:
   - элемент без `/` на конце — файл: состав — `ls-tree` коммита базы с этим путём, буквально (`--literal-pathspecs`); текст — `show`;
   - элемент с `/` на конце — каталог: все обычные файлы `*.md` под ним, рекурсивно (`ls-tree -r`), по пути отсортированно; не более `KNOWLEDGE_DIR_MAX_FILES = 20` (константа `brief.py`), сверх — строка «документы knowledge: каталог <путь> — показаны первые 20 файлов из <N>» и запись журнала;
   - элемент без `/`, оказавшийся каталогом, — пометка «конвенции проекта не прочитаны: <путь>: каталог — элемент-каталог пишется с «/» на конце» с записью журнала;
   - символьная ссылка и подмодуль — та же пометка с причиной «не обычный файл»;
   - нет пути в дереве базы — «файла нет»; сбой git и текст не в UTF-8 — прежняя пометка «конвенции проекта не прочитаны» с записью журнала.

   Подпись куска — «<путь> (knowledge компонента <имя>, ветка <base> проекта <target>)»; оформление — тот же `render` вызывающего. База не прочитана — одна прежняя пометка, перечень — `PROJECT_CONVENTIONS` и элементы `knowledge`. Отказ, пропуск, `test_profile`, компонент без `knowledge`, запись из нескольких компонентов (отказ `decide` до G3б) — прежний вывод побайтно; у артели функция не вызывается, как сегодня. Действует у всех пяти потребителей: developer, аудитор SPEC, аналитик, test_author, ревьювер (через пакет ревьювера). Исключение модуля `targets` (ошибка записи проекта) при чтении записи для `decide` или `components` — прежний вывод побайтно, сборку брифа не останавливает.
2. Тесты детерминированы, без сети: учебный git-проект с компонентом и полем `knowledge` — бриф у пяти потребителей (пакет ревьювера — только присутствие и порядок кусков `knowledge`, не сравнение пакета целиком: его строки меняет G3а-2б-1); эталон, снятый с кода пина при постоянном `run_id` (`brief.new_run_id` подменён): выход `_project_conventions_parts` с тремя способами оформления (`_manifest_component`, `_journal_component`, `review._conventions_component`) у `test_profile` и у компонента без `knowledge`; отдельные случаи: файл в подкаталоге, каталог с `*.md` и не-`*.md`, элемент-каталог без `/`, символьная ссылка, повтор пути (`CLAUDE.md` в `knowledge`), отсутствующий путь, превышение предела 20, текст не в UTF-8, база не прочитана; у артели функция не вызывается. Существующие тесты без правок и зелёные.

Зоны: orchestrator/brief.py, tests/

Только чтение: docs/adr/0026-project-components-and-outcome-gates.md, orchestrator/project_profile.py, orchestrator/targets.py, orchestrator/repo_context.py, orchestrator/reference_cache.py, orchestrator/context_package.py, orchestrator/knowledge_cards.py, orchestrator/store.py, orchestrator/config.py, orchestrator/review.py (вызывающий `_project_conventions_parts`, `artifact_part`; подпись не меняется), orchestrator/advance_gates/capacity.py (пакет ревьювера), orchestrator/role_prompt.py (вызывающий сборщиков брифа; зона G5б).

Не входит: задание test_author по правилу планки, сводки Vitest, итоговая строка `plank-run`, скилы (G5б); карта кода и справочник ядра внешнего проекта; `knowledge` у записи из нескольких компонентов (sled) — после G3б; выбор компонента по диффу (G3б).

Бюджет: $20–25.
