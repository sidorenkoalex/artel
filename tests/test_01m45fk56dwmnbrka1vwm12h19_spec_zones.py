"""Защищённые зоны ТЗ (`new`) и SPEC (гейт SPEC) — по перечню защищённых
путей проекта задачи.

Группа: долгоживущий
Красен до реализации: `new` сверяет «Зоны:» ТЗ с `config.PROTECTED_PATHS` для любого проекта — зона под `no_paths` внешнего проекта проходит, а зона под записью пульта отказывает; гейт SPEC защищённые зоны не сверяет вовсе — зона под `no_paths` внешнего проекта отказа «защищённый путь только приложением» не даёт. Половина артели (`new` по прежнему перечню) держит сегодняшнее поведение и зелёная с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`): корень — клон
артели с bare `origin`; внешний проект — клон с bare `origin`
(`tests.sandbox.make_project_repo`), запись `targets.yaml` песочницы с полем
`no_paths` из случайных каталогов `zn…/`. ТЗ — файл во временном каталоге
песочницы со строкой «Зоны: …» и командой `catalog.cmd_new`. Гейт SPEC —
задача внешнего проекта, заведённая `catalog.cmd_new`, SPEC.md с полем
`zones` в её ссылке документов автокоммитом шага
(`checkpoint.commit_step_artifacts`), задача на `spec_gate`, команда
`fsm.cmd_approve`. Наблюдается текст отказа (вывод и журнал задачи) и
состояние задачи.

Провалидировано временным стабом реализации (удалён, не закоммичен):
`new` и гейт SPEC сверяют зоны с перечнем проекта задачи — все методы
зелёные.

Зерно печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import catalog, checkpoint, config, fsm, store
from scripts import guard
from tests.sandbox import (RealGitSandbox, capture, capture_new_task_id,
                           make_project_repo)

ARTEL = config.DEFAULT_TARGET
EXT = "vnesh"
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

TARGET_ENTRY = """  {name}:
    forge: github
    url: {url}
    base: {base}
    token_slot: {name}-token
    no_paths: [{no_paths}]
    project_skills: []
    merge_gate: operator
"""

# Профиль тестов артели — как в `targets.yaml` пульта: без него пульт
# проекту артели отказывает (fail-closed). Внешнему проекту не пишется.
ARTEL_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

TZ_TEXT = """# ТЗ: фикстура зон {word}

Требуется: правка по зонам.

Зоны: {zones}.
"""

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
zones: {zones}
---

# SPEC: фикстура зон

## Контекст

## Требования

## Критерии приёмки

## Не входит
"""


