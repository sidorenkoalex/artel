"""Миссия роли + бриф/ревью-пакет шага: сборка содержимого промпта, общего
для всех ролей `cmd_run` (analyst/spec_auditor/test_author/developer/
reviewer).
Перенесено из orchestrator/runner.py без изменения поведения (T091,
декомпозиция диспетчеров fsm/runner).
"""
import sqlite3
import sys
from pathlib import Path

from scripts import guard

from . import brief, config, project_profile, review, stack, store
from .advance_gates import spec_audit


def mission_brief_package(conn, task_id: str, t, role: str, cwd,
                          docs_dir=None):
    """(mission, brief_text, package) — `brief_text`/`package` — `None`,
    когда роли соответствующий компонент не положен (та же комбинация,
    что и раньше в теле `_cmd_run`: только `role == "review"` собирает
    `package`, у остальных трёх ролей он всегда `None`).

    `cwd` — рабочий каталог ЭТОГО шага (`runner.role_cwd_path`, тот же
    путь, что реально вернул бы `runner.role_cwd`, SPEC
    01M1RQ12JVHE3PQYDFV1XPSTQ3, требование 2): миссия каждой из четырёх
    ролей заканчивается буквальной строкой рабочего каталога — роль не
    обязана домысливать, где именно ей можно писать файлы Write.

    `docs_dir` — каталог документов задачи (`artifact_branch.docs_dir`):
    миссия называет его буквальной строкой (`docs_dir_note`); `None` —
    абзаца нет."""
    task_ref = f"tasks/{task_id}"
    package = None
    brief_text = None
    # Состав брифа задачи внешнего проекта (SPEC 01M5634E094QF7JX8HD3KSG4KN,
    # требование 10): конвенции проекта вместо карты кодовой базы пульта.
    artel = conn is None or brief.is_artel_task(conn, task_id)
    if role == "analyst":
        brief_line = (
            "Карта кодовой базы и шаблоны templates/SPEC.md и "
            "templates/QUESTIONS.md — в БРИФЕ РОЛИ ниже." if artel else
            "Конвенции проекта (CLAUDE.md и AGENTS.md его базовой ветки) и "
            "шаблоны templates/SPEC.md и templates/QUESTIONS.md — в БРИФЕ "
            "РОЛИ ниже.")
        mission = (
            f"Роль: аналитик. Задача {task_id}, ветка {t['branch']} — уже "
            f"выписана в этом рабочем каталоге (собственный worktree "
            f"задачи, рабочая копия пульта его не видит). "
            f"Основной вход — ТЗ Оператора, разработчик увидит задачу "
            f"только после тебя. {brief_line}\n"
            f"{_template_unread_note()}\n"
            f"1) Прочитай {task_ref}/TZ.md.\n"
            f"2) ТЗ достаточно — напиши {task_ref}/SPEC.md по шаблону SPEC "
            f"из брифа: критерии приёмки размечены AC-n строго "
            f"из формулировок ТЗ, «не входит» — из его же границ, "
            f"budget_usd по классу задачи и только вниз от дефолта, "
            f"status: ready.\n"
            f"3) ТЗ неясно или неполно — не домысливай: один батч всех "
            f"вопросов в {task_ref}/QUESTIONS.md по шаблону QUESTIONS из "
            f"брифа, отсортированный по блокирующести, каждый — с вариантами "
            f"и дефолтом. SPEC.md в этом случае не трогай — сам файл "
            f"эскалирует задачу.\n"
            f"4) Прогони scripts/guard.py на своём файле. tasks/<id>/ "
            f"коммитить не нужно — автокоммит оркестратора сам перенесёт "
            f"написанное в артефактную ветку. Код репозитория не трогай."
        )
        brief_text = brief.analyst_map_component(conn, task_id)
    elif role == "test_author":
        long_lived = _long_lived_paths(conn, task_id)
        mission = (
            f"Роль: автор приёмочных тестов. Задача {task_id}, ветка "
            f"{t['branch']} — уже выписана в этом рабочем каталоге "
            f"(собственный worktree задачи). Разработчик увидит задачу "
            f"только после тебя —\n"
            f"1) {task_ref}/SPEC.md на диске — актуальная версия "
            f"(материализована из артефактной ветки на старте шага). "
            f"Изучи раздел «Критерии приёмки» (AC-1, AC-2, …).\n"
            f"2) Для каждого AC-n напиши unittest в "
            f"{task_ref}/acceptance_tests/test_*.py, метод test_ac<n>_... — "
            f"ТОЛЬКО из формулировки критерия.\n"
            f"{_long_lived_author_note(task_ref, long_lived)}"
            f"3) Критерий нельзя проверить тестом напрямую — пометь "
            f"`# AC-n: manual — <причина>` (Оператор проверит на приёмке) "
            f"или `# AC-n: skip — <причина>`.\n"
            f"4) Критерий в принципе неисполним тестом — не изобретай "
            f"компромисс: `# AC-n: escalate — <вопрос Оператору>`.\n"
            f"5) Прогони планку командой пульта `plank-run` (абзац о "
            f"каталоге документов ниже): она сама выложит черновик и выполнит "
            f"`python3 -m pytest {task_ref}/acceptance_tests -p "
            f"no:cacheprovider -p timeout -o "
            f"timeout={stack.PER_TEST_TIMEOUT_SEC}`"
            f"{_long_lived_run_note(long_lived)}. tasks/<id>/ коммитить "
            f"не нужно — автокоммит оркестратора сам перенесёт написанное в "
            f"артефактную ветку. Остальной код репозитория и SPEC.md НЕ трогай."
        )
        brief_text = brief.test_author_answer_component(conn, task_id)
    elif role == "developer":
        long_lived = _long_lived_paths(conn, task_id)
        brief_line = (
            "SPEC задачи, карта кодовой базы, конвенции проекта и шаблон "
            "templates/PLAN.md — целиком в БРИФЕ РОЛИ ниже, отдельно их "
            "читать не нужно." if artel else
            "SPEC задачи, конвенции проекта (CLAUDE.md и AGENTS.md его "
            "базовой ветки) и шаблон templates/PLAN.md — целиком в БРИФЕ "
            "РОЛИ ниже, отдельно их читать не нужно; правила работы роли — "
            "в скилах пульта (СКИЛЫ РОЛИ ниже).")
        mission = (
            f"Роль: разработчик. Задача {task_id}, ветка {t['branch']} — "
            f"уже выписана в этом рабочем каталоге (собственный worktree "
            f"задачи). {brief_line}\n"
            f"{_template_unread_note()}\n"
            f"1) Изучи бриф.\n"
            f"2) Напиши {task_ref}/PLAN.md по шаблону PLAN из брифа.\n"
            f"3) Реализуй по плану + юнит-тесты. Если есть {task_ref}/REVIEW.md "
            f"со статусом changes_requested — сначала закрой замечания. Если "
            f"есть {task_ref}/acceptance_tests/ — они залочены (tasks/T023): "
            f"код чинится под них, их правка — эскалация, не правка."
            f"{_long_lived_developer_note(long_lived)}\n"
            f"4) Прогони scripts/guard.py на своих артефактах, поставь "
            f"PLAN.md status: ready. НЕ мержи. Коммитить код самому не "
            f"обязательно: код, оставленный в worktree незакоммиченным, по "
            f"итогам шага коммитит пульт в ветку задачи. tasks/<id>/ "
            f"коммитить не нужно — автокоммит оркестратора сам перенесёт "
            f"PLAN.md в артефактную ветку.\n"
            f"{suite_run_note(task_id)}"
        )
        brief_text = brief.developer_brief(conn, task_id)
    elif role == "spec_auditor":
        mission = _spec_auditor_mission(conn, task_id, t, artel)
        brief_text = brief.spec_auditor_brief(conn, task_id)
    else:
        # номер, которого ждёт FSM: вердикт с прежним iteration он уже учёл
        iteration = t["reviewed_iter"] + 1
        mission = (
            f"Роль: ревьювер. Задача {task_id}, ветка {t['branch']}. Свежий "
            f"контекст: всё нужное для ревью уже собрано в РЕВЬЮ-ПАКЕТЕ ниже "
            f"(SPEC, PLAN, прошлый REVIEW, форма вердикта, список изменённых "
            f"файлов, diff). "
            f"Работай от пакета, а не от обхода репозитория.\n"
            f"Файлы сверх пакета читай точечно и только когда без них не "
            f"проверить конкретное замечание; причину чтения называй в самом "
            f"замечании. Права не сужены: тесты, guard и другие исполняемые "
            f"проверки запускай, когда они доказывают или опровергают "
            f"замечание.\n"
            f"Проведи обе фазы review-checklist (гейт плана + ревью MR) и "
            f"заполни {task_ref}/REVIEW.md по форме из пакета "
            f"(iteration: {iteration}). Код НЕ правь. Коммитить "
            f"REVIEW.md не нужно — автокоммит оркестратора сам перенесёт "
            f"его в артефактную ветку."
        )
        # Sha предыдущего вердикта нужен только для инкрементального diff
        # (iteration > 1) — на первой итерации журнал сравнивать не с чем,
        # и чтение не тратится зря (T029, SPEC требования 1, 2, 3).
        prev_sha = (review.previous_verdict_sha(conn, task_id)
                   if iteration > 1 else "")
        package = review.review_package(conn, task_id, t["title"], t["branch"],
                                        iteration=iteration, prev_sha=prev_sha)
    # Записки шагов — одинаково для всех ролей (SPEC
    # 01M4RZBPG6EXM74MTBPTEGW2D4, требование 10): у роли без брифа блок и
    # есть бриф; записок нет — бриф прежний.
    notes = brief.step_notes_block(conn, task_id, role)
    if notes:
        brief_text = f"{brief_text}\n\n{notes}" if brief_text else notes
    # Строка о команде `knowledge` — одинаково для всех ролей (SPEC
    # 01M4S0K2MJRMVMQWKATAME3RHR, требование 11).
    mission = f"{mission}\n\n{knowledge_hint_note(conn, task_id, t)}"
    # С каталогом документов запись открыта и в нём (`--add-dir`): строка
    # «запись вне него недоступна» противоречила бы абзацу ниже, и роль
    # могла бы не записать документ туда (REVIEW итерации 1, R1-F3).
    if docs_dir is None:
        mission = (f"{mission}\n\nрабочий каталог шага — {cwd}; все пути ниже "
                  f"относительно него; запись вне него недоступна.")
    else:
        mission = (f"{mission}\n\nрабочий каталог шага — {cwd}; пути кода "
                  f"ниже относительно него; запись вне него и вне каталога "
                  f"документов задачи недоступна.")
        mission = f"{mission}\n\n{docs_dir_note(task_id, docs_dir)}"
        mission = f"{mission}\n\n{step_note_note(role, docs_dir)}"
    return mission, brief_text, package


