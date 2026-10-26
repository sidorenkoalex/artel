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

# Правило о полном наборе тестов для ревьювера — единственный его источник
# (SPEC 01M5KP57JXWKKKCJKY47HT21W8, решение Оператора 23.10, вариант А):
# скил и образец REVIEW.md его не повторяют, как `suite_run_note` у
# разработчика.
REVIEWER_FULL_SUITE_RULE = (
    "Полный набор тестов в шаге ревью не запускай — ни командой пульта "
    "`suite-run`, ни `pytest` или `unittest` по всему `tests/`: его гоняют CI "
    "и гейты пульта (приёмка и мерж). В шаге — планка задачи и тесты файлов "
    "задачи.")


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
    # требование 10): конвенции проекта вместо карты кодовой базы пульта —
    # из файла пульта, не из файлов обвязки проекта (SPEC
    # 01M5T18K1YFBYA7MM1BBRV869A, требование 10).
    artel = conn is None or brief.is_artel_task(conn, task_id)
    if role == "analyst":
        brief_line = (
            "Карта кодовой базы и шаблоны templates/SPEC.md и "
            "templates/QUESTIONS.md — в БРИФЕ РОЛИ ниже." if artel else
            "Конвенции проекта (файл пульта conventions.md, разобранный при "
            "Операторе) и шаблоны templates/SPEC.md и templates/QUESTIONS.md "
            "— в БРИФЕ РОЛИ ниже.")
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
            f"4) Прогони {_guard_tool(task_id, artel, '<файл>')} на своём "
            f"файле. tasks/<id>/ "
            f"коммитить не нужно — автокоммит оркестратора сам перенесёт "
            f"написанное в артефактную ветку. Код репозитория не трогай."
        )
        brief_text = brief.analyst_map_component(conn, task_id)
    elif role == "test_author":
        long_lived = _long_lived_paths(conn, task_id)
        labelled = _labelled_profile(conn, task_id)
        if labelled is None:
            plank_point = (
                f"2) Для каждого AC-n напиши unittest в "
                f"{task_ref}/acceptance_tests/test_*.py, метод test_ac<n>_... — "
                f"ТОЛЬКО из формулировки критерия.\n")
            marker = "#"
        else:
            plank_point = _labelled_plank_point(task_id, task_ref, labelled)
            marker = guard.MARKER_SLASH
        mission = (
            f"Роль: автор приёмочных тестов. Задача {task_id}, ветка "
            f"{t['branch']} — уже выписана в этом рабочем каталоге "
            f"(собственный worktree задачи). Разработчик увидит задачу "
            f"только после тебя —\n"
            f"1) {task_ref}/SPEC.md на диске — актуальная версия "
            f"(материализована из артефактной ветки на старте шага). "
            f"Изучи раздел «Критерии приёмки» (AC-1, AC-2, …).\n"
            f"{plank_point}"
            f"{_long_lived_author_note(task_ref, long_lived)}"
            f"3) Критерий нельзя проверить тестом напрямую — пометь "
            f"`{marker} AC-n: manual — <причина>` (Оператор проверит на "
            f"приёмке) или `{marker} AC-n: skip — <причина>`"
            f"{_labelled_marker_place(labelled)}.\n"
            f"4) Критерий в принципе неисполним тестом — не изобретай "
            f"компромисс: `{marker} AC-n: escalate — <вопрос Оператору>`"
            f"{_labelled_marker_place(labelled)}.\n"
            f"{_plank_run_point(task_id, task_ref, artel, long_lived)}"
            f". tasks/<id>/ коммитить "
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
            "SPEC задачи, конвенции проекта (файл пульта conventions.md, "
            "разобранный при Операторе) и шаблон templates/PLAN.md — "
            "целиком в БРИФЕ РОЛИ ниже, отдельно их читать не нужно; "
            "правила работы роли — в скилах пульта (СКИЛЫ РОЛИ ниже).")
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
            f"4) Прогони {_guard_tool(task_id, artel)} на своих "
            f"артефактах, поставь "
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
            f"замечании. {_reviewer_checks_note(task_id, artel)} "
            f"{REVIEWER_FULL_SUITE_RULE}\n"
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


