"""Бриф роли несёт шаблон своего артефакта целиком с головы `main` пульта.

Группа: долгоживущий
Красен до реализации: функции брифа analyst/developer/spec_auditor ещё не кладут в бриф компоненты `templates/<имя>` и пометку «шаблон … не прочитан», а миссии этих ролей велят читать шаблон по `templates/<имя>` безусловно; методы AC-5 и два метода AC-8 о первом компоненте держат прежнее поведение (reviewer/test_author без шаблона, прежний первый компонент) и зелены с рождения.

Песочница — `tests.sandbox.TmpRootTest`: пути `config` во временном
каталоге, `gitcmd.git` — `fake_git` (сверка свежести карты отвечает
«расхождений нет»), `gitcmd.ls_tree_files` — `disk_backed_ls_tree_files`,
`gitcmd.show` — подмена этого файла. Шаблон `templates/<имя>` она отдаёт
текстом `main` только на ветке `config.MAIN_BRANCH` в репозитории
`config.ROOT` (или без `repo`); `main` иного репозитория (клона проекта)
отдаёт свой текст, любая иная ветка — третий; на диске
`config.ROOT/templates/` лежит четвёртый. Прочие пути — с диска
(`tests.sandbox.disk_backed_show`). Тексты шаблонов и причины отказа
порождаются от зерна при каждом запуске; зерно печатается и входит в
текст провала.

Функции брифа зовутся напрямую (`brief.analyst_map_component`,
`brief.developer_brief`, `brief.spec_auditor_brief`,
`brief.test_author_answer_component`); миссии и состав промпта
reviewer — штатным `role_prompt.mission_brief_package`.
"""
import hashlib
import random
import re
import string
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import brief, config, review, role_prompt, store
from orchestrator.advance_gates import spec_audit
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git)

TASK = "T001"
ROLE_TEMPLATES = {
    "analyst": ("SPEC.md", "QUESTIONS.md"),
    "developer": ("PLAN.md",),
    "spec_auditor": ("SPEC-AUDIT.md",),
}
ALL_TEMPLATES = ("SPEC.md", "QUESTIONS.md", "PLAN.md", "SPEC-AUDIT.md",
                 "REVIEW.md")
BUILDERS = {
    "analyst": "analyst_map_component",
    "developer": "developer_brief",
    "spec_auditor": "spec_auditor_brief",
}
TEMPLATE_DIR = "templates"
FAILED_ACTION = "бриф: шаблон не прочитан"
COMPONENT_ACTION = "бриф: компонент"
MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
             "---\n\n# Карта\n")
WORDS = ("критерий", "граница", "шаблон", "артефакт", "роль", "журнал",
         "опись", "часть", "пометка", "бриф", "ветка", "пульт")
PART_HEADER = re.compile(
    r"^--- ЧАСТЬ (\d+)/(\d+) \((\d+) байт, sha256=([0-9a-f]{64})\) ---\n\n",
    re.M)
HEADING = re.compile(r"^### (.+)$", re.M)


def label_of(name: str) -> str:
    return f"{TEMPLATE_DIR}/{name}"


def task_label(name: str) -> str:
    return f"{config.TASKS.name}/{TASK}/{name}"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def failed_note(name: str, reason: str) -> str:
    return f"шаблон {label_of(name)} не прочитан: {reason} — прочитай его сам"


def boundary_pattern() -> re.Pattern:
    """Регулярное выражение пары граничных маркеров — от публичного
    `brief.wrap_boundary`, не от литерала формата."""
    sample = brief.wrap_boundary("RIDTOKEN", "BODYTOKEN")
    open_line, _body, close_line = sample.split("\n")
    o_pre, o_suf = open_line.split("RIDTOKEN")
    c_pre, c_suf = close_line.split("RIDTOKEN")
    return re.compile(
        re.escape(o_pre) + r"(?P<rid>\S+)" + re.escape(o_suf)
        + r"\n(?P<body>.*?)\n" + re.escape(c_pre) + r"(?P=rid)"
        + re.escape(c_suf), re.S)


def blocks(text: str) -> list[dict]:
    """Компоненты в границах по порядку: метка ближайшего заголовка
    `### <метка>[ — опись]` перед открывающим маркером, id запуска, тело,
    позиции начала и конца."""
    found = []
    spans = [(m.start(), m.end(), m) for m in boundary_pattern().finditer(text)]
    headings = [(h.start(), h.group(1)) for h in HEADING.finditer(text)
                if not any(s <= h.start() < e for s, e, _ in spans)]
    for start, end, m in spans:
        before = [label for pos, label in headings if pos < start]
        label = before[-1].split(" — ")[0] if before else ""
        found.append({"label": label, "rid": m.group("rid"),
                      "body": m.group("body"), "start": start, "end": end})
    return found


def inside_any_block(text: str, pos: int) -> bool:
    return any(b["start"] <= pos < b["end"] for b in blocks(text))


