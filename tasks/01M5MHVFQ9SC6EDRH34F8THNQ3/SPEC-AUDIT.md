---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/.
spec_sha: 995dd013f150e9d171a324817028bbb07bda6f5b
schema_version: 5
---

# SPEC-AUDIT: Одна функция открытия БД пульта только на чтение вместо пяти копий

## ТЗ и SPEC
ANSWER-n.md в каталоге задачи нет; решений Оператора на гейте SPEC в брифе нет.

- ТЗ треб. 1 → SPEC треб. 1, AC-1, AC-2, AC-3, AC-5 — дословно.
- ТЗ треб. 2 → SPEC треб. 2, AC-6 (вызов из пяти мест), AC-7 (тексты и коды).
- ТЗ треб. 3 → SPEC треб. 3; проверяется AC-4 (линтер) — но не полностью, см. отклонение 2.
- ТЗ треб. 4 (а)–(д) → AC-1…AC-5, это одно и то же; докстринг-маркер мутации для (г) перенесён в SPEC треб. 4.
  ТЗ называет красными (а)–(д); SPEC треб. 4 говорит «все эти проверки красные» про AC-1…AC-5. AC-6 на текущем коде тоже красный (функции нет). AC-7 зелёный с рождения — это регрессионная проверка, её нужно помечать «Зелёный с рождения:» (`scripts/guard.py:940`). Это не противоречит ТЗ.
- ТЗ треб. 5, «Зоны», «Ограничение зон по смыслу», «Только чтение», «Не входит», бюджет $25 → frontmatter и «Не входит» SPEC. Всё перенесено.
- В SPEC нет требований, которых нет в ТЗ. AC-6 и AC-7 — это проверяемая форма ТЗ треб. 2 и 5.

## Факты против кода
Подтверждено по рабочему каталогу:
- `orchestrator/store.py:337` — `sqlite3.connect(f"{config.DB.resolve().as_uri()}?mode=ro", uri=True)` в `db_usable` (def :325). Проверка `is_file()` на :334, перехват `sqlite3.Error` на :339.
- `orchestrator/store.py:387` — `db()`. Функции открытия на чтение в store нет.
- `orchestrator/knowledge_cards.py:767` (def `_open_db_readonly` :761), `sys.exit` на :766, `row_factory` на :768.
- `orchestrator/suite_run.py:179` (def `_readonly_db` :178), запасной путь `_db()` :169–175.
- `orchestrator/preflight.py:84` (def :80), `None` при отсутствии файла (:82–83). `_task_row` печатает сообщение и выходит с кодом 2 (:93–95). (В ТЗ `sys.path.insert` в test_rule_stats указан на строке 41, фактически он на :39. SPEC этот факт не повторяет.)
- `scripts/test_rule_stats.py:72` — URI строится отдельной строкой, `connect` стоит на :74 внутри `try`, `StatsError` на :71 и :83.
- `grep -rn "?mode=ro" orchestrator scripts` сейчас находит ровно эти пять строк. Докстринги (artel.py:2177, store.py:332, preflight.py:15 и др.) пишут `mode=ro` без `?`, поэтому grep треб. 3 их не задевает.
- `config.SPLIT_SIGNAL_ZONE_FILES = 5` (`orchestrator/config.py:584`) — сигнал деления указан верно.
- Импорт `sqlite3` нужен всем четырём вызывающим и после правки: knowledge_cards.py:828, suite_run.py:174, preflight.py:80 (аннотация), test_rule_stats.py:82. Оговорка «ставший лишним импорт» к этим файлам не применится.
- Существующие тесты переживут правку. `test_ac11_sqlite_connect_only_from_store` (`tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py:476–498`) смотрит, из какого модуля пришёл вызов, по `f_globals["__name__"]`, а вызов из `store.db_readonly` идёт из `orchestrator.store`. Шпионы `knowledge_command.py:640`, `developer_suite_run.py:343` и `rule_stats.py:445` подменяют глобальный атрибут `sqlite3.connect`. `test_rule_stats` запускается через `runpy` в том же процессе (`test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py:202`), поэтому импорт `orchestrator.store` из скрипта берётся из `sys.modules`.

Расхождение:
- `scripts/test_rule_stats.py:41-43` сейчас импортирует только `config` и `advance_gates.test_integrity`. `store` там не импортируется, вопреки неявной посылке ограничения зон (см. отклонение 1).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | убран `?mode=ro` или добавлен `mode=rw` → запись проходит; не ставится `row_factory` или он ставится при `rows=False`; по умолчанию `rows=False` |
| AC-2 | да | `mode=rwc`, открытие без URI (`sqlite3.connect(path)`) или вызов `store.db()` → файл создаётся, исключения нет; добавлен перехват с возвратом `None` |
| AC-3 | да, с оговоркой | `uri` передан позиционно; URI собран без `as_uri()`; другой суффикс. Мутацию «убран `.resolve()`» тест поймает, только если переданный путь отличается от разрешённого (относительный путь или symlink, например `/var`→`/private/var` на macOS). Это нужно учесть автору тестов |
| AC-4 | да | своя копия `f"…?mode=ro"` в любом `.py` из `orchestrator/` или `scripts/` вне `store.db_readonly` |
| AC-5 | да | значение по умолчанию, связанное при импорте (`path=config.DB` в сигнатуре или константа модуля) → шпион видит старый путь |
| AC-6 | да | одно из пяти мест оставило свой `sqlite3.connect`; `db_usable`/`journal` вызывают с `rows=True`; `journal` открывает `config.DB` вместо `db_path`; импорт `from orchestrator.store import db_readonly` (шпион на атрибуте модуля его не увидит, значит критерий фактически требует вызова через `store.db_readonly`) |
| AC-7 | да (регрессия, зелёный с рождения) | проверка `is_file()` перенесена в `db_readonly` или из вызывающих убрана, так что текст отказа или код выхода меняется; из `db_usable` убран перехват `sqlite3.Error` |