def _long_lived_paths(conn, task_id: str) -> tuple[str, str] | None:
    """(каталог, префикс имени) долгоживущих файлов задачи по профилю её
    проекта — тем же источником, что гейт выхода из `tests_writing`
    (SPEC 01M551W0TFCT2XRQ71XFXJDKB9, требования 1, 5). Префикс конкретный,
    не шаблон (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 10, Р1).
    `None` — профиля нет (отказ или пропуск): умолчания артели не
    подставляются, и задание каталог долгоживущих тестов не называет.
    `conn=None` — проект артели (тот же ответ, что `store.task_target` у
    задачи без строки)."""
    target = (store.task_target(conn, task_id) if conn is not None
              else config.DEFAULT_TARGET)
    profile = project_profile.decide(target).profile
    if profile is None:
        return None
    return profile.long_lived_dir, profile.long_lived_prefix(task_id)


def _long_lived_author_note(task_ref: str, long_lived) -> str:
    """Пункт 2а задания test_author; пустая строка — профиля нет."""
    if long_lived is None:
        return ""
    directory, prefix = long_lived
    return (
        f"2а) Долгоживущий файл (`Группа: долгоживущий`, "
        f"skills/test-authoring.md) пиши не в каталог приёмочных тестов, "
        f"а в каталог {directory}/ кодовой ветки, с именем "
        f"{prefix}<имя>.py (<имя> — строчные латинские буквы, "
        f"цифры, подчёркивание). Существующие файлы {directory}/ не трогай — "
        f"их правку, переименование и удаление, как и любую другую "
        f"правку вне {task_ref}/, пульт откатит; свои новые файлы с этим "
        f"префиксом он сам закоммитит в ветку на чекпоинте шага.\n")


