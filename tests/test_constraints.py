"""
ハード制約（教会のルール・除外設定・インターバル）の単体テスト
"""

import unittest
from datetime import date, timedelta
import sys
from pathlib import Path

# 親ディレクトリのモジュールをインポート可能にする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sacrament import (
    Member,
    calculate_score,
    get_sunday_type,
    format_elapsed,
)


class TestConstraints(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 10, 11)
        self.bishop = Member(
            id=1, name="佐藤 ビショップ", gender="M", category="adult",
            household_id=1, is_bishopric=True
        )
        self.high_councilor = Member(
            id=2, name="鈴木 高等評議員", gender="M", category="adult",
            household_id=2, is_high_councilor=True
        )
        self.regular_male = Member(
            id=3, name="田中 兄弟", gender="M", category="adult",
            household_id=3
        )
        self.regular_female = Member(
            id=4, name="田中 姉妹", gender="F", category="adult",
            household_id=3
        )
        self.baby_husband = Member(
            id=5, name="渡辺 夫", gender="M", category="adult",
            household_id=4, has_small_children=True
        )
        self.baby_wife = Member(
            id=6, name="渡辺 妻", gender="F", category="adult",
            household_id=4, has_small_children=True
        )
        self.youth = Member(
            id=7, name="伊藤 ユース", gender="M", category="youth",
            household_id=5
        )

    def test_bishopric_exclusion(self):
        """ビショップリックはお話・お祈りともに通常枠から除外されること"""
        score_talk, reason_talk = calculate_score(self.bishop, self.today, "talk", [])
        self.assertEqual(score_talk, -99999.0)
        self.assertIn("ビショップリック", reason_talk)

        score_pray, reason_pray = calculate_score(self.bishop, self.today, "prayer", [])
        self.assertEqual(score_pray, -99999.0)
        self.assertIn("ビショップリック", reason_pray)

    def test_high_councilor_exclusion_for_talk(self):
        """高等評議員は自ワードのお話枠から除外されるがお祈りは可能であること"""
        score_talk, reason_talk = calculate_score(self.high_councilor, self.today, "talk", [])
        self.assertEqual(score_talk, -99999.0)
        self.assertIn("高等評議員", reason_talk)

        score_pray, reason_pray = calculate_score(self.high_councilor, self.today, "prayer", [])
        self.assertGreater(score_pray, 0)

    def test_same_day_duplicate_assignment(self):
        """同日に既に役割が決まっている会員は除外されること"""
        assigned = [self.regular_male]
        score, reason = calculate_score(self.regular_male, self.today, "prayer", assigned)
        self.assertEqual(score, -99999.0)
        self.assertIn("同日に他の役割", reason)

    def test_small_children_couple_conflict(self):
        """乳幼児がいる夫婦は同日に重複して割り当てられないこと"""
        assigned = [self.baby_husband]
        score, reason = calculate_score(self.baby_wife, self.today, "talk", assigned)
        self.assertEqual(score, -99999.0)
        self.assertIn("乳幼児", reason)

        # 乳幼児がいない夫婦は同日重複可能（夫婦登壇など）
        assigned_reg = [self.regular_male]
        score_reg, _ = calculate_score(self.regular_female, self.today, "talk", assigned_reg)
        self.assertGreater(score_reg, 0)

    def test_minimum_interval(self):
        """お話は最低60日、お祈りは最低28日空けること"""
        # お話: 50日前は不可、70日前は可能
        self.regular_male.last_talk_date = self.today - timedelta(days=50)
        s_invalid, _ = calculate_score(self.regular_male, self.today, "talk", [])
        self.assertEqual(s_invalid, -99999.0)

        self.regular_male.last_talk_date = self.today - timedelta(days=70)
        s_valid, _ = calculate_score(self.regular_male, self.today, "talk", [])
        self.assertGreater(s_valid, 0)

        # お祈り: 20日前は不可、35日前は可能
        self.regular_female.last_prayer_date = self.today - timedelta(days=20)
        sp_invalid, _ = calculate_score(self.regular_female, self.today, "prayer", [])
        self.assertEqual(sp_invalid, -99999.0)

        self.regular_female.last_prayer_date = self.today - timedelta(days=35)
        sp_valid, _ = calculate_score(self.regular_female, self.today, "prayer", [])
        self.assertGreater(sp_valid, 0)

    def test_sunday_type_detection(self):
        """日曜日の種別（断食、高等評議員、通常）が正しく判定されること"""
        # 2026年10月4日 (第1日曜) -> fast
        t_fast, _ = get_sunday_type(date(2026, 10, 4), hc_week=3)
        self.assertEqual(t_fast, "fast")

        # 2026年10月11日 (第2日曜) -> regular
        t_reg, _ = get_sunday_type(date(2026, 10, 11), hc_week=3)
        self.assertEqual(t_reg, "regular")

        # 2026年10月18日 (第3日曜) -> high_council
        t_hc, _ = get_sunday_type(date(2026, 10, 18), hc_week=3)
        self.assertEqual(t_hc, "high_council")

        # 第2日曜に設定変更した場合
        t_hc2, _ = get_sunday_type(date(2026, 10, 11), hc_week=2)
        self.assertEqual(t_hc2, "high_council")

    def test_format_elapsed_text(self):
        """経過日数の表示テキストが人間可読であること"""
        self.assertEqual(format_elapsed(None, is_talk=True), "未登壇 (最優先)")
        self.assertEqual(format_elapsed(None, is_talk=False), "未担当 (最優先)")
        self.assertEqual(format_elapsed(15), "15日前")
        self.assertEqual(format_elapsed(90), "90日 (約3ヶ月前)")
        self.assertEqual(format_elapsed(400), "400日 (約1年1ヶ月前)")


if __name__ == "__main__":
    unittest.main()
