"""AC-7 (tasks/01M1SG9T962WJJ31S282GWM0EN/SPEC.md): в песочнице тестов с
локальным `origin/main`, ушедшим вперёд локального `main` на файл вне
зон, и веткой задачи, влившей `origin/main`: гейт зон не отказывает по
этому файлу; гейт ёмкости не учитывает его байты в diff снимка; полный
diff ревью-пакета не содержит этот файл.

`MergeBaseFixture` (`_sandbox.py`, `CREATE_ORIGIN_REF = True`) строит
именно этот сценарий: локальный main стоит на commit0, `refs/remotes/
origin/main` указывает на коммит с файлом `docs/roadmap.md` (300 000
байт — заведомо крупнее `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`, чтобы
включение/исключение этого файла реально меняло исход гейта ёмкости, не
только текст журнала), а ветка задачи создана от commit0 и мержит этот
коммит origin (та же git-механика, что делает подтяжка перед
`verifying`).

Красен до реализации: сегодняшние `_zones_gate_refuses`/
`_capacity_gate_refuses`/`review.review_package` сравнивают ветку с
ЛОКАЛЬНЫМ `config.MAIN_BRANCH` (commit0) независимо от того, заведён ли
`refs/remotes/origin/main`, — файл `docs/roadmap.md`, попавший в ветку
задачи через мерж origin, окажется в этом диффе как «правка задачи»:
гейт зон отказывает (файл вне заявленной зоны), гейт ёмкости отказывает
(300 000 байт выше потолка), полный diff содержит этот файл. Все три
проверки ниже упадут на сегодняшнем коде.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import fsm_advance, review  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MergeBaseFixture  # noqa: E402


class ZonesGateIgnoresOriginOnlyFileTest(MergeBaseFixture):

    def test_ac7_zones_gate_does_not_refuse_on_the_origin_only_file(self):
        """Ловит мутацию: база сравнения гейта зон не переключена на
        merge-base с `origin/main` (осталась `config.MAIN_BRANCH`) —
        `docs/roadmap.md`, пришедший через мерж origin, попал бы в дифф
        задачи как «файл вне заявленных zones» и гейт отказал бы."""
        refused = fsm_advance._zones_gate_refuses(
            self.conn, self.TASK_ID, self.t, self.BRANCH, "PLAN\n")

        self.assertFalse(
            refused, "правка origin, слитая в ветку задачи, не имеет "
            "права выглядеть как «вне зон» задачи")


class CapacityGateExcludesOriginOnlyBytesTest(MergeBaseFixture):

    def test_ac7_capacity_gate_does_not_count_the_origin_only_file_bytes(self):
        """Ловит мутацию: та же база не переключена на merge-base с
        `origin/main` — 300 000 байт `docs/roadmap.md` вошли бы в diff
        снимка и превысили `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES`,
        хотя задача этот файл не трогала вовсе."""
        refused = fsm_advance._capacity_gate_refuses(
            self.conn, self.TASK_ID, self.t, "in_dev")

        self.assertFalse(
            refused, "байты файла, принесённого мержем origin, не имеют "
            "права засчитываться в снимок задачи")


class ReviewPackageFullDiffExcludesOriginOnlyFileTest(MergeBaseFixture):

    def test_ac7_full_review_diff_does_not_contain_the_origin_only_file(self):
        """Ловит мутацию: `review.review_package` при `iteration == 1`
        по-прежнему берёт diff от `config.MAIN_BRANCH` — путь `docs/
        roadmap.md` оказался бы и в стат-списке, и в самом diff пакета,
        хотя ревьюверу задачи он не интересен вовсе (не её правка)."""
        package = review.review_package(
            self.conn, self.TASK_ID, "Тест merge-base", self.BRANCH)

        self.assertNotIn(self.OUT_OF_ZONE_REL, package["text"])
        self.assertIn(self.IN_ZONE_REL.rsplit("/", 1)[-1], package["text"],
                      "своя правка задачи обязана остаться в diff пакета")


if __name__ == "__main__":
    unittest.main()