def _long_lived_paths(conn, task_id: str) -> tuple[str, str, str, bool] | None:
    """(каталог, пример пути с `<имя>`, пример пути с `*`, шаблон несёт
    `<dir>`) долгоживущих файлов задачи по профилю её проекта — тем же
    источником, что гейт выхода из `tests_writing` (SPEC
    01M551W0TFCT2XRQ71XFXJDKB9, требования 1, 5). Пример конкретный, не
    шаблон (SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требование 10, Р1): у профиля
    из шаблона `long_lived` — `Profile.long_lived_hint` (SPEC
    01M5AA5TS90RDJ2AFXB882WTPD, требование 4), иначе — префикс и «.py».
    `None` — профиля нет (отказ или пропуск): умолчания артели не
    подставляются, и задание каталог долгоживущих тестов не называет.
    `conn=None` — проект артели (тот же ответ, что `store.task_target` у
    задачи без строки)."""
    target = (store.task_target(conn, task_id) if conn is not None
              else config.DEFAULT_TARGET)
    profile = project_profile.for_task_target(target, task_id, conn).profile
    if profile is None:
        return None
    return (profile.long_lived_dir, profile.long_lived_hint(task_id),
            profile.long_lived_hint(task_id, "*"),
            "<dir>" in profile.long_lived_template)


def _labelled_profile(conn, task_id: str):
    """Профиль проекта задачи, если его компонент получает от правила планки
    метку `AC-<n>: ` (SPEC 01M5ENWTDD8NP9SMPFX3JN08J9, требование 1) — тот
    же источник, что у guard; `None` — прежнее задание test_author
    (артель, `test_profile`, pytest-компонент, профиль не определён,
    правило не построено)."""
    target = (store.task_target(conn, task_id) if conn is not None
              else config.DEFAULT_TARGET)
    profile = project_profile.for_task_target(target, task_id, conn).profile
    if profile is None:
        return None
    labelled = project_profile.plank_rule(target).labelled_components()
    return profile if profile.component in labelled else None


# Строка запретов текста Vitest-планки (SPEC 01M5ENWTDD8NP9SMPFX3JN08J9,
# требование 1) — то, что отвергает `guard.plank_ban_errors`.
_LABELLED_PLANK_BANS = (
    "В тексте планки запрещены `.fails`, `.skipIf`, `.runIf`, `.only`, "
    "`vi.setConfig`, ключи `retry`/`timeout` и числовой литерал в "
    "аргументах `it`/`test`/`describe`/`suite`.")


def _labelled_plank_point(task_id: str, task_ref: str, profile) -> str:
    """Пункт 2 и строка запретов задания test_author у компонента с меткой
    `AC-<n>: `: имена файлов — последние сегменты масок `tests` в порядке
    записи; фраза о каталоге выкладки — только при `plank_layout`, `<id>`
    в нём заменён id задачи как есть (как выкладка планки)."""
    segments = ", ".join(f"`{mask.rsplit('/', 1)[-1]}`"
                         for mask in profile.tests)
    layout = ""
    if profile.plank_layout:
        layout = (f" На прогоне файлы лежат в "
                  f"`{profile.plank_layout.replace('<id>', task_id)}`: импорты "
                  f"кода пиши относительно этого каталога.")
    return (f"2) Для каждого AC-n напиши тест в {task_ref}/acceptance_tests/ "
            f"(без подкаталогов), имя файла — по маскам {segments}; "
            f"помощники — `_<имя>.<расширение>`. Имя теста `it`/`test` "
            f"начинается с `AC-<n>: `, одна метка на тест, `describe` меткой "
            f"не начинается — ТОЛЬКО из формулировки критерия.{layout}\n"
            f"{_LABELLED_PLANK_BANS}\n")


def _labelled_marker_place(profile) -> str:
    """Где стоит пометка `// AC-n: …` у компонента с меткой `AC-<n>: `;
    пусто — прежний текст пунктов 3–4."""
    if profile is None:
        return ""
    return " — с начала строки в файле планки компонента"


def _long_lived_author_note(task_ref: str, long_lived) -> str:
    """Пункт 2а задания test_author; пустая строка — профиля нет."""
    if long_lived is None:
        return ""
    directory, example, _star, has_dir = long_lived
    dir_note = (f"; <каталог> — каталог модуля: ноль или больше подкаталогов "
                f"{directory}/, ни один не начинается с точки"
                if has_dir else "")
    return (
        f"2а) Долгоживущий файл (`Группа: долгоживущий`, "
        f"skills/test-authoring.md) пиши не в каталог приёмочных тестов, "
        f"а в каталог {directory}/ кодовой ветки, с именем "
        f"{example} (<имя> — строчные латинские буквы, "
        f"цифры, подчёркивание{dir_note}). Существующие файлы {directory}/ "
        f"не трогай — их правку, переименование и удаление, как и любую другую "
        f"правку вне {task_ref}/, пульт откатит; свои новые файлы с этим "
        f"префиксом он сам закоммитит в ветку на чекпоинте шага.\n")