class ZonesSandbox(RealGitSandbox):
    """Клон артели, клон внешнего проекта и `targets.yaml` с их записями."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = store.db()
        self.add_synced_origin()
        make_project_repo(EXT)
        self.no_paths = []
        while len(self.no_paths) < self.rng.randint(2, 3):
            name = f"zn{self.word()}/"
            if name not in self.no_paths:
                self.no_paths.append(name)
        config.TARGETS.write_text(
            "targets:\n"
            + TARGET_ENTRY.format(name=ARTEL, url="http://localhost/artel",
                                  base=config.MAIN_BRANCH,
                                  no_paths=", ".join(config.PROTECTED_PATHS))
            + ARTEL_PROFILE
            + TARGET_ENTRY.format(name=EXT, url=f"file:///nonexistent/{EXT}",
                                  base=config.MAIN_BRANCH,
                                  no_paths=", ".join(self.no_paths)),
            encoding="utf-8")
        capture(catalog.cmd_init)

    def word(self, size: int = 6) -> str:
        return "".join(self.rng.choice(ALPHABET) for _ in range(size))

    def explain(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def ext_zone(self) -> str:
        return f"{self.rng.choice(self.no_paths)}{self.word()}/"

    def artel_only_zone(self) -> str:
        """Зона под случайной записью-каталогом `config.PROTECTED_PATHS`."""
        entry = self.rng.choice([e for e in config.PROTECTED_PATHS
                                 if e.endswith("/") and not e.startswith("**/")])
        return f"{entry}{self.word()}/"

    @staticmethod
    def run_cmd(fn, *args, **kwargs) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def new_with_tz(self, target: str, zones: list[str]) -> str:
        """Вывод `new` с ТЗ, чья строка «Зоны:» несёт `zones` и `src/`."""
        tz = self.root / ".artel" / f"tz-{self.word()}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text(TZ_TEXT.format(word=self.word(),
                                     zones=", ".join(["src/"] + zones)),
                      encoding="utf-8")
        return self.run_cmd(catalog.cmd_new, f"Фикстура {self.word()}", str(tz),
                            target=target)

    def approve_spec(self, zones: list[str]) -> tuple[str, str, str]:
        """(вывод `approve` на `spec_gate`, журнал, состояние после) задачи
        внешнего проекта с `zones` в SPEC.md."""
        _out, task_id = capture_new_task_id(
            lambda: catalog.cmd_new(f"Фикстура {self.word()}", target=EXT))
        docs = config.PROJECTS / EXT / "tasks" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "SPEC.md").write_text(
            SPEC_TEXT.format(task=task_id, zones=", ".join(["src/"] + zones)),
            encoding="utf-8")
        capture(checkpoint.commit_step_artifacts, self.conn, task_id, "analyst")
        store.update_task(self.conn, task_id, state="spec_gate")
        out = self.run_cmd(fsm.cmd_approve, task_id)
        journal = "\n".join(f"{r['action']} | {r['detail'] or ''}"
                            for r in store.task_steps(self.conn, task_id))
        return out, journal, store.get_task(self.conn, task_id)["state"]


class TzZonesTest(ZonesSandbox):

    def test_ac10_tz_zones_checked_by_project_perimeter(self):
        """«Зоны:» ТЗ сверяются с перечнем защищённых путей проекта, для которого заводится задача.

        Сценарий: `new` с ТЗ для внешнего проекта — зона под записью
        `no_paths` даёт отказ «защищённый путь только приложением»,
        называющий зону; зона под записью-каталогом `config.PROTECTED_PATHS`
        (её нет в `no_paths`) такого отказа не даёт. `new` с ТЗ для артели —
        зона под записью пульта даёт тот же отказ, зона под `no_paths`
        внешнего проекта — не даёт.

        Ловит мутацию: `new` сверяет зоны ТЗ по `config.PROTECTED_PATHS` для
        любого проекта — зона `no_paths` внешнего проекта проходит, зона
        пульта у него отказывает; перечень проекта не передан из `new` в
        `guard.protected_zones`; у артели перечень сменён на поле `no_paths`
        её записи или пуст.
        """
        cases = [(EXT, self.ext_zone(), True), (EXT, self.artel_only_zone(), False),
                 (ARTEL, self.artel_only_zone(), True), (ARTEL, self.ext_zone(), False)]
        self.rng.shuffle(cases)
        for target, zone, refused in cases:
            with self.subTest(project=target, zone=zone):
                out = self.new_with_tz(target, [zone])
                note = self.explain(f"{target}, зона {zone}: {out}")
                if refused:
                    self.assertIn(guard.PROTECTED_ZONE_REFUSAL, out, note)
                    lines = [line for line in out.splitlines()
                             if guard.PROTECTED_ZONE_REFUSAL in line]
                    self.assertTrue([line for line in lines if zone in line], note)
                else:
                    self.assertNotIn(guard.PROTECTED_ZONE_REFUSAL, out, note)


class SpecGateZonesTest(ZonesSandbox):

    def test_ac10_spec_gate_zones_checked_by_external_no_paths(self):
        """Гейт SPEC задачи внешнего проекта отказывает зоне под её `no_paths` и не отказывает зоне, защищённой только у артели.

        Сценарий: задача внешнего проекта на `spec_gate`, SPEC.md с
        `zones` — зона под записью `no_paths`: после `approve` в выводе или
        журнале есть отказ «защищённый путь только приложением», называющий
        зону, задача осталась на `spec_gate`. Вторая задача — зона под
        записью-каталогом `config.PROTECTED_PATHS` (её нет в `no_paths`):
        такого отказа нет ни в выводе, ни в журнале.

        Ловит мутацию: гейт SPEC не сверяет зоны с перечнем проекта — зона
        `no_paths` проходит `approve`; сверка есть, но по
        `config.PROTECTED_PATHS` — зона пульта у внешнего проекта отказывает,
        а зона его `no_paths` проходит.
        """
        zone = self.ext_zone()
        out, journal, state = self.approve_spec([zone])
        text = f"{out}\n{journal}"
        note = self.explain(f"зона no_paths {zone}: {text}")
        lines = [line for line in text.splitlines()
                 if guard.PROTECTED_ZONE_REFUSAL in line]
        self.assertTrue([line for line in lines if zone in line], note)
        self.assertEqual(state, "spec_gate", note)

        zone = self.artel_only_zone()
        out, journal, _state = self.approve_spec([zone])
        text = f"{out}\n{journal}"
        self.assertNotIn(guard.PROTECTED_ZONE_REFUSAL, text, self.explain(
            f"зона пульта {zone}: {text}"))


if __name__ == "__main__":
    unittest.main()
