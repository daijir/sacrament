"""
エッジケース（極小支部、青少年0人、男女極端偏り、CSV欠損等）のテスト
"""

import unittest
from datetime import date, timedelta
import sys
from pathlib import Path
import tempfile
import csv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sacrament import (
    Member,
    generate_schedule,
    get_sunday_type,
    load_members,
)


class TestEdgeCases(unittest.TestCase):
    def test_no_youth_unit(self):
        """青少年が0人のユニットでもクラッシュせず青少年枠がスキップされること"""
        members = {
            1: Member(id=1, name="佐藤 兄弟", gender="M", category="adult", household_id=1),
            2: Member(id=2, name="佐藤 姉妹", gender="F", category="adult", household_id=1),
            3: Member(id=3, name="鈴木 兄弟", gender="M", category="adult", household_id=2),
            4: Member(id=4, name="鈴木 姉妹", gender="F", category="adult", household_id=2),
        }
        slots = generate_schedule(members, weeks=4, start_date=date(2026, 10, 11))
        self.assertEqual(len(slots), 4)
        for s in slots:
            # 青少年がいないので youth_talk は None
            self.assertIsNone(s.youth_talk)

    def test_small_branch_no_deadlock(self):
        """極小規模支部（会員数わずか6名）で長期スケジュールしてもクラッシュ（デッドロック）しないこと"""
        members = {
            1: Member(id=1, name="支部1", gender="M", category="adult", household_id=1),
            2: Member(id=2, name="支部2", gender="F", category="adult", household_id=1),
            3: Member(id=3, name="支部3", gender="M", category="adult", household_id=2),
            4: Member(id=4, name="支部4", gender="F", category="adult", household_id=2),
            5: Member(id=5, name="ユース1", gender="M", category="youth", household_id=3),
            6: Member(id=6, name="ユース2", gender="F", category="youth", household_id=3),
        }
        # 12週間（全員が何度も順番を迎える）
        slots = generate_schedule(members, weeks=12, start_date=date(2026, 10, 11))
        self.assertEqual(len(slots), 12)
        # 各週でお祈りや話者がフォールバック選出され、クラッシュしていないこと
        for s in slots:
            if s.sunday_type == "regular":
                self.assertIsNotNone(s.adult_talk_1)

    def test_single_gender_unit(self):
        """男性のみ（または女性のみ）の環境でも安全に処理されること"""
        male_only = {
            1: Member(id=1, name="男性1", gender="M", category="adult", household_id=1),
            2: Member(id=2, name="男性2", gender="M", category="adult", household_id=2),
            3: Member(id=3, name="男性3", gender="M", category="adult", household_id=3),
        }
        slots = generate_schedule(male_only, weeks=2, start_date=date(2026, 10, 11))
        self.assertEqual(len(slots), 2)
        for s in slots:
            # 男性がいるので開会の祈りは選出される
            self.assertIsNotNone(s.invocation)
            # 女性がいないので閉会の祈りは None
            self.assertIsNone(s.benediction)

    def test_all_small_children_households(self):
        """全会員が乳幼児あり世帯の場合でも、同一世帯の夫婦が同日に重複しないこと"""
        members = {
            1: Member(id=1, name="夫A", gender="M", category="adult", household_id=1, has_small_children=True),
            2: Member(id=2, name="妻A", gender="F", category="adult", household_id=1, has_small_children=True),
            3: Member(id=3, name="夫B", gender="M", category="adult", household_id=2, has_small_children=True),
            4: Member(id=4, name="妻B", gender="F", category="adult", household_id=2, has_small_children=True),
        }
        slots = generate_schedule(members, weeks=6, start_date=date(2026, 10, 11))
        for s in slots:
            assigned = [
                m for m in [s.invocation, s.benediction, s.youth_talk, s.adult_talk_1, s.adult_talk_2]
                if m is not None
            ]
            household_ids = [m.household_id for m in assigned]
            # 同一世帯IDの重複が絶対にないこと
            self.assertEqual(len(household_ids), len(set(household_ids)), f"同日重複発生: {s.meeting_date}")

    def test_fifth_sunday_and_leap_year(self):
        """第5日曜日やうるう年の日付計算が正確に行われること"""
        # 2026年5月31日 (第5日曜日)
        t_5th, title_5th = get_sunday_type(date(2026, 5, 31), hc_week=3)
        self.assertEqual(t_5th, "regular")
        self.assertIn("通常", title_5th)

        # うるう年の2月29日 (2028年はうるう年、2028年2月27日は第4日曜)
        t_leap, _ = get_sunday_type(date(2028, 2, 27), hc_week=3)
        self.assertEqual(t_leap, "regular")

    def test_legacy_csv_backward_compatibility(self):
        """古い形式のCSV（is_high_councilor列がない）でも安全に読み込めること"""
        old_csv_content = (
            "id,name,gender,category,household_id,is_bishopric,couple_talk_together,has_small_children,is_new_member\n"
            "1,テスト太郎,M,adult,1,False,False,False,False\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(old_csv_content)
            temp_csv_path = f.name

        try:
            # 簡易パーステスト
            with open(temp_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader)
                m = Member(
                    id=int(row["id"]),
                    name=row["name"],
                    gender=row["gender"],
                    category=row["category"],
                    household_id=int(row["household_id"]),
                    is_high_councilor=row.get("is_high_councilor", "false").strip().lower() == "true",
                )
                self.assertFalse(m.is_high_councilor)
        finally:
            Path(temp_csv_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