def _pult_command() -> str:
    """Форма команды пульта, которую разрешает белый список роли внешнего
    проекта (`providers/claude.py`): полный путь к `artel.py` пульта."""
    return f"python3 {config.ROOT / 'orchestrator' / 'artel.py'}"


def _guard_tool(task_id: str, artel: bool, file_arg: str = "") -> str:
    """Чем роль проверяет свой артефакт (SPEC 01M56G23ZQDHV2BKEVWWC22R96,
    требование 4): у артели — `scripts/guard.py` рабочего каталога, как
    прежде; у внешнего проекта его в рабочем каталоге нет, а разрешён роли
    только `artel.py` пульта — команда пульта `guard`."""
    if artel:
        return "scripts/guard.py"
    tail = f" {file_arg}" if file_arg else ""
    return f"командой пульта `{_pult_command()} guard {task_id}{tail}`"


def _plank_run_point(task_id: str, task_ref: str, artel: bool,
                     long_lived) -> str:
    """Пункт 5 задания test_author без завершающей точки. У внешнего
    проекта `python3 -m pytest` неверен (своя команда и `workdir` профиля,
    SPEC 01M56G23ZQDHV2BKEVWWC22R96, требование 8): и планка, и
    долгоживущие файлы — командой пульта `plank-run`, которая гонит их
    раннером профиля."""
    if artel:
        return (f"5) Прогони планку командой пульта `plank-run` (абзац о "
                f"каталоге документов ниже): она сама выложит черновик и "
                f"выполнит `python3 -m pytest {task_ref}/acceptance_tests -p "
                f"no:cacheprovider -p timeout -o "
                f"timeout={stack.PER_TEST_TIMEOUT_SEC}`"
                f"{_long_lived_run_note(long_lived)}")
    pult = _pult_command()
    point = (f"5) Прогони планку командой пульта `{pult} plank-run {task_id}` "
             f"(абзац о каталоге документов ниже): она сама выложит черновик "
             f"и прогонит его раннером проекта")
    if long_lived is not None:
        point += (f"; долгоживущие файлы {long_lived[0]}/ — той же командой "
                  f"по пути каждого файла: `{pult} plank-run {task_id} "
                  f"{long_lived[1]}`")
    return point


def _reviewer_checks_note(task_id: str, artel: bool) -> str:
    """Фраза миссии ревьювера о проверках (SPEC 01M56G23ZQDHV2BKEVWWC22R96,
    требование 9): у внешнего проекта права роли сужены до команд пульта
    белого списка ролей. `suite-run` в перечне нет: полный набор ревьюверу
    не положен (`REVIEWER_FULL_SUITE_RULE`, SPEC 01M5KP57JXWKKKCJKY47HT21W8)."""
    if artel:
        return ("Права не сужены: тесты, guard и другие исполняемые "
                "проверки запускай, когда они доказывают или опровергают "
                "замечание.")
    pult = _pult_command()
    return (f"Исполняемые проверки доступны только командами пульта: "
            f"`{pult} guard {task_id} [<файл>]` — структура артефактов, "
            f"`{pult} plank-run {task_id} [<файл>]` — планка и долгоживущие "
            f"файлы задачи; запускай их, когда они доказывают или "
            f"опровергают замечание.")


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
    directory, _example, star, _has_dir = long_lived
    return (f" Долгоживущие файлы задачи в {directory}/ ({star}) "
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
        f"вердикт недействительным. Прогони "
        f"{_guard_tool(task_id, artel, spec_audit.ARTIFACT)} на своём файле. "
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
    роль без такой команды сама делила набор на пачки и обходила сторож.
    Новый полный прогон шагу разработчика не положен (SPEC
    01M5HDB1GSFDKFM7QB9JZMCCWJ): `suite-run <id>` без флагов ему отказывает,
    миссия его и не предлагает."""
    pult = config.ROOT / "orchestrator" / "artel.py"
    return (
        f"Полный набор тестов гоняют CI и гейт приёмки — в шаге разработчика "
        f"новый полный прогон не запускай (`suite-run` без флагов роли "
        f"developer отказывает). Тесты затронутых модулей — `python3 -m "
        f"pytest tests/<файлы> …` в переднем плане; повтор только упавших — "
        f"`python3 {pult} suite-run {task_id} --failed` (работает только "
        f"после прогона Оператора или ревьювера: перечень упавших пишет "
        f"только `suite-run`), отчёт идущего прогона — `python3 {pult} "
        f"suite-run {task_id} --wait <минуты, не больше "
        f"{config.SUITE_RUN_MAX_WAIT_MIN}>`. Файлы tests/ в обход сторожа не "
        f"перечисляй и набор на пачки своими сценариями не дели.")


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