def _long_lived_run_note(long_lived) -> str:
    """Хвост пункта 5 задания test_author о прогоне долгоживущих файлов."""
    if long_lived is None:
        return ""
    return (f"; долгоживущие файлы {long_lived[0]}/ — тем же pytest с теми "
            f"же флагами по их путям из рабочего каталога")


def _long_lived_developer_note(long_lived) -> str:
    """Фраза пункта 3 задания developer о долгоживущих файлах задачи."""
    if long_lived is None:
        return ""
    directory, prefix = long_lived
    return (f" Долгоживущие файлы задачи в {directory}/ ({prefix}*.py) "
            f"зафиксированы так же, как приёмочные тесты, — перечнем сумм под "
            f"тем же локом: их не правь, расхождение с ними эскалируй.")


def _spec_auditor_mission(conn, task_id: str, t, artel: bool = True) -> str:
    """Миссия аудитора SPEC (ADR-0022 пп. 2-3, SPEC
    01M4MQAGRWMWR0GFDM9086P3TD, требования 6-7): проверяемая версия SPEC
    (sha содержимого на входе), сработавшие сигналы и глубина разбора — из
    записи входа в `spec_audit`, не пересчётом: аудитор проверяет ровно ту
    версию, к которой пульт потом привяжет его вердикт."""
    task_ref = f"tasks/{task_id}"
    entry = spec_audit.entry(conn, task_id) or {}
    sha = entry.get("sha") or "(не записан — эскалируй)"
    listed = entry.get("signals") or spec_audit.NO_SIGNALS
    if entry.get("full", True):
        depth = ("полный разбор — каждый из разделов «ТЗ и SPEC», «Факты "
                 "против кода», «Проверяемость критериев», «Зоны», «Матрица "
                 "неослабления», «Пути обхода гейтов» по существу, с "
                 "проверкой по коду")
    else:
        depth = ("краткий разбор — вердикт и отклонения; разделы без "
                 "находок — одной строкой «отклонений нет»")
    context = "карта кодовой базы" if artel else "конвенции проекта"
    return (
        f"Роль: аудитор SPEC. Задача {task_id}, ветка {t['branch']}. Ты — "
        f"независимая проверка SPEC аналитика до гейта SPEC: ТЗ, SPEC, ответы "
        f"Оператора, {context} и шаблон "
        f"templates/{spec_audit.ARTIFACT} — в БРИФЕ РОЛИ ниже, код — в "
        f"рабочем каталоге.\n"
        f"{_template_unread_note()}\n"
        f"Проверяемая версия: sha содержимого {task_ref}/SPEC.md в ссылке "
        f"документов — {sha}.\n"
        f"Сработавшие сигналы глубины: {listed}.\n"
        f"Глубина: {depth}.\n"
        f"1) Заполни {task_ref}/{spec_audit.ARTIFACT} по шаблону "
        f"{spec_audit.ARTIFACT} из брифа: в «Вердикте» — перечень отклонений "
        f"со ссылками файл:строка; поля frontmatter — verdict (pass | "
        f"concerns | fail), signals (сигналы выше дословно) и spec_sha: "
        f"{sha}; status: ready.\n"
        f"2) Без ответа Оператора вердикт не вынести — status: escalate и "
        f"раздел «Эскалация» (skills/escalation-rules.md).\n"
        f"3) SPEC.md, ТЗ и код не правь: правка SPEC за визит аудита делает "
        f"вердикт недействительным. Прогони scripts/guard.py на своём файле. "
        f"tasks/<id>/ коммитить не нужно — автокоммит оркестратора сам "
        f"перенесёт {spec_audit.ARTIFACT} в артефактную ветку."
    )