def reassemble_parts(text: str) -> tuple[list[str], int]:
    """(содержимое частей по номеру, позиция первого заголовка части):
    каждая часть сверена с объявленными в её заголовке размером и sha256;
    провал сверки — `AssertionError`."""
    parts = []
    pos = 0
    first = -1
    total = None
    while total is None or len(parts) < total:
        m = PART_HEADER.search(text, pos)
        assert m is not None, f"нет заголовка части {len(parts) + 1}"
        n, total = int(m.group(1)), int(m.group(2))
        assert n == len(parts) + 1, f"часть {n} вместо {len(parts) + 1}"
        if first < 0:
            first = m.start()
        size, digest = int(m.group(3)), m.group(4)
        raw = text[m.end():].encode("utf-8")[:size]
        content = raw.decode("utf-8")
        assert len(raw) == size, f"часть {n}: объявлено {size} байт"
        assert sha256(content) == digest, f"часть {n}: sha256 не сходится"
        parts.append(content)
        pos = m.end() + len(content)
    return parts, first


def template_text(rng: random.Random, name: str, source: str) -> str:
    token = "".join(rng.choice(string.ascii_lowercase + string.digits)
                    for _ in range(16))
    lines = [" ".join(rng.choice(WORDS) for _ in range(rng.randint(3, 9)))
             for _ in range(rng.randint(5, 25))]
    return (f"---\ntask: TASK_ID\ntype: {name.lower()}\nstatus: draft\n---\n\n"
            f"# Шаблон {name} ИСТОЧНИК-{source}-{token}\n\n"
            + "\n".join(lines) + "\n")