## Зоны
- Зоны SPEC: store.py, knowledge_cards.py, suite_run.py, preflight.py, scripts/test_rule_stats.py, docs/codebase-map.md, tests/. Это всё, что требования заставят менять. Карту нужно регенерировать (`*.py` в orchestrator/ и scripts/ меняются), она в зонах.
- Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) задача не трогает. Песочница ролей не расширяется.
- Отклонение 1. «Не входит», последний пункт перед перечнем тестов (SPEC: «В `knowledge_cards.py`, `suite_run.py`, `preflight.py`, `scripts/test_rule_stats.py` — любые правки кроме строки открытия соединения и ставшего лишним импорта `sqlite3`»), противоречит SPEC треб. 2 и AC-6 для `scripts/test_rule_stats.py`:
  - чтобы вызвать `store.db_readonly`, скрипту нужен новый импорт `from orchestrator import store`. Сейчас его нет: `scripts/test_rule_stats.py:41-43`;
  - открытие на :72–74 занимает две строки (`uri = …` и `connect(uri, uri=True)`), и `uri = …` придётся удалить, иначе AC-4 останется красным.
  Буквально исполнить и треб. 2, и запрет нельзя. Ограничение перенесено из ТЗ («Ограничение зон по смыслу»). Оператору достаточно подтвердить, что новый импорт `store` и удаление строки `uri =` входят в «строку открытия».

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| открытие БД в `knowledge_cards._open_db_readonly` | соединение `mode=ro` и `uri=True`, `store.db()` для чтения не зовётся — `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py:640` (test_ac5) | да | тот же тест (не правится) + AC-6 | остаётся |
| открытие БД в `suite_run._readonly_db` | запасной путь только на чтение — `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py:343`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py` | да | те же тесты + AC-6 | остаётся |
| открытие БД в `preflight._open_db_readonly` | код 2 без создания БД — `tests/test_preflight.py::test_missing_db_exits_2_and_creates_no_db`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py::test_ac8_readonly_db_file_same_output_and_code` | да | те же тесты + AC-7 | остаётся |
| открытие БД в `scripts/test_rule_stats.journal` | каждое соединение отказывает в записи, БД не меняется — `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py:414`; нет БД → код 2 — `tests/test_test_rule_stats.py::FailClosedTest::test_missing_db_is_exit_2_without_summary` | да | те же тесты + AC-6, AC-7 | остаётся |
| открытие БД в `store.db_usable` | `False` при отсутствии файла или ошибке; подмена в `tests/test_reference_command.py:91` | да | тот же тест + AC-7 | остаётся |
| новый вызов `sqlite3.connect` в `store.db_readonly` | `connect` только из `orchestrator.store` во время `canary runs` — `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py:476` | да | тот же тест | остаётся |

Существующие тесты, гейты и лимиты не ослабляются. Раздела «Меняемое поведение» в SPEC нет, и он не нужен: ни одно ожидание существующих тестов не меняется.

## Пути обхода гейтов
- Отклонение 2. Треб. 3 (grep находит ровно одну строку) шире AC-4. AC-4 не учитывает докстринги и комментарии (`#`), а `grep -rn "?mode=ro"` их видит. Пример: исполнитель пишет в докстринге `db_readonly` или в новом комментарии вызывающего «открывает `…?mode=ro`». AC-4 остаётся зелёным, а треб. 3 буквально нарушено. Ни один AC не держит треб. 3 целиком. Различие перенесено из ТЗ (треб. 3 и 4(г)). Оператор решает, достаточно ли AC-4 или нужна оговорка «grep без учёта докстрингов и комментариев».
- Наблюдение, отклонением не считаю. AC-4 ищет подстроку `?mode=ro` в одной константе. Копию, собранную из частей (`"?mode" + "=ro"`, `"mode=ro"` с отдельным `"?"`), линтер не увидит. Пять известных мест такой мутацией держит AC-6; остаются только новые копии в других местах. Линтер стоит в таком виде по решению ТЗ, поэтому это не путь обхода смысла SPEC.

## Вердикт
concerns. Оба отклонения перенесены из ТЗ, и Оператор может снять их одним решением на гейте. Возвращать SPEC аналитику не требуется.

1. SPEC, раздел «Не входит» (пункт про `knowledge_cards.py`, `suite_run.py`, `preflight.py`, `scripts/test_rule_stats.py`), противоречит SPEC треб. 2 и AC-6. В `scripts/test_rule_stats.py:41-43` нет импорта `store`, а открытие на `scripts/test_rule_stats.py:72-74` занимает две строки. Исполнитель обязан добавить `from orchestrator import store` и удалить `uri = …`, а это за пределами разрешённых «строки открытия и импорта `sqlite3`». Оператору нужно подтвердить, что эти правки допустимы.
2. SPEC треб. 3 (grep ровно одной строки, включая докстринги и комментарии) не покрыт AC-4 целиком: AC-4 исключает докстринги, а комментарии AST не видит вовсе. Докстринг или комментарий с `?mode=ro` нарушает треб. 3 при зелёной планке.

Заметка автору тестов, не отклонение SPEC: для AC-3 нужен путь, у которого `resolve()` отличается от исходного, иначе мутацию «убран `.resolve()`» тест не поймает.