def _template_unread_note() -> str:
    """Строка миссии об исключении (SPEC 01M4RZBDFSHNESSBQREH5MKY9B,
    требование 5): шаблон артефакта лежит в брифе роли, файл с диска нужен
    только там, где бриф вместо шаблона несёт пометку о неудаче чтения
    (`brief._template_components`)."""
    return ("Если вместо шаблона в брифе стоит пометка «шаблон "
            "templates/<имя> не прочитан», прочитай этот файл templates/<имя> "
            "с диска сам.")


def suite_run_note(task_id: str) -> str:
    """Строка миссии разработчика о полном прогоне тестов (SPEC
    01M462QACEH29RPRD2RZHGHQFM, требование 16): той же формой, что
    `plank-run` в `docs_dir_note`, — полный путь к `artel.py` пульта. 05.10
    роль без такой команды сама делила набор на пачки и обходила сторож."""
    pult = config.ROOT / "orchestrator" / "artel.py"
    return (
        f"Полный набор тестов — только командой пульта `python3 {pult} "
        f"suite-run {task_id}`: она запускает прогон фоном (параллель, "
        f"сравнение с базой ветки) и сразу возвращается; отчёт — `python3 "
        f"{pult} suite-run {task_id} --wait <минуты, не больше "
        f"{config.SUITE_RUN_MAX_WAIT_MIN}>`, повтор только упавших — "
        f"`python3 {pult} suite-run {task_id} --failed`. Сначала — тесты "
        f"затронутых модулей; файлы tests/ в обход сторожа не перечисляй и "
        f"набор на пачки своими сценариями не дели.")