class TemplateBriefSandbox(TmpRootTest):
    """Песочница брифа: карта, CLAUDE.md, SPEC задачи на диске и четыре
    расходящихся источника каждого шаблона."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        (self.root / "docs").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции проекта\n",
                                             encoding="utf-8")
        self.task_dir = config.TASKS / TASK
        self.task_dir.mkdir(parents=True, exist_ok=True)
        self.write_task("SPEC.md", "# SPEC\n\nМаркер-текста-SPEC.\n")
        store.create_schema(store.db())
        self.conn = store.db()
        self.broken = {}
        self.new_templates()
        for attr, value in (("show", self.fake_show),
                            ("ls_tree_files", disk_backed_ls_tree_files),
                            ("git", fake_git)):
            patcher = mock.patch(f"orchestrator.gitcmd.{attr}", value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def msg(self, extra: str = "") -> str:
        return f"зерно: {self.seed}. {extra}"

    def new_templates(self) -> None:
        """Свежие тексты четырёх источников каждого шаблона; диск
        `config.ROOT/templates/` переписывается."""
        self.main = {n: template_text(self.rng, n, "MAIN") for n in ALL_TEMPLATES}
        self.clone = {n: template_text(self.rng, n, "CLONE") for n in ALL_TEMPLATES}
        self.branch = {n: template_text(self.rng, n, "BRANCH") for n in ALL_TEMPLATES}
        self.disk = {n: template_text(self.rng, n, "DISK") for n in ALL_TEMPLATES}
        (self.root / TEMPLATE_DIR).mkdir(parents=True, exist_ok=True)
        for name, text in self.disk.items():
            (self.root / TEMPLATE_DIR / name).write_text(text, encoding="utf-8")

    def all_sources(self, name: str) -> dict[str, str]:
        return {"main": self.main[name], "клон": self.clone[name],
                "ветка": self.branch[name], "диск": self.disk[name]}

    def fake_show(self, branch: str, rel: str, *, repo=None) -> tuple:
        prefix = f"{TEMPLATE_DIR}/"
        if not rel.startswith(prefix):
            return disk_backed_show(branch, rel, repo=repo)
        name = rel[len(prefix):]
        if name in self.broken:
            return None, self.broken[name]
        if name not in self.main:
            return None, f"fatal: path '{rel}' does not exist"
        if branch != config.MAIN_BRANCH:
            return self.branch[name], ""
        if repo is not None and Path(repo).resolve() != Path(config.ROOT).resolve():
            return self.clone[name], ""
        return self.main[name], ""

    def write_task(self, name: str, text: str) -> None:
        (self.task_dir / name).write_text(text, encoding="utf-8")

    def seed_state(self, actor: str, state: str, detail: str = "") -> None:
        store.journal(self.conn, TASK, actor, f"state -> {state}", detail)

    def seed_return(self, role: str) -> None:
        token = self.rng.randrange(10 ** 6)
        if role == "analyst":
            self.seed_state("fsm", "spec_gate", "SPEC готов")
            self.seed_state("operator", "spec_writing",
                            f"возврат из spec_gate: причина-{token}")
        elif role == "developer":
            self.seed_state("fsm", "in_dev", "приёмочные тесты готовы")
            self.seed_state("operator", "review", "готово к ревью")
            self.seed_state("fsm", "in_dev", f"замечания ревью {token}")
        else:
            self.seed_state("fsm", "spec_audit", "SPEC готов к аудиту")
            self.seed_state("fsm", "escalated", f"аудит: вопрос {token}")
            self.write_task("ANSWER-1.md", "# ANSWER-1\n\nОК.\n")
            self.seed_state("operator", "spec_audit",
                            "эскалация разрешена, продолжаем")

    def seed_optional_components(self, role: str) -> None:
        """Все необязательные прежние компоненты брифа роли — чтобы шаблон
        было с чем сравнить по порядку."""
        self.write_task("ANSWER-1.md", "# ANSWER-1\n\nМАРКЕР-ANSWER.\n")
        if role == "analyst":
            self.write_task("QUESTIONS.md", "# QUESTIONS\n\nМАРКЕР-QUESTION.\n")
        elif role == "developer":
            self.write_task("PLAN.md", "# PLAN\n\nМАРКЕР-PLAN.\n")
            self.write_task("REVIEW.md", "# REVIEW\n\nМАРКЕР-REVIEW.\n")
        else:
            self.write_task("TZ.md", "# ТЗ\n\nМАРКЕР-ТЗ.\n")
            self.seed_state("fsm", "spec_gate", "SPEC готов")
            self.seed_state("operator", "spec_writing",
                            "возврат из spec_gate: решение Оператора")
            self.seed_state("fsm", "spec_audit", "SPEC готов к аудиту")

    def last_step_id(self) -> int:
        row = self.conn.execute("SELECT MAX(id) AS m FROM steps").fetchone()
        return row["m"] or 0

    def steps_after(self, step_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT id, actor, action, detail FROM steps WHERE id > ? "
            "ORDER BY id", (step_id,))]

    def build(self, role: str) -> tuple[str, list[dict]]:
        """(текст брифа, записи журнала, сделанные сборкой) — функция брифа
        роли зовётся напрямую; падение сборки — провал с зерном."""
        before = self.last_step_id()
        try:
            text = getattr(brief, BUILDERS[role])(self.conn, TASK)
        except BaseException as exc:  # noqa: BLE001 — SystemExit тоже провал
            self.fail(self.msg(f"сборка брифа {role} упала: {exc!r}"))
        return text, self.steps_after(before)

    def template_blocks(self, text: str, name: str) -> list[dict]:
        return [b for b in blocks(text) if b["label"] == label_of(name)]

    def assert_template_component(self, role: str, text: str, name: str,
                                  rid: str) -> None:
        """Шаблон `name` стоит ровно одним компонентом с меткой
        `templates/<имя>`, тело — текст `main`, граница — с id `rid`."""
        found = self.template_blocks(text, name)
        self.assertEqual(len(found), 1, self.msg(
            f"{role}: компонентов {label_of(name)} — {len(found)}"))
        self.assertEqual(found[0]["body"], self.main[name].strip(), self.msg(
            f"{role}: тело {label_of(name)} — не текст main целиком"))
        self.assertEqual(found[0]["rid"], rid, self.msg(
            f"{role}: граница {label_of(name)} — чужой id запуска"))


class AnalystTemplatesTest(TemplateBriefSandbox):

    def test_ac1_analyst_brief_carries_spec_and_questions_templates_in_map_boundary(self):
        """Бриф analyst несёт целиком `templates/SPEC.md` и `templates/QUESTIONS.md`.

        Сценарий: три раза подряд с новыми текстами шаблонов
        `brief.analyst_map_component` собирает бриф. В нём оба шаблона —
        каждый отдельным компонентом с меткой `templates/<имя>`, тело в
        границе — текст `main` целиком, id границы — тот же, что у карты
        кодовой базы этого брифа.

        Ловит мутацию: analyst получил PLAN вместо SPEC и QUESTIONS (таблица
        «роль → шаблоны» перепутана) — компонентов `templates/SPEC.md` и
        `templates/QUESTIONS.md` в брифе нет; analyst получил только один из
        двух шаблонов — второго компонента нет; шаблон дописан снаружи к
        тексту `analyst_map_component` под своим `new_run_id()` — id
        границы шаблона не равен id границы карты."""
        for _ in range(3):
            self.new_templates()
            text, _steps = self.build("analyst")
            maps = [b for b in blocks(text)
                    if b["label"] == brief.MAP_PROJECTION_LABEL]
            self.assertEqual(len(maps), 1, self.msg("карта в брифе не найдена"))
            for name in ROLE_TEMPLATES["analyst"]:
                self.assert_template_component("analyst", text, name,
                                               maps[0]["rid"])


class DeveloperAndAuditorTemplatesTest(TemplateBriefSandbox):

    def first_task_block(self, text: str, role: str) -> dict:
        own = task_label("SPEC.md")
        found = [b for b in blocks(text) if b["label"] == own]
        self.assertTrue(found, self.msg(f"{role}: компонента {own} нет"))
        return found[0]

    def check_role_template(self, role: str) -> None:
        name = ROLE_TEMPLATES[role][0]
        for _ in range(3):
            self.new_templates()
            text, _steps = self.build(role)
            rid = self.first_task_block(text, role)["rid"]
            self.assert_template_component(role, text, name, rid)
            header = [h.group(1) for h in HEADING.finditer(text)
                      if h.group(1).split(" — ")[0] == label_of(name)]
            size = len(self.main[name].encode("utf-8"))
            self.assertEqual(
                header, [f"{label_of(name)} — {size} байт, "
                         f"sha256={sha256(self.main[name])}"],
                self.msg(f"{role}: шаблон не внесён в опись брифа"))

    def check_parts(self, role: str) -> None:
        """Бриф крупнее потолка части: шаблон — внутри пронумерованных
        частей, части сверены, граница шаблона — общего id запуска."""
        name = ROLE_TEMPLATES[role][0]
        for _ in range(3):
            self.new_templates()
            whole_text, _steps = self.build(role)
            cap = max(len(whole_text.encode("utf-8")) // 3, 256)
            with mock.patch.object(config, "CONTEXT_PART_MAX_BYTES", cap):
                text, _steps = self.build(role)
            parts, first_header = reassemble_parts(text)
            self.assertGreater(len(parts), 1, self.msg("бриф не поделён"))
            whole = "".join(parts)
            self.assertTrue(whole.startswith(brief.HEADER), self.msg(
                "конкатенация частей не начинается шапкой брифа"))
            rid = self.first_task_block(whole, role)["rid"]
            self.assert_template_component(role, whole, name, rid)
            title = next(ln for ln in self.main[name].splitlines()
                         if "ИСТОЧНИК-" in ln)
            self.assertGreater(text.find(title), first_header, self.msg(
                f"{role}: шаблон лежит вне пронумерованных частей"))
            rids = {b["rid"] for b in blocks(whole)}
            self.assertEqual(len(rids), 1, self.msg(
                f"{role}: в брифе границы разных запусков: {rids}"))

    def test_ac2_developer_brief_carries_plan_template_with_manifest(self):
        """Бриф developer несёт целиком `templates/PLAN.md` в описи и границе.

        Сценарий: три раза с новыми текстами шаблонов `brief.developer_brief`
        собирает бриф. В нём один компонент `templates/PLAN.md`: заголовок
        описи несёт размер и sha256 текста `main`, тело в границе — этот
        текст целиком, id границы — тот же, что у компонента SPEC задачи.

        Ловит мутацию: developer не получил шаблон PLAN (строки developer в
        таблице нет или чтение не вызвано) — компонента `templates/PLAN.md`
        нет; шаблон оформлен `_journal_component` вместо
        `_manifest_component` — заголовок без размера и sha256."""
        self.check_role_template("developer")

    def test_ac2_developer_template_goes_through_parts(self):
        """Шаблон PLAN проходит деление брифа developer на части.

        Сценарий: потолок части `config.CONTEXT_PART_MAX_BYTES` — треть
        размера брифа; бриф поделён на пронумерованные части. Каждая часть
        сверена с объявленными размером и sha256, конкатенация частей
        начинается шапкой брифа и несёт компонент `templates/PLAN.md` с
        текстом `main` и границей того же id, что у SPEC; строка
        заголовка шаблона стоит после заголовка первой части.

        Ловит мутацию: шаблон дописан к тексту после
        `context_package.discipline` под своим `new_run_id()` — в
        конкатенации частей компонента нет, а его граница несёт чужой id."""
        self.check_parts("developer")

    def test_ac3_spec_auditor_brief_carries_spec_audit_template_with_manifest(self):
        """Бриф spec_auditor несёт целиком `templates/SPEC-AUDIT.md` в описи и границе.

        Сценарий: три раза с новыми текстами шаблонов
        `brief.spec_auditor_brief` собирает бриф. В нём один компонент
        `templates/SPEC-AUDIT.md`: заголовок описи несёт размер и sha256
        текста `main`, тело в границе — этот текст целиком, id границы —
        тот же, что у компонента SPEC задачи.

        Ловит мутацию: spec_auditor не получил SPEC-AUDIT (строки
        spec_auditor в таблице нет) — компонента `templates/SPEC-AUDIT.md`
        нет; шаблон без описи — заголовок без размера и sha256."""
        self.check_role_template("spec_auditor")

    def test_ac3_spec_auditor_template_goes_through_parts(self):
        """Шаблон SPEC-AUDIT проходит деление брифа spec_auditor на части.

        Сценарий: тот же, что у developer, — потолок части равен трети
        размера брифа, части сверены по размеру и sha256, конкатенация
        несёт компонент `templates/SPEC-AUDIT.md` с текстом `main` и
        границей общего id, строка заголовка шаблона — после заголовка
        первой части.

        Ловит мутацию: шаблон дописан после `context_package.discipline`
        под своим `new_run_id()` — в конкатенации частей компонента нет,
        граница несёт чужой id."""
        self.check_parts("spec_auditor")


class OnlyOwnTemplatesTest(TemplateBriefSandbox):

    def test_ac4_each_role_gets_only_its_table_row(self):
        """Каждая роль получает только шаблоны своей строки таблицы.

        Сценарий: для analyst, developer и spec_auditor собирается бриф.
        Ни компонента, ни пометки «не прочитан», ни текста любого источника
        чужого шаблона (из `templates/SPEC.md`, `QUESTIONS.md`, `PLAN.md`,
        `SPEC-AUDIT.md`, `REVIEW.md` вне строки роли) в брифе нет; свои —
        ровно по одному компоненту.

        Ловит мутацию: всем ролям кладётся объединение строк таблицы (или
        общий список шаблонов) — у developer появляется
        `templates/SPEC.md`, у analyst — `templates/PLAN.md`; analyst
        получил PLAN вместо SPEC и QUESTIONS."""
        for role, own in ROLE_TEMPLATES.items():
            with self.subTest(role=role):
                text, _steps = self.build(role)
                for name in ALL_TEMPLATES:
                    found = self.template_blocks(text, name)
                    if name in own:
                        self.assertEqual(len(found), 1, self.msg(
                            f"{role}: своего {label_of(name)} — {len(found)}"))
                        continue
                    self.assertEqual(found, [], self.msg(
                        f"{role}: чужой компонент {label_of(name)}"))
                    self.assertNotIn(f"шаблон {label_of(name)} не прочитан",
                                     text, self.msg(f"{role}: чужая пометка"))
                    for source, body in self.all_sources(name).items():
                        self.assertNotIn(body.strip(), text, self.msg(
                            f"{role}: текст «{source}» чужого {label_of(name)}"))


class ReviewerAndTestAuthorTest(TemplateBriefSandbox):

    def test_ac5_test_author_brief_has_no_template(self):
        """Бриф test_author не несёт ни одного шаблона из `templates/`.

        Сценарий: test_author возвращён из эскалации и есть ANSWER-1 —
        `brief.test_author_answer_component` отдаёт непустой бриф. В нём
        нет компонента `templates/<имя>`, пометки «шаблон … не прочитан» и
        текста любого источника любого шаблона.

        Ловит мутацию: test_author получил шаблон (строка test_author
        добавлена в таблицу, сборщик test_author дописывает компоненты
        шаблонов) — в брифе появляется компонент `templates/<имя>`."""
        self.seed_state("operator", "tests_writing", "гейт SPEC пройден")
        self.seed_state("fsm", "escalated", "test_author: вопрос")
        self.write_task("ANSWER-1.md", "# ANSWER-1\n\nМАРКЕР-ANSWER.\n")
        self.seed_state("operator", "tests_writing",
                        "эскалация разрешена, продолжаем")
        text = brief.test_author_answer_component(self.conn, TASK)
        self.assertIsNotNone(text, self.msg("бриф test_author не собран"))
        self.assertIn("МАРКЕР-ANSWER", text)
        for b in blocks(text):
            self.assertFalse(b["label"].startswith(f"{TEMPLATE_DIR}/"),
                             self.msg(f"компонент шаблона: {b['label']}"))
        self.assertNotIn("не прочитан", text, self.msg("пометка о шаблоне"))
        for name in ALL_TEMPLATES:
            for source, body in self.all_sources(name).items():
                self.assertNotIn(body.strip(), text, self.msg(
                    f"текст «{source}» {label_of(name)} в брифе test_author"))

    def test_ac5_reviewer_prompt_has_review_form_once_from_package(self):
        """Форма REVIEW входит в промпт reviewer один раз — из ревью-пакета.

        Сценарий: `role_prompt.mission_brief_package` собирает шаг
        reviewer; ревью-пакет подменён текстом, несущим форму
        `templates/REVIEW.md` (текст `main`) ровно один раз. В миссии,
        брифе и пакете вместе форма встречается один раз, бриф reviewer
        пуст, текстов прочих шаблонов нет ни в одном источнике.

        Ловит мутацию: reviewer получил шаблон (строка reviewer добавлена в
        таблицу, `mission_brief_package` собирает reviewer бриф с
        шаблонами) — форма REVIEW в промпте дважды или в брифе появляется
        компонент `templates/<имя>`."""
        package = f"РЕВЬЮ-ПАКЕТ\n\n## Форма\n\n{self.main['REVIEW.md']}"
        t = {"branch": f"task/{self.rng.randrange(10 ** 6)}-x",
             "title": "Фикстура", "reviewed_iter": 0}
        with mock.patch.object(review, "review_package",
                               return_value=package), \
                mock.patch.object(review, "previous_verdict_sha",
                                  return_value=""):
            mission, brief_text, got = role_prompt.mission_brief_package(
                self.conn, TASK, t, "reviewer", "/tmp/cwd")
        prompt = "\n".join([mission, brief_text or "", str(got)])
        self.assertEqual(prompt.count(self.main["REVIEW.md"].strip()), 1,
                         self.msg("форма REVIEW в промпте reviewer не один раз"))
        self.assertFalse(brief_text, self.msg("у reviewer появился бриф"))
        for name in ALL_TEMPLATES:
            for source, body in self.all_sources(name).items():
                if name == "REVIEW.md" and source == "main":
                    continue
                self.assertNotIn(body.strip(), prompt, self.msg(
                    f"текст «{source}» {label_of(name)} в промпте reviewer"))


class MainBranchSourceTest(TemplateBriefSandbox):

    def test_ac6_template_comes_from_pult_main_not_disk_branch_or_clone(self):
        """Шаблон в брифе — текст `main` пульта, не диска, ветки или клона.

        Сценарий: у каждого шаблона четыре разных текста — `main` в
        `config.ROOT`, `main` иного репозитория (клона проекта), иная ветка
        и файл на диске `config.ROOT/templates/`. Для analyst, developer и
        spec_auditor в брифе тело компонента шаблона — текст `main`
        пульта; текстов трёх прочих источников в брифе нет.

        Ловит мутацию: шаблон прочитан с диска (`config.ROOT /
        "templates" / имя`), с ветки задачи (`artifact_branch.show`) или с
        `main` клона проекта (`repo=<клон>`) — в брифе текст диска, ветки
        или клона вместо текста `main`."""
        for role, own in ROLE_TEMPLATES.items():
            with self.subTest(role=role):
                self.new_templates()
                text, _steps = self.build(role)
                for name in own:
                    found = self.template_blocks(text, name)
                    self.assertEqual([b["body"] for b in found],
                                     [self.main[name].strip()], self.msg(
                                         f"{role}: {label_of(name)} не с main"))
                    for source, body in self.all_sources(name).items():
                        if source != "main":
                            self.assertNotIn(body.strip(), text, self.msg(
                                f"{role}: текст «{source}» {label_of(name)}"))


class TemplateJournalTest(TemplateBriefSandbox):

    def test_ac7_journal_has_component_record_with_raw_text_sha(self):
        """На каждый прочитанный шаблон — запись «бриф: компонент» с sha256 исходного текста.

        Сценарий: три раза с новыми текстами шаблонов собираются брифы
        трёх ролей. Среди записей сборки у каждого своего шаблона есть
        запись актора-роли с действием «бриф: компонент», чья деталь несёт
        метку `templates/<имя>` и sha256 текста `main` до обёртки (текст
        оканчивается переводом строки, поэтому sha256 обрезанного или
        обёрнутого текста от него отличается); записи с той же меткой и
        иным sha256 нет.

        Ловит мутацию: компонент шаблона собран без записи журнала (тело
        обёрнуто `wrap_boundary` напрямую) — записи нет; в журнал пишется
        sha256 обёрнутого или `.strip()`-нутого текста — sha256 записи не
        равен sha256 исходного текста шаблона."""
        for _ in range(3):
            self.new_templates()
            for role, own in ROLE_TEMPLATES.items():
                _text, steps = self.build(role)
                for name in own:
                    expected = sha256(self.main[name])
                    labelled = [s for s in steps
                                if s["action"] == COMPONENT_ACTION
                                and label_of(name) in (s["detail"] or "")]
                    self.assertTrue(labelled, self.msg(
                        f"{role}: нет записи «{COMPONENT_ACTION}» "
                        f"{label_of(name)}"))
                    for s in labelled:
                        self.assertEqual(s["actor"], role, self.msg(str(s)))
                        self.assertIn(expected, s["detail"], self.msg(
                            f"{role}: sha256 записи {s['detail']!r} — не "
                            f"исходного текста {expected}"))


class TemplateOrderTest(TemplateBriefSandbox):

    def expected_first(self, role: str, with_tz: bool) -> str:
        if role == "analyst":
            return brief.MAP_PROJECTION_LABEL
        if role == "spec_auditor" and with_tz:
            return task_label("TZ.md")
        return task_label("SPEC.md")

    def check_first(self, role: str, expected: str, text: str,
                    steps: list[dict]) -> None:
        found = blocks(text)
        self.assertTrue(found, self.msg(f"{role}: в брифе нет компонентов"))
        self.assertEqual(found[0]["label"], expected, self.msg(
            f"{role}: первый компонент брифа"))
        records = [s for s in steps if s["action"] == COMPONENT_ACTION]
        self.assertTrue(records, self.msg(f"{role}: нет записей компонентов"))
        self.assertTrue(records[0]["detail"].startswith(f"{expected}: "),
                        self.msg(f"{role}: первая запись журнала брифа — "
                                 f"{records[0]['detail']!r}"))

    def test_ac8_first_component_unchanged_without_return(self):
        """Без возврата первый компонент и первая запись журнала брифа — прежние.

        Сценарий: визит без возврата; у spec_auditor — и с ТЗ, и без него.
        Первый компонент брифа и первая запись «бриф: компонент» сборки —
        карта кодовой базы у analyst, SPEC.md задачи у developer, TZ.md
        задачи у spec_auditor (SPEC.md задачи, если ТЗ нет).

        Ловит мутацию: компоненты шаблонов поставлены перед существующими
        компонентами брифа (вставлены в начало `parts`) — первым идёт
        `templates/<имя>`, и первая запись журнала брифа — запись шаблона."""
        cases = [("analyst", False), ("developer", False),
                 ("spec_auditor", False), ("spec_auditor", True)]
        for role, with_tz in cases:
            with self.subTest(role=role, with_tz=with_tz):
                tz = self.task_dir / "TZ.md"
                if with_tz:
                    self.write_task("TZ.md", "# ТЗ\n\nМАРКЕР-ТЗ.\n")
                elif tz.exists():
                    tz.unlink()
                text, steps = self.build(role)
                self.check_first(role, self.expected_first(role, with_tz),
                                 text, steps)

    def test_ac8_return_reason_stays_first_on_return_visit(self):
        """На визите с возвратом первой идёт «Причина возврата» у трёх ролей.

        Сценарий: для analyst (возврат с гейта SPEC), developer (замечания
        ревью) и spec_auditor (возврат из эскалации) журнал засеян
        возвратом; первый компонент брифа и первая запись «бриф: компонент»
        сборки — «Причина возврата».

        Ловит мутацию: компонент шаблона поставлен перед разделом «Причина
        возврата» — первым идёт `templates/<имя>`."""
        for role in ROLE_TEMPLATES:
            with self.subTest(role=role):
                self.seed_return(role)
                text, steps = self.build(role)
                self.check_first(role, brief.RETURN_REASON_HEADER, text, steps)

    def test_ac8_templates_follow_all_previous_components(self):
        """Компоненты шаблонов стоят после всех прежних компонентов роли.

        Сценарий: у задачи есть все необязательные прежние компоненты роли
        (ANSWER-1; QUESTIONS у analyst; PLAN и REVIEW у developer; ТЗ и
        решение Оператора на гейте SPEC у spec_auditor). Каждый компонент
        `templates/<имя>` в брифе стоит позже каждого компонента с иной
        меткой.

        Ловит мутацию: шаблон вставлен между прежними компонентами (до
        ANSWER-n, до карты у spec_auditor, сразу после SPEC у developer) —
        за компонентом шаблона следует прежний компонент брифа."""
        for role, own in ROLE_TEMPLATES.items():
            with self.subTest(role=role):
                self.seed_optional_components(role)
                text, _steps = self.build(role)
                found = blocks(text)
                labels = {label_of(n) for n in own}
                tpl = [i for i, b in enumerate(found) if b["label"] in labels]
                rest = [i for i, b in enumerate(found)
                        if b["label"] not in labels]
                self.assertEqual(len(tpl), len(own), self.msg(
                    f"{role}: шаблонов в брифе {len(tpl)}"))
                self.assertTrue(rest, self.msg(f"{role}: прежних нет"))
                self.assertGreater(min(tpl), max(rest), self.msg(
                    f"{role}: порядок {[b['label'] for b in found]}"))


class TemplateReadFailureTest(TemplateBriefSandbox):

    REASONS = ("git не ответил", "fatal: invalid object name 'main'")

    def check_failure(self, role: str, failing: tuple, reason: str) -> None:
        self.broken = {name: reason for name in failing}
        text, steps = self.build(role)
        for name in ROLE_TEMPLATES[role]:
            if name not in failing:
                self.assertEqual(len(self.template_blocks(text, name)), 1,
                                 self.msg(f"{role}: прочитанного "
                                          f"{label_of(name)} нет"))
                continue
            note = failed_note(name, reason)
            pos = text.find(note)
            self.assertGreaterEqual(pos, 0, self.msg(
                f"{role}: нет пометки «{note}»"))
            self.assertFalse(inside_any_block(text, pos), self.msg(
                f"{role}: пометка внутри границы"))
            self.assertEqual(self.template_blocks(text, name), [], self.msg(
                f"{role}: компонент непрочитанного {label_of(name)}"))
            self.assertNotIn(self.disk[name].strip(), text, self.msg(
                f"{role}: вместо пометки — текст {label_of(name)} с диска"))
            failed = [s for s in steps if s["action"] == FAILED_ACTION
                      and label_of(name) in (s["detail"] or "")]
            self.assertEqual(len(failed), 1, self.msg(
                f"{role}: записей «{FAILED_ACTION}» {label_of(name)}: "
                f"{steps}"))
            self.assertEqual(failed[0]["actor"], role, self.msg(
                f"{role}: актор записи — {failed[0]['actor']}"))
            self.assertIn(reason, failed[0]["detail"], self.msg(
                f"{role}: в детали записи нет причины"))
            self.assertFalse(
                [s for s in steps if s["action"] == COMPONENT_ACTION
                 and (s["detail"] or "").startswith(f"{label_of(name)}:")],
                self.msg(f"{role}: неудача записана как «{COMPONENT_ACTION}»"))

    def test_ac9_unread_template_leaves_note_and_journal_record(self):
        """Непрочитанный шаблон — пометка вне границы и запись журнала, бриф собран.

        Сценарий: шаблон лежит на диске `config.ROOT/templates/<имя>`, а
        `show main:templates/<имя>` отвечает отказом с причиной («git не
        ответил» или отказ git). Для developer и spec_auditor бриф
        собирается без падения; на месте компонента вне границы стоит
        «шаблон templates/<имя> не прочитан: <причина> — прочитай его
        сам»; текста с диска нет; в журнале ровно одна запись актора-роли с
        действием «бриф: шаблон не прочитан», деталь несёт
        `templates/<имя>` и причину; записи «бриф: компонент» этой метки
        нет.

        Ловит мутацию: при неудаче чтения компонент тихо пропал (нет
        пометки или записи журнала); сборка брифа упала (`sys.exit` через
        `_main_branch_text`); неудача записана не от имени роли (актор
        `brief`/`fsm`) либо общим действием «бриф: компонент»; деталь
        записи без имени шаблона или без причины; при отказе git шаблон
        прочитан с диска."""
        for role in ("developer", "spec_auditor"):
            for reason in self.REASONS:
                with self.subTest(role=role, reason=reason):
                    self.new_templates()
                    self.check_failure(role, ROLE_TEMPLATES[role], reason)

    def test_ac9_analyst_reports_each_unread_template_by_name(self):
        """У analyst пометка и запись — отдельно на каждый из двух шаблонов.

        Сценарий: не читается только `templates/SPEC.md`, только
        `templates/QUESTIONS.md` или оба; причина — со случайным словом.
        На каждый непрочитанный — своя пометка вне границы и своя запись
        «бриф: шаблон не прочитан» актора analyst с именем и причиной;
        прочитанный при этом остаётся компонентом.

        Ловит мутацию: одна общая пометка/запись на оба шаблона analyst
        (или по имени только первого) — для `templates/QUESTIONS.md` нет
        своей пометки или записи; неудача одного шаблона роняет и второй
        компонент."""
        token = "".join(self.rng.choice(string.ascii_lowercase)
                        for _ in range(10))
        reason = f"fatal: bad object {token}"
        for failing in (("SPEC.md",), ("QUESTIONS.md",),
                        ("SPEC.md", "QUESTIONS.md")):
            with self.subTest(failing=failing):
                self.new_templates()
                self.check_failure("analyst", failing, reason)


class MissionTemplateWordingTest(unittest.TestCase):

    def missions(self, rng: random.Random) -> dict[str, str]:
        alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
        task_id = "01M" + "".join(rng.choice(alphabet) for _ in range(23))
        t = {"branch": f"task/{task_id.lower()}-x", "title": "x",
             "reviewed_iter": 0}
        out = {}
        with mock.patch.object(brief, "analyst_map_component",
                               return_value=""), \
                mock.patch.object(brief, "developer_brief", return_value=""), \
                mock.patch.object(brief, "spec_auditor_brief",
                                  return_value=""), \
                mock.patch.object(spec_audit, "entry", return_value=None):
            for role in ROLE_TEMPLATES:
                mission, _b, _p = role_prompt.mission_brief_package(
                    None, task_id, t, role, f"/tmp/cwd-{rng.randrange(999)}")
                out[role] = mission
        return out

    def test_ac10_missions_point_to_brief_and_read_disk_only_on_failure_note(self):
        """Миссии analyst, developer, spec_auditor: шаблон — в БРИФЕ РОЛИ, диск — только при пометке.

        Сценарий: миссии трёх ролей собраны штатным
        `role_prompt.mission_brief_package` для нескольких случайных id
        (сборщики брифа подменены пустыми). Каждая миссия называет
        `templates/<имя>` своих шаблонов; есть строка, где шаблон назван в
        БРИФЕ РОЛИ; есть строка с оговоркой «не прочитан»; каждая строка,
        где назван `templates/<имя>`, говорит либо о БРИФЕ РОЛИ, либо об
        оговорке «не прочитан» — безусловного «по templates/<имя>» нет.

        Ловит мутацию: миссия developer велит читать `templates/PLAN.md`
        безусловно («напиши PLAN.md по templates/PLAN.md» без оговорки о
        пометке «не прочитан»); миссия не говорит, что шаблон — в брифе;
        имя шаблона из миссии убрано."""
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for _ in range(3):
            for role, mission in self.missions(rng).items():
                lines = mission.splitlines()
                with self.subTest(role=role):
                    self.assertTrue(
                        any("шаблон" in ln.lower() and "БРИФЕ РОЛИ" in ln
                            for ln in lines),
                        f"зерно: {seed}. {role}: нет строки «шаблон … в "
                        f"БРИФЕ РОЛИ»\n{mission}")
                    self.assertTrue(
                        any("не прочитан" in ln for ln in lines),
                        f"зерно: {seed}. {role}: нет оговорки «не "
                        f"прочитан»\n{mission}")
                    for name in ROLE_TEMPLATES[role]:
                        label = label_of(name)
                        named = [ln for ln in lines if label in ln]
                        self.assertTrue(named, f"зерно: {seed}. {role}: "
                                               f"имени {label} нет")
                        for ln in named:
                            self.assertTrue(
                                "не прочитан" in ln or "БРИФ" in ln,
                                f"зерно: {seed}. {role}: безусловное "
                                f"указание на {label}: {ln!r}")


if __name__ == "__main__":
    unittest.main()
