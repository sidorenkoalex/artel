"""Строка-подсказка о команде `knowledge` в миссии пяти ролей
(`role_prompt.mission_brief_package`): форма строки, перечень тем без текста
карточек, предел ключей, «тем нет», отказ чтения вида и его единственная
запись в журнале шага за визит, проект задачи по строке задачи.

Связка «сборка миссии — git — БД»: песочница — настоящий git-репозиторий
пульта (`RealGitSandbox`) с `knowledge/system.yaml` и `knowledge/artel.yaml`
в голове `main`, временный `targets.yaml`, файлы карточек внешних проектов
на диске их областей; голая песочница без `.git`, `targets.yaml` и файлов
карточек — `TmpRootTest`. Компоненты брифа и ревью-пакета подменены пустыми
(предмет — только текст миссии). Ключи и тексты карточек порождаются от
зерна (печатается).

Группа: долгоживущий
Красен до реализации: модуля orchestrator.knowledge_cards ещё нет, а role_prompt.mission_brief_package не дописывает строку о команде knowledge — его импорт внутри тестов падает ModuleNotFoundError, констант config.KNOWLEDGE_CARD_* (К-4а) нет — AttributeError.
"""
import importlib
import random
import unittest
from contextlib import ExitStack
from unittest import mock

from orchestrator import brief, config, review, role_prompt, store
from orchestrator.advance_gates import spec_audit
from tests.sandbox import RealGitSandbox, TmpRootTest, artel_target_entry


def knowledge_cards_module():
    """Модуль карточек — импорт в тесте, чтобы файл собирался и до реализации."""
    return importlib.import_module("orchestrator.knowledge_cards")


ROLES = ("analyst", "spec_auditor", "test_author", "developer", "reviewer")
ALPHA = "alphaproj"
BETA = "betaproj"
SYSTEM_REL = "knowledge/system.yaml"
ARTEL_REL = "knowledge/artel.yaml"