def knowledge_hint_note(conn, task_id: str, t) -> str:
    """Строка миссии о команде `knowledge` (SPEC 01M4S0K2MJRMVMQWKATAME3RHR,
    требование 11): темы карточек проекта задачи без их текста. Отказ
    чтения вида — одна запись журнала за визит задачи в состояние; без
    соединения (`conn is None`) журнал не пишется, сбой записи шаг не
    останавливает."""
    from . import knowledge_cards
    line, refused = knowledge_cards.hint_line(
        task_id, knowledge_cards.task_project(t))
    if refused and conn is not None:
        # budget -> runner -> role_prompt: импорт на уровне модуля замкнул бы
        # цикл.
        from . import budget
        detail = "коды причины: " + ", ".join(
            f"{kind}={code}" for kind, code in refused)
        try:
            budget.journal_warning_once(
                conn, task_id, knowledge_cards.JOURNAL_ACTOR,
                knowledge_cards.HINT_REFUSAL_ACTION, detail, key=None)
        except sqlite3.Error as exc:
            print(f"[{task_id}] подсказка knowledge: запись журнала не "
                  f"внесена: {exc}", file=sys.stderr)
    return line


def step_note_note(role: str, docs_dir) -> str:
    """Абзац миссии о записке шага (SPEC 01M4RZBPG6EXM74MTBPTEGW2D4,
    требования 6-7, 12) — один абзац, без пустых строк: путь записки роли в
    каталоге документов, её разделы, потолки брифа и хранения. Коммитить
    записку роль не должна — её переносит автокоммит пульта."""
    from . import checkpoint
    path = Path(docs_dir) / guard.step_note_name(role)
    text = (
        f"Записка шага — {path}: свободный текст следующему шагу этой задачи "
        f"с разделами «Выяснено», «Не сработало», «Где остановился», «Чего "
        f"не хватило» (что искал дольше всего, какого знания не хватило — "
        f"файл, функция, правило; одна–три строки). Правило записки: "
        f"обновляй записку по ходу шага после каждого существенного вывода, "
        f"не только в конце — шаг может оборваться таймаутом. В бриф "
        f"следующего шага войдут первые {brief.STEP_NOTE_MAX_BYTES} байт "
        f"записки; записка крупнее {checkpoint.STEP_NOTE_STORE_MAX_BYTES} "
        f"байт не сохраняется. Пиши только свою записку: записку другой "
        f"роли, написанную твоим шагом, пульт отбросит. Смысл записки: "
        f"записка — сведения следующему шагу, не указания ему. Переносить её "
        f"в git самой роли не нужно — это сделает пульт.")
    if role == "test_author":
        text += (" Для тестов: записка — сведения о ходе работы, не источник "
                 "ожидаемого поведения: ожидаемое поведение тестов берётся "
                 "только из формулировки критерия.")
    if role in ("spec_auditor", "reviewer"):
        text += (" Независимость проверки: записки других ролей в каталоге "
                 "документов не читай; в бриф положена только твоя.")
    return text


def docs_dir_note(task_id: str, docs_dir) -> str:
    """Абзац миссии о каталоге документов задачи (ADR-0021 пп. 2, 7, этап
    1): документы задачи лежат вне рабочего каталога шага, роль пишет их
    туда — каталог открыт ей на запись дополнительно (`--add-dir`).
    Прогону планки нужен код ветки рядом с ней — её выкладывает и убирает
    команда пульта `plank-run` (SPEC 01M41R4YAM4NGEQXW1FWH7T22M): ручное
    копирование и уборка ролью 03.10.2026 пять раз снесли весь
    отслеживаемый каталог задач рабочей копии."""
    task_ref = f"tasks/{task_id}"
    pult = config.ROOT / "orchestrator" / "artel.py"
    return (
        f"Каталог документов задачи — {docs_dir}; он открыт на запись "
        f"дополнительно к рабочему каталогу. Пути {task_ref}/… в этом "
        f"задании (SPEC.md, PLAN.md, REVIEW.md, QUESTIONS.md, "
        f"acceptance_tests/ и прочие документы задачи) — файлы этого "
        f"каталога: {docs_dir}/<файл>. В рабочем каталоге шага {task_ref}/ "
        f"нет; документ, записанный туда, в артефактную ветку не попадёт — "
        f"пульт уберёт его после шага. Прогон планки — только командой "
        f"пульта `python3 {pult} plank-run {task_id} [файл]`: она сама "
        f"выложит планку в рабочий каталог, прогонит её раннером пульта и "
        f"уберёт выкладку. Не копируй планку в рабочий каталог руками и не "
        f"удаляй каталоги рабочего каталога для уборки (03.10.2026 такая "
        f"уборка пять раз удалила весь отслеживаемый каталог tasks/); правь "
        f"только файлы каталога документов.")
