"""Записка роли `NOTE-<роль>.md` в автокоммите шага и в чекпоинте старта
шага: принимается только записка роли этого шага, чужая и слишком крупная
отбрасываются с записью журнала, неизменённая выкладка не считается
написанной шагом, принятая записка получает запись «записка шага
сохранена» с ролью, размером и sha256.

Группа: долгоживущий

Красен до реализации: белый список корня каталога задачи не знает имён `NOTE-<роль>.md` — автокоммит отбрасывает любую записку как посторонний файл, записей «чужая записка отброшена», «записка слишком велика», «записка из рабочей копии кода отброшена: автор не определён» и «записка шага сохранена» нет, константы `checkpoint.STEP_NOTE_STORE_MAX_BYTES` нет.

Планка провалидирована временным стабом реализации (все методы зелёные, стаб удалён, не закоммичен).

Связка, которую держит файл: «чекпоинт шага (`checkpoint.
commit_step_artifacts` — штатный исход, `checkpoint.
commit_timeout_checkpoint` — таймаут, `checkpoint.harvest_code_copy_docs` —
старт шага) — журнал пульта — ссылка документов задачи в git проекта».
Песочница — `tests.sandbox.RealGitSandbox` с клоном внешнего проекта
(`tests.sandbox.make_project_repo`): ссылка документов задачи
`refs/artifacts/<id>` живёт в git проекта, каталог документов —
`config.PROJECTS/<проект>/<каталог задач>/<id>/`, рабочая копия кода —
`workspace.path`. Рабочей копии кода у задачи нет, поэтому чекпоинт
таймаута переходит прямо к переносу каталога документов.

Выкладка начала шага изображается так же, как её делает пульт: файлы
головы ссылки пишутся в каталог документов, sha головы — в
`tasks.materialized_artifact_sha` (`store.update_task`). Сдвиг головы ссылки
во время шага — коммит поверх головы во вспомогательном репозитории,
отправленный в ссылку, с перефиксацией (`store.record_fixation`). Провал
коммита в ссылку — файл блокировки `<ссылка>.lock` в git проекта: git
отказывает в `update-ref`.

Номера задач, тексты записок, роли и размеры порождаются при каждом
запуске от зерна; зерно печатается и входит в текст провала.
"""
import hashlib
import random
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator import checkpoint, config, store, workspace
from scripts import guard
from tests.sandbox import RealGitSandbox, make_project_repo

TARGET = "zametki"
TASKS = config.TASKS.name
ROLES = ("analyst", "spec_auditor", "test_author", "developer", "reviewer")
OUTCOMES = ("штатный", "таймаут")
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

SAVED = "записка шага сохранена"
FOREIGN = "чужая записка отброшена"
TOO_BIG = "записка слишком велика"
CODE_COPY_NOTE = "записка из рабочей копии кода отброшена: автор не определён"
STRAY_ROOT = "посторонние файлы в каталоге задачи"