_EXTERNAL_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    knowledge: .artel/projects/{name}/knowledge/cards.yaml
"""


def card_block(key: str, token: str) -> str:
    return (f"  {key}:\n"
            f"    where: [src/{token}.py]\n"
            f"    rule: правило {token}\n"
            f"    why: причина {token}\n")


def build_missions(conn, task_id: str, t) -> dict:
    """Миссии пяти ролей штатной сборкой; бриф и пакет — пустые."""
    with ExitStack() as stack:
        for target, name, value in (
                (brief, "analyst_map_component", ""),
                (brief, "test_author_answer_component", None),
                (brief, "developer_brief", ""),
                (brief, "spec_auditor_brief", ""),
                (spec_audit, "entry", {}),
                (review, "review_package", ""),
                (review, "previous_verdict_sha", "")):
            stack.enter_context(mock.patch.object(target, name,
                                                  return_value=value))
        cwd = f"/tmp/fixture-cwd-{task_id}"
        return {role: role_prompt.mission_brief_package(
            conn, task_id, t, role, cwd)[0] for role in ROLES}


def pult_path() -> str:
    return str(config.ROOT / "orchestrator" / "artel.py")


def hint_lines(mission: str) -> list:
    return [line for line in mission.splitlines()
            if "knowledge" in line and pult_path() in line]


def hint_records(task_id: str) -> list:
    return [r for r in store.task_steps(store.db(), task_id)
            if r["action"] == knowledge_cards_module().HINT_REFUSAL_ACTION]


class HintSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.use_role_map()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        entry = artel_target_entry().replace(
            "    merge_gate: operator\n",
            f"    merge_gate: operator\n    knowledge: {ARTEL_REL}\n", 1)
        text = "targets:\n" + entry + "".join(
            _EXTERNAL_ENTRY.format(name=n, base=config.MAIN_BRANCH)
            for n in (ALPHA, BETA))
        config.TARGETS.parent.mkdir(parents=True, exist_ok=True)
        config.TARGETS.write_text(text, encoding="utf-8")
        self.conn = store.db()

    def keys(self, count: int, tag: str) -> list:
        """`count` различных ключей, ни один не подстрока другого."""
        stem = "".join(self.rng.choice("abcdefghijkmnpqrstuvwxyz")
                       for _ in range(5))
        return [f"{stem}-{tag}{i:03d}x" for i in range(count)]

    def cards(self, keys: list) -> str:
        shuffled = list(keys)
        self.rng.shuffle(shuffled)
        return "cards:\n" + "".join(card_block(k, f"t{k}") for k in shuffled)

    def commit_main(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "карточки")

    def project_cards(self, name: str, text: str) -> None:
        path = config.PROJECTS / name / "knowledge" / "cards.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def add_task(self, task_id: str, target: str | None):
        store.insert_task(self.conn, task_id, "Задача", "tests_writing",
                          f"task/{task_id.lower()}-zadacha",
                          target or config.DEFAULT_TARGET, 25.0)
        if target is None:
            self.conn.execute("UPDATE tasks SET target=NULL WHERE id=?",
                              (task_id,))
            self.conn.commit()
        return store.get_task(self.conn, task_id)


class HintLineTest(HintSandbox):
    """AC-15: строка-подсказка при заведённых карточках."""

    def test_ac15_each_role_has_one_hint_with_both_kinds_no_card_text(self):
        """Две системные карточки и две проектные карточки проекта ALPHA;
        задача ALPHA, строка задачи — `store.get_task` (`sqlite3.Row`).

        Наблюдение: в миссии каждой из пяти ролей ровно одна строка с полным
        путём к `artel.py` пульта и `knowledge`; она несёт id задачи,
        «только чтение» и все четыре ключа; текста карточек (правил,
        причин) в миссии нет; карточки проекта BETA не названы.

        Ловит мутацию: строка дописана только в ветку одной роли (например
        developer), а не в общий хвост — у остальных ролей строки нет.
        """
        sys_keys, alpha_keys = self.keys(2, "s"), self.keys(2, "a")
        beta_keys = self.keys(2, "b")
        self.commit_main({SYSTEM_REL: self.cards(sys_keys)})
        self.project_cards(ALPHA, self.cards(alpha_keys))
        self.project_cards(BETA, self.cards(beta_keys))
        row = self.add_task("T501", ALPHA)
        missions = build_missions(self.conn, "T501", row)
        for role, mission in missions.items():
            with self.subTest(role):
                lines = hint_lines(mission)
                self.assertEqual(len(lines), 1,
                                 f"зерно: {self.seed}; {role}\n{mission}")
                line = lines[0]
                self.assertIn("T501", line)
                self.assertIn("только чтение", line)
                for key in sys_keys + alpha_keys:
                    self.assertIn(key, line, f"зерно: {self.seed}; {role}")
                for key in beta_keys:
                    self.assertNotIn(key, mission, f"зерно: {self.seed}")
                for key in sys_keys + alpha_keys:
                    self.assertNotIn(f"правило t{key}", mission)
                    self.assertNotIn(f"причина t{key}", mission)
        self.assertEqual(hint_records("T501"), [])

    def test_ac15_keys_capped_with_rest_count(self):
        """Системных и проектных ключей вместе больше
        `KNOWLEDGE_CARD_HINT_MAX_KEYS`.

        Наблюдение: строка-подсказка называет не больше
        `KNOWLEDGE_CARD_HINT_MAX_KEYS` ключей и несёт «и ещё N», где N —
        число неназванных.

        Ловит мутацию: предел ключей не применяется — строка называет все
        ключи и не несёт «и ещё N».
        """
        cap = config.KNOWLEDGE_CARD_HINT_MAX_KEYS
        per_file = config.KNOWLEDGE_CARD_MAX_PER_FILE
        n_sys = min(per_file, cap)
        n_prj = min(per_file, self.rng.randint(3, 12))
        self.assertGreater(n_sys + n_prj, cap)
        sys_keys, alpha_keys = self.keys(n_sys, "s"), self.keys(n_prj, "a")
        self.commit_main({SYSTEM_REL: self.cards(sys_keys)})
        self.project_cards(ALPHA, self.cards(alpha_keys))
        row = self.add_task("T501", ALPHA)
        mission = build_missions(self.conn, "T501", row)["developer"]
        lines = hint_lines(mission)
        self.assertEqual(len(lines), 1, f"зерно: {self.seed}")
        named = [k for k in sys_keys + alpha_keys if k in lines[0]]
        self.assertLessEqual(len(named), cap, f"зерно: {self.seed}")
        rest = n_sys + n_prj - len(named)
        self.assertIn(f"и ещё {rest}", lines[0], f"зерно: {self.seed}\n"
                                                 f"{lines[0]}")

    def test_ac15_no_topics_line_without_journal(self):
        """Два случая: файлы карточек не заведены (системного нет в `main`,
        у проекта задачи нет файла); файлы заведены с пустым `cards:`.

        Наблюдение: строка-подсказка есть и несёт «тем нет»; записей
        `HINT_REFUSAL_ACTION` в журнале нет.

        Ловит мутацию: «не заведён» трактуется как отказ — в журнал шага
        пишется запись отказа подсказки.
        """
        for label, sys_text, prj_text in (("не заведены", None, None),
                                          ("пустые", "cards:\n", "cards:\n")):
            with self.subTest(label):
                task_id = "T501" if sys_text is None else "T502"
                if sys_text is not None:
                    self.commit_main({SYSTEM_REL: sys_text})
                    self.project_cards(ALPHA, prj_text)
                row = self.add_task(task_id, ALPHA)
                for role, mission in build_missions(self.conn, task_id,
                                                    row).items():
                    lines = hint_lines(mission)
                    self.assertEqual(len(lines), 1, f"{label}; {role}")
                    self.assertIn("тем нет", lines[0], f"{label}; {role}")
                self.assertEqual(hint_records(task_id), [], label)

    def test_ac15_refused_kind_code_without_quote_one_record_per_visit(self):
        """Системный файл в `main` не проходит форму (неизвестное поле с
        уникальным именем и значением); проектный исправен. Миссии пяти
        ролей собираются дважды в одном визите.

        Наблюдение: строка-подсказка несёт код причины из
        `REFUSAL_CODES`, но не имя поля и не значение из файла; проектные
        ключи названы; в журнале ровно одна запись `HINT_REFUSAL_ACTION`
        автора `JOURNAL_ACTOR`; исключения нет.

        Ловит мутацию: запись об отказе пишется `store.journal` на каждой
        сборке миссии, а не `budget.journal_warning_once` — записей больше
        одной.
        """
        leak = "zzleak" + "".join(self.rng.choice("abcdefghijk")
                                  for _ in range(8))
        bad = ("cards:\n  good-key:\n    where: [a/b.py]\n"
               f"    rule: правило\n    why: причина\n"
               f"    {leak}: {leak}value\n")
        alpha_keys = self.keys(2, "a")
        self.commit_main({SYSTEM_REL: bad})
        self.project_cards(ALPHA, self.cards(alpha_keys))
        row = self.add_task("T501", ALPHA)
        for _round in range(2):
            missions = build_missions(self.conn, "T501", row)
            for role, mission in missions.items():
                lines = hint_lines(mission)
                self.assertEqual(len(lines), 1, f"{role}\n{mission}")
                self.assertTrue(any(code in lines[0]
                                    for code in knowledge_cards_module().REFUSAL_CODES),
                                f"зерно: {self.seed}; {role}: {lines[0]}")
                self.assertNotIn(leak, mission, f"зерно: {self.seed}")
                for key in alpha_keys:
                    self.assertIn(key, lines[0], f"зерно: {self.seed}")
        records = hint_records("T501")
        self.assertEqual(len(records), 1, f"зерно: {self.seed}")
        self.assertEqual(records[0]["actor"], knowledge_cards_module().JOURNAL_ACTOR)

    def test_ac15_project_by_task_row_target(self):
        """Карточки систем, проектов ALPHA, BETA и артели
        (`knowledge/artel.yaml`). Три строки задачи: `store.get_task` с
        `target` ALPHA, `store.get_task` с `target` NULL и словарь без
        ключа `target` при `conn=None`.

        Наблюдение: ALPHA — системные и ALPHA ключи, без BETA и артели;
        NULL — системные и ключи артели (`config.DEFAULT_TARGET`); словарь
        без `target` — только системные ключи, без исключения и без записи
        журнала.

        Ловит мутацию: `target` NULL не заменяется `config.DEFAULT_TARGET`
        — задаче с NULL не названы ключи артели.
        """
        sys_keys = self.keys(2, "s")
        groups = {ALPHA: self.keys(2, "a"), BETA: self.keys(2, "b"),
                  "artel": self.keys(2, "r")}
        self.commit_main({SYSTEM_REL: self.cards(sys_keys),
                          ARTEL_REL: self.cards(groups["artel"])})
        self.project_cards(ALPHA, self.cards(groups[ALPHA]))
        self.project_cards(BETA, self.cards(groups[BETA]))
        alpha_row = self.add_task("T501", ALPHA)
        null_row = self.add_task("T502", None)
        bare = {"branch": "task/t503-zadacha", "title": "Задача",
                "reviewed_iter": 0}
        for label, conn, task_id, row, own in (
                ("ALPHA", self.conn, "T501", alpha_row, ALPHA),
                ("NULL", self.conn, "T502", null_row, "artel"),
                ("без target", None, "T503", bare, None)):
            with self.subTest(label):
                missions = build_missions(conn, task_id, row)
                for role, mission in missions.items():
                    lines = hint_lines(mission)
                    self.assertEqual(len(lines), 1, f"{label}; {role}")
                    for key in sys_keys:
                        self.assertIn(key, lines[0], f"зерно: {self.seed}")
                    for name, keys in groups.items():
                        for key in keys:
                            if name == own:
                                self.assertIn(key, lines[0],
                                              f"зерно: {self.seed}; {label}")
                            else:
                                self.assertNotIn(key, mission,
                                                 f"зерно: {self.seed}; {label}")
        for task_id in ("T501", "T502", "T503"):
            self.assertEqual(hint_records(task_id), [])


class BareSandboxHintTest(TmpRootTest):
    """AC-15: песочница без `.git`, `targets.yaml` и файлов карточек."""

    def test_ac15_bare_sandbox_no_journal_no_refusal(self):
        """Корень пульта — временный каталог без `.git`, `targets.yaml`
        удалён, файлов карточек нет; задача в БД, соединение есть.

        Наблюдение: миссия каждой из пяти ролей собирается без исключения,
        несёт одну строку-подсказку «тем нет»; записей журнала задачи
        сборка не добавляет.

        Ловит мутацию: отсутствие `targets.yaml` или `.git` трактуется как
        отказ чтения вида — в журнал шага пишется запись отказа подсказки.
        """
        if config.TARGETS.exists():
            config.TARGETS.unlink()
        conn = store.db()
        store.create_schema(conn)
        store.insert_task(conn, "T601", "Задача", "in_dev",
                          "task/t601-zadacha", config.DEFAULT_TARGET, 25.0)
        before = len(store.task_steps(conn, "T601"))
        row = store.get_task(conn, "T601")
        for role, mission in build_missions(conn, "T601", row).items():
            lines = hint_lines(mission)
            self.assertEqual(len(lines), 1, f"{role}\n{mission}")
            self.assertIn("тем нет", lines[0], role)
        self.assertEqual(len(store.task_steps(conn, "T601")), before)


if __name__ == "__main__":
    unittest.main()