class NoteSandbox(RealGitSandbox):
    """Клон внешнего проекта, задачи этого проекта, каталог документов и
    ссылка документов в git проекта."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.project = make_project_repo(TARGET)

    # --------------------------------------------------------------- задача

    def new_task(self, state: str = "in_dev") -> str:
        tid = "01T" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))
        store.insert_task(self.conn, tid, f"Задача {tid}", state,
                          f"task/{tid.lower()}-n", TARGET,
                          config.DEFAULT_BUDGET_USD)
        return tid

    def docs(self, tid: str) -> Path:
        return config.PROJECTS / TARGET / TASKS / tid

    def rel(self, tid: str, name: str) -> str:
        return f"{TASKS}/{tid}/{name}"

    def write(self, tid: str, name: str, data) -> bytes:
        path = self.docs(tid) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = data if isinstance(data, bytes) else data.encode("utf-8")
        path.write_bytes(raw)
        return raw

    def note_text(self, role: str) -> str:
        token = self.rng.randrange(10 ** 9)
        return (f"Выяснено: записка {role} {token} — ёжик ж\n"
                f"Не сработало: ничего {token}\n"
                f"Где остановился: шаг {self.rng.randrange(100)}\n"
                f"Чего не хватило: правила {token}\n")

    def step(self, tid: str, role: str, outcome: str = "штатный") -> None:
        if outcome == "таймаут":
            checkpoint.commit_timeout_checkpoint(self.conn, tid, role)
        else:
            checkpoint.commit_step_artifacts(self.conn, tid, role)

    # --------------------------------------------------------------- ссылка

    def ref(self, tid: str) -> str:
        return f"refs/artifacts/{tid}"

    def in_project(self, *args: str) -> str:
        return self.git("-C", str(self.project), *args)

    def ref_head(self, tid: str) -> str:
        try:
            return self.in_project("rev-parse", "--verify", "-q",
                                   self.ref(tid)).strip()
        except AssertionError:
            return ""

    def ref_files(self, tid: str) -> list:
        if not self.ref_head(tid):
            return []
        return self.in_project("ls-tree", "-r", "--name-only",
                               self.ref(tid)).split()

    def ref_text(self, tid: str, name: str):
        if self.rel(tid, name) not in self.ref_files(tid):
            return None
        return self.in_project("show", f"{self.ref(tid)}:{self.rel(tid, name)}")

    def materialize(self, tid: str) -> str:
        """Выкладка начала шага: голова ссылки — в каталог документов, её
        sha — в `materialized_artifact_sha`."""
        head = self.ref_head(tid)
        shutil.rmtree(self.docs(tid), ignore_errors=True)
        prefix = f"{TASKS}/{tid}/"
        for rel in self.ref_files(tid):
            if rel.startswith(prefix):
                self.write(tid, rel[len(prefix):],
                           self.in_project("show", f"{head}:{rel}"))
        store.update_task(self.conn, tid, materialized_artifact_sha=head or None)
        return head

    def pult_write(self, tid: str, files: dict) -> None:
        """Запись в ссылку мимо шага роли с перефиксацией: коммит поверх
        головы во вспомогательном репозитории, отправка в ссылку проекта."""
        scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
        self.git("init", "-q", str(scratch))
        run = lambda *a: self.git("-C", str(scratch), *a)  # noqa: E731
        run("fetch", "-q", str(self.project), f"+{self.ref(tid)}:refs/heads/w")
        run("checkout", "-q", "w")
        for name, data in files.items():
            path = scratch / TASKS / tid / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        run("add", "-A")
        run("-c", "user.name=p", "-c", "user.email=p@example.invalid",
            "commit", "-q", "-m", "запись пульта")
        run("push", "-q", str(self.project), f"HEAD:{self.ref(tid)}")
        store.record_fixation(self.conn, tid)

    def lock_ref(self, tid: str) -> None:
        git_dir = Path(self.in_project("rev-parse", "--absolute-git-dir").strip())
        lock = git_dir / "refs" / "artifacts" / f"{tid}.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("", encoding="utf-8")

    # --------------------------------------------------------------- журнал

    def top_id(self) -> int:
        return store.journal_maxima(self.conn)[0]

    def records(self, tid: str, action: str, since: int = 0) -> list:
        return [row["detail"] or "" for row in store.task_steps(self.conn, tid)
                if row["action"] == action and row["id"] > since]

    def journal_dump(self, tid: str) -> str:
        return "\n".join(f"{row['id']} {row['action']} | {row['detail'] or ''}"
                         for row in store.task_steps(self.conn, tid))

    def msg(self, tid: str, text: str) -> str:
        return f"зерно: {self.seed}; {text}\nжурнал:\n{self.journal_dump(tid)}"

    def assert_number_in(self, number: int, text: str, what: str, tid: str) -> None:
        self.assertTrue(re.search(rf"(?<!\d){number}(?!\d)", text),
                        self.msg(tid, f"{what}: нет числа {number} в «{text}»"))


# ---------------------------------------------------------------- AC-2, AC-5


class OwnNoteAcceptedTest(NoteSandbox):

    def test_ac5_own_note_lands_in_ref_on_normal_and_timeout_outcomes(self):
        """Шаг каждой из пяти ролей пишет свою записку `NOTE-<роль>.md` и
        заканчивается штатно (`commit_step_artifacts`) либо таймаутом
        (`commit_timeout_checkpoint`).

        Наблюдение: записка с тем же текстом — в ссылке документов задачи;
        записей «посторонние файлы в каталоге задачи» и «чужая записка
        отброшена», называющих её, нет.

        Ловит мутацию: записка принята белым списком только на штатном
        исходе, а перенос на таймауте (`timeout=True`) по-прежнему
        отбрасывает её как посторонний файл; либо роль шага не доходит до
        фильтра и своя записка отбрасывается как чужая.
        """
        for outcome in OUTCOMES:
            for role in ROLES:
                with self.subTest(исход=outcome, роль=role, зерно=self.seed):
                    tid = self.new_task()
                    name = f"NOTE-{role}.md"
                    text = self.note_text(role)
                    self.write(tid, name, text)

                    self.step(tid, role, outcome)

                    self.assertEqual(self.ref_text(tid, name), text,
                                     self.msg(tid, f"{name} нет в ссылке"))
                    for action in (STRAY_ROOT, FOREIGN):
                        self.assertEqual(
                            [d for d in self.records(tid, action) if name in d], [],
                            self.msg(tid, f"запись «{action}» о своей записке"))

    def test_ac2_non_role_note_names_are_dropped_as_stray(self):
        """Шаг developer пишет `PLAN.md` и файл с именем записки не из
        перечня ролей: `NOTE.md`, `NOTE-operator.md` или
        `NOTE-<случайное слово>.md`.

        Наблюдение: этого файла нет в ссылке, есть запись «посторонние
        файлы в каталоге задачи» с его именем; `PLAN.md` в ссылке.

        Ловит мутацию: белый список расширен маской `NOTE-.*` вместо точных
        имён — `NOTE-operator.md` уезжает в ссылку без записи журнала.
        """
        word = "".join(self.rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
        for name in ("NOTE.md", "NOTE-operator.md", f"NOTE-{word}.md"):
            with self.subTest(имя=name, зерно=self.seed):
                tid = self.new_task()
                self.write(tid, "PLAN.md", "план\n")
                self.write(tid, name, self.note_text("operator"))

                self.step(tid, "developer")

                self.assertNotIn(self.rel(tid, name), self.ref_files(tid),
                                 self.msg(tid, f"{name} попал в ссылку"))
                self.assertIn(self.rel(tid, "PLAN.md"), self.ref_files(tid),
                              self.msg(tid, "PLAN.md не попал в ссылку"))
                self.assertTrue([d for d in self.records(tid, STRAY_ROOT) if name in d],
                                self.msg(tid, f"нет записи «{STRAY_ROOT}» о {name}"))


# ---------------------------------------------------------------- AC-6


class ForeignNoteTest(NoteSandbox):

    def test_ac6_developer_step_drops_reviewer_note_and_commits_the_rest(self):
        """Шаг developer пишет `PLAN.md` и `NOTE-reviewer.md` (на штатном
        исходе и на таймауте); отдельно — случайная пара ролей X ≠ Y: шаг
        роли Y пишет `NOTE-<X>.md` рядом с `PLAN.md`.

        Наблюдение: чужой записки нет в ссылке, `PLAN.md` в ссылке, есть
        запись «чужая записка отброшена» с именем файла записки в детали.

        Ловит мутацию: автокоммит принимает любое имя из `STEP_NOTE_ROLES`
        без сверки с ролью шага — `NOTE-reviewer.md` уезжает в ссылку; либо
        чужая записка отбрасывает весь набор файлов шага — `PLAN.md` не
        доезжает.
        """
        writer, author = self.rng.sample(ROLES, 2)
        cases = [("developer", "reviewer", o) for o in OUTCOMES]
        cases.append((writer, author, self.rng.choice(OUTCOMES)))
        for step_role, note_role, outcome in cases:
            with self.subTest(шаг=step_role, записка=note_role, исход=outcome,
                              зерно=self.seed):
                tid = self.new_task()
                name = f"NOTE-{note_role}.md"
                self.write(tid, "PLAN.md", f"план {self.rng.randrange(10 ** 6)}\n")
                self.write(tid, name, self.note_text(note_role))

                self.step(tid, step_role, outcome)

                files = self.ref_files(tid)
                self.assertNotIn(self.rel(tid, name), files,
                                 self.msg(tid, f"{name} шага {step_role} в ссылке"))
                self.assertIn(self.rel(tid, "PLAN.md"), files,
                              self.msg(tid, "остальные файлы шага не закоммичены"))
                self.assertTrue([d for d in self.records(tid, FOREIGN) if name in d],
                                self.msg(tid, f"нет записи «{FOREIGN}» с {name}"))


# ---------------------------------------------------------------- AC-7, AC-8


class UnchangedLayoutTest(NoteSandbox):

    def saved_reviewer_note(self, tid: str) -> str:
        text = self.note_text("reviewer")
        self.write(tid, "NOTE-reviewer.md", text)
        self.step(tid, "reviewer")
        self.assertEqual(self.ref_text(tid, "NOTE-reviewer.md"), text,
                         self.msg(tid, "фикстура: записка reviewer не сохранена"))
        return text

    def test_ac7_unchanged_foreign_note_layout_is_not_dropped_even_after_head_moved(self):
        """Шаг reviewer сохранил свою записку; шаг developer начинается
        выкладкой ссылки (записка reviewer — в каталоге документов, sha
        головы — в `materialized_artifact_sha`), пишет `PLAN.md` и чужую
        записку не трогает. Во втором случае во время шага голова ссылки
        уходит вперёд: запись пульта с перефиксацией меняет именно
        `NOTE-reviewer.md`.

        Наблюдение: записи «чужая записка отброшена» за шаг developer нет;
        в ссылке `NOTE-reviewer.md` — версия головы (без сдвига — прежняя,
        со сдвигом — новая), `PLAN.md` в ссылке.

        Ловит мутацию: «написана шагом» сверяется с головой ссылки, а не с
        выкладкой начала шага, — после сдвига головы неизменённая выкладка
        признаётся написанной и отбрасывается как чужая с записью журнала;
        либо фильтр чужой записки стоит после конфликт-гварда и подменяет
        его — версия головы теряется.
        """
        for moved in (False, True):
            with self.subTest(голова_сдвинута=moved, зерно=self.seed):
                tid = self.new_task()
                original = self.saved_reviewer_note(tid)
                self.materialize(tid)
                expected = original
                if moved:
                    expected = self.note_text("reviewer")
                    self.pult_write(tid, {"NOTE-reviewer.md": expected})
                since = self.top_id()
                self.write(tid, "PLAN.md", f"план {self.rng.randrange(10 ** 6)}\n")

                self.step(tid, "developer")

                self.assertEqual(self.records(tid, FOREIGN, since), [],
                                 self.msg(tid, "неизменённая выкладка отброшена как чужая"))
                self.assertEqual(self.ref_text(tid, "NOTE-reviewer.md"), expected,
                                 self.msg(tid, "в ссылке не версия головы"))
                self.assertIn(self.rel(tid, "PLAN.md"), self.ref_files(tid),
                              self.msg(tid, "PLAN.md не закоммичен"))

    def test_ac8_empty_layout_fixation_compares_note_with_ref_head(self):
        """Выкладка начала шага пуста (`materialized_artifact_sha` не
        записан), а в каталоге документов шага developer лежат записки,
        уже сохранённые в ссылке: `NOTE-reviewer.md` — байт в байт как в
        голове ссылки либо изменённая; своя `NOTE-developer.md` — байт в
        байт как в голове.

        Наблюдение: равная голове чужая записка не даёт записи «чужая
        записка отброшена»; изменённая — даёт запись с её именем и в ссылку
        не попадает (там прежний текст); равная голове своя записка не даёт
        новой записи «записка шага сохранена».

        Ловит мутацию: при пустой фиксации выкладки любой файл каталога
        документов считается написанным шагом — равная голове чужая записка
        журналируется как чужая, а равная голове своя получает новую запись
        о сохранении.
        """
        for changed in (False, True):
            with self.subTest(чужая_изменена=changed, зерно=self.seed):
                tid = self.new_task()
                reviewer_text = self.saved_reviewer_note(tid)
                own_text = self.note_text("developer")
                self.write(tid, "NOTE-developer.md", own_text)
                self.step(tid, "developer")
                self.assertEqual(len(self.records(tid, SAVED)), 2,
                                 self.msg(tid, "фикстура: две записки не сохранены"))
                store.update_task(self.conn, tid, materialized_artifact_sha=None)
                self.write(tid, "NOTE-reviewer.md",
                           reviewer_text + ("правка\n" if changed else ""))
                self.write(tid, "NOTE-developer.md", own_text)
                self.write(tid, "PLAN.md", f"план {self.rng.randrange(10 ** 6)}\n")
                since = self.top_id()

                self.step(tid, "developer")

                foreign = [d for d in self.records(tid, FOREIGN, since)
                           if "NOTE-reviewer.md" in d]
                if changed:
                    self.assertTrue(foreign, self.msg(tid, "изменённая чужая записка "
                                                           "не отброшена"))
                else:
                    self.assertEqual(foreign, [], self.msg(tid, "равная голове чужая "
                                                                "записка отброшена"))
                self.assertEqual(self.ref_text(tid, "NOTE-reviewer.md"), reviewer_text,
                                 self.msg(tid, "чужая записка в ссылке изменилась"))
                self.assertEqual(self.records(tid, SAVED, since), [],
                                 self.msg(tid, "равная голове своя записка получила "
                                               "новую запись о сохранении"))


# ---------------------------------------------------------------- AC-9


class NoteStoreCeilingTest(NoteSandbox):

    def test_ac9_note_above_store_ceiling_is_dropped_with_journal_record(self):
        """Шаг случайной роли пишет свою записку размером
        `STEP_NOTE_STORE_MAX_BYTES` + k байт (k > 0, текст с
        двухбайтовыми символами) и, отдельно, ровно
        `STEP_NOTE_STORE_MAX_BYTES` байт.

        Наблюдение: крупная записка в ссылку не попадает, есть запись
        «записка слишком велика» с ролью и размером в байтах в детали;
        записка ровно на потолке попадает в ссылку без такой записи.

        Ловит мутацию: размер считается в символах, а не в байтах (записка
        из двухбайтовых символов проходит), или сравнение `>=` вместо `>`
        — записка ровно на потолке отбрасывается; либо крупная записка
        отбрасывается молча, без записи журнала.
        """
        ceiling = checkpoint.STEP_NOTE_STORE_MAX_BYTES
        role = self.rng.choice(ROLES)
        name = f"NOTE-{role}.md"
        for extra in (self.rng.randrange(1, 4000), 0):
            with self.subTest(сверх_потолка=extra, роль=role, зерно=self.seed):
                tid = self.new_task()
                size = ceiling + extra
                head = "Выяснено: " + "ж" * ((size // 2) - 20)
                body = (head + "a" * size).encode("utf-8")[:size]
                self.assertEqual(len(body), size)
                body.decode("utf-8")
                self.write(tid, name, body)

                self.step(tid, role)

                big = self.records(tid, TOO_BIG)
                if extra:
                    self.assertNotIn(self.rel(tid, name), self.ref_files(tid),
                                     self.msg(tid, "записка сверх потолка в ссылке"))
                    self.assertTrue(big, self.msg(tid, f"нет записи «{TOO_BIG}»"))
                    self.assertIn(role, big[-1], self.msg(tid, "в детали нет роли"))
                    self.assert_number_in(size, big[-1], "размер записки", tid)
                else:
                    self.assertIn(self.rel(tid, name), self.ref_files(tid),
                                  self.msg(tid, "записка ровно на потолке отброшена"))
                    self.assertEqual(big, [], self.msg(tid, "запись о потолке на потолке"))


# ---------------------------------------------------------------- AC-10


class CodeCopyNoteAtStartTest(NoteSandbox):

    def code_copy_write(self, tid: str, name: str, text: str) -> None:
        path = workspace.path(tid, TARGET) / TASKS / tid / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_ac10_role_note_in_code_copy_is_dropped_at_step_start(self):
        """В рабочей копии кода задачи на старте шага лежит каталог задачи
        с `PLAN.md` и записка `NOTE-<роль>.md` — для каждой из пяти ролей;
        чекпоинт старта шага `harvest_code_copy_docs`.

        Наблюдение: записки нет ни в ссылке документов, ни в наборе,
        который вернула функция; есть запись «записка из рабочей копии
        кода отброшена: автор не определён» с именем файла в детали.

        Ловит мутацию: на старте шага (роль неизвестна, `None`) фильтр
        записки пропускает имена из `STEP_NOTE_ROLES` как законные — записка
        уезжает в ссылку; либо записка отброшена из ссылки, но осталась в
        возвращённом наборе, и `role_cwd` положит её в каталог документов.
        """
        for role in ROLES:
            with self.subTest(роль=role, зерно=self.seed):
                tid = self.new_task()
                name = f"NOTE-{role}.md"
                self.code_copy_write(tid, "PLAN.md", "план из рабочей копии\n")
                self.code_copy_write(tid, name, self.note_text(role))

                harvested = checkpoint.harvest_code_copy_docs(self.conn, tid, TARGET)

                self.assertEqual([k for k in (harvested or {}) if k.endswith(name)], [],
                                 self.msg(tid, f"{name} в возвращённом наборе"))
                self.assertNotIn(self.rel(tid, name), self.ref_files(tid),
                                 self.msg(tid, f"{name} попал в ссылку"))
                self.assertTrue([d for d in self.records(tid, CODE_COPY_NOTE) if name in d],
                                self.msg(tid, f"нет записи «{CODE_COPY_NOTE}» с {name}"))

    def test_ac10_non_role_note_in_code_copy_is_stray_file(self):
        """В рабочей копии кода на старте шага лежат `NOTE.md` или
        `NOTE-operator.md` рядом с `PLAN.md`.

        Наблюдение: файла нет ни в ссылке, ни в возвращённом наборе; есть
        запись «посторонние файлы в каталоге задачи» с его именем.

        Ловит мутацию: фильтр старта шага отбрасывает любую `NOTE*.md` своей
        записью и пропускает её мимо проверки посторонних файлов — записи
        «посторонние файлы в каталоге задачи» нет; либо маска `NOTE-.*`
        пропускает `NOTE-operator.md` в ссылку.
        """
        for name in ("NOTE.md", "NOTE-operator.md"):
            with self.subTest(имя=name, зерно=self.seed):
                tid = self.new_task()
                self.code_copy_write(tid, "PLAN.md", "план из рабочей копии\n")
                self.code_copy_write(tid, name, self.note_text("operator"))

                harvested = checkpoint.harvest_code_copy_docs(self.conn, tid, TARGET)

                self.assertEqual([k for k in (harvested or {}) if k.endswith("/" + name)],
                                 [], self.msg(tid, f"{name} в возвращённом наборе"))
                self.assertNotIn(self.rel(tid, name), self.ref_files(tid),
                                 self.msg(tid, f"{name} попал в ссылку"))
                self.assertTrue([d for d in self.records(tid, STRAY_ROOT) if name in d],
                                self.msg(tid, f"нет записи «{STRAY_ROOT}» с {name}"))


# ---------------------------------------------------------------- AC-11


class SavedNoteRecordTest(NoteSandbox):

    def test_ac11_accepted_note_gets_saved_record_with_role_size_and_sha256(self):
        """Шаг каждой из пяти ролей (штатный исход и таймаут) пишет свою
        записку с многобайтовыми символами.

        Наблюдение: после шага ровно одна запись «записка шага сохранена»;
        её деталь несёт роль, размер записки в байтах и sha256 её байтов.

        Ловит мутацию: размер в детали — число символов, а не байтов, или
        sha256 считается от текста другой формы (без перевода строки,
        от имени файла); либо запись на исходе «таймаут» не заводится.
        """
        for outcome in OUTCOMES:
            for role in ROLES:
                with self.subTest(исход=outcome, роль=role, зерно=self.seed):
                    tid = self.new_task()
                    raw = self.write(tid, f"NOTE-{role}.md", self.note_text(role))

                    self.step(tid, role, outcome)

                    saved = self.records(tid, SAVED)
                    self.assertEqual(len(saved), 1, self.msg(tid, f"записи «{SAVED}»"))
                    self.assertIn(role, saved[0], self.msg(tid, "в детали нет роли"))
                    self.assert_number_in(len(raw), saved[0], "размер в байтах", tid)
                    self.assertIn(hashlib.sha256(raw).hexdigest(), saved[0],
                                  self.msg(tid, "в детали нет sha256 байтов записки"))

    def test_ac11_no_saved_record_on_failed_commit_unchanged_layout_or_foreign_note(self):
        """Три сценария без сохранения: (а) коммит в ссылку не удался (git
        отказывает в `update-ref` из-за файла блокировки ссылки); (б) шаг
        developer после выкладки ссылки, где его записка уже сохранена,
        пишет только `PLAN.md`; (в) шаг developer пишет `NOTE-reviewer.md`.

        Наблюдение: ни в одном сценарии шаг не добавляет записи «записка
        шага сохранена»; в (а) записки нет в ссылке.

        Ловит мутацию: запись о сохранении заводится до коммита или без
        проверки его результата (а), для каждой принятой в набор записки
        независимо от того, изменилась ли она (б), или для любой записки,
        принятой в набор, включая чужую (в).
        """
        with self.subTest(сценарий="коммит не удался", зерно=self.seed):
            tid = self.new_task()
            name = "NOTE-developer.md"
            self.write(tid, name, self.note_text("developer"))
            self.lock_ref(tid)
            self.step(tid, "developer")
            self.assertEqual(self.records(tid, SAVED), [],
                             self.msg(tid, "запись о сохранении при провале коммита"))
            self.assertNotIn(self.rel(tid, name), self.ref_files(tid),
                             self.msg(tid, "фикстура: коммит не провалился"))

        with self.subTest(сценарий="неизменённая выкладка", зерно=self.seed):
            tid = self.new_task()
            self.write(tid, "NOTE-developer.md", self.note_text("developer"))
            self.step(tid, "developer")
            self.assertEqual(len(self.records(tid, SAVED)), 1,
                             self.msg(tid, "фикстура: записка не сохранена"))
            self.materialize(tid)
            since = self.top_id()
            self.write(tid, "PLAN.md", f"план {self.rng.randrange(10 ** 6)}\n")
            self.step(tid, "developer")
            self.assertIn(self.rel(tid, "PLAN.md"), self.ref_files(tid),
                          self.msg(tid, "фикстура: PLAN.md не закоммичен"))
            self.assertEqual(self.records(tid, SAVED, since), [],
                             self.msg(tid, "запись о сохранении неизменённой выкладки"))

        with self.subTest(сценарий="чужая записка", зерно=self.seed):
            tid = self.new_task()
            self.write(tid, "PLAN.md", "план\n")
            self.write(tid, "NOTE-reviewer.md", self.note_text("reviewer"))
            self.step(tid, "developer")
            self.assertEqual(self.records(tid, SAVED), [],
                             self.msg(tid, "запись о сохранении чужой записки"))


if __name__ == "__main__":
    unittest.main()
