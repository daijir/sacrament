"""
確率・公平性・長期シミュレーションテスト (Probability & Fairness Test)
1年間（52週）のシミュレーションを実行し、統計的な偏りや飢餓状態がないかを検証します。
"""

import unittest
from datetime import date
import sys
from pathlib import Path
import math

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sacrament import (
    Member,
    generate_schedule,
    load_members,
)


class TestProbabilityAndFairness(unittest.TestCase):
    def setUp(self):
        # 40名のサンプルデータをベースにテスト用プールを構築
        self.members = load_members()
        # 過去実績日をリセットして公平なテスト環境を用意
        base_date = date(2025, 1, 1)
        for m in self.members.values():
            m.last_talk_date = None
            m.last_prayer_date = None
            m.total_talks = 0
            m.total_prayers = 0

    def test_no_starvation_in_one_year(self):
        """1年間（52週）の運用で、登壇・お祈りの飢餓状態（一度も当たらない会員）がゼロであること"""
        # 52週間のスケジュールをシミュレーション
        slots = generate_schedule(self.members, weeks=52, start_date=date(2026, 1, 4))
        self.assertEqual(len(slots), 52)

        # ビショップリック・高等評議員以外の成人会員
        eligible_talkers = [
            m for m in self.members.values()
            if not m.is_bishopric and not m.is_high_councilor and m.category == "adult"
        ]
        eligible_prayers = [
            m for m in self.members.values()
            if not m.is_bishopric
        ]
        youths = [
            m for m in self.members.values()
            if m.category == "youth"
        ]

        # 1. 成人話者の飢餓チェック
        unassigned_talkers = [m for m in eligible_talkers if m.total_talks == 0]
        self.assertEqual(
            len(unassigned_talkers), 0,
            f"1年間で一度もお話ししなかった成人会員がいます: {[m.name for m in unassigned_talkers]}"
        )

        # 2. お祈りの飢餓チェック
        unassigned_prayers = [m for m in eligible_prayers if m.total_prayers == 0]
        self.assertEqual(
            len(unassigned_prayers), 0,
            f"1年間で一度もお祈りしなかった会員がいます: {[m.name for m in unassigned_prayers]}"
        )

        # 3. 青少年の飢餓チェック
        unassigned_youths = [m for m in youths if m.total_talks == 0]
        self.assertEqual(
            len(unassigned_youths), 0,
            f"1年間で一度もお話ししなかった青少年がいます: {[m.name for m in unassigned_youths]}"
        )

    def test_talk_frequency_distribution_fairness(self):
        """成人話者の登壇回数の分散が小さく、特定の人に偏っていないこと（公平性）"""
        generate_schedule(self.members, weeks=52, start_date=date(2026, 1, 4))

        eligible = [
            m for m in self.members.values()
            if not m.is_bishopric and not m.is_high_councilor and m.category == "adult"
        ]
        counts = [m.total_talks for m in eligible]
        
        avg_talks = sum(counts) / len(counts)
        variance = sum((x - avg_talks) ** 2 for x in counts) / len(counts)
        std_dev = math.sqrt(variance)
        max_diff = max(counts) - min(counts)

        # 最大・最小の差が2回以内に収まっていること（特定の人ばかり何回も当たらない）
        self.assertLessEqual(max_diff, 2, f"登壇回数の格差が大きすぎます (最大: {max(counts)}, 最小: {min(counts)})")
        # 標準偏差が1.0未満（均等に分散している）
        self.assertLess(std_dev, 1.0, f"登壇回数の標準偏差が大きすぎます: {std_dev:.2f}")

    def test_prayer_gender_balance_convergence(self):
        """通年のお祈り担当の男女比率が 50% : 50% （誤差±5%以内）に収束すること"""
        slots = generate_schedule(self.members, weeks=52, start_date=date(2026, 1, 4))

        male_prayers = 0
        female_prayers = 0

        for s in slots:
            if s.invocation:
                if s.invocation.gender == "M":
                    male_prayers += 1
                else:
                    female_prayers += 1
            if s.benediction:
                if s.benediction.gender == "M":
                    male_prayers += 1
                else:
                    female_prayers += 1

        total_prayers = male_prayers + female_prayers
        self.assertGreater(total_prayers, 0)

        male_ratio = male_prayers / total_prayers
        female_ratio = female_prayers / total_prayers

        # 45% 〜 55% の範囲に収束していること
        self.assertAlmostEqual(male_ratio, 0.5, delta=0.05, msg=f"男性お祈り比率が偏っています: {male_ratio:.2%}")
        self.assertAlmostEqual(female_ratio, 0.5, delta=0.05, msg=f"女性お祈り比率が偏っています: {female_ratio:.2%}")

    def test_youth_talk_rotation(self):
        """青少年（7名）がおよそ月1回弱のペースで全員均等にお話を経験できていること"""
        generate_schedule(self.members, weeks=52, start_date=date(2026, 1, 4))

        youths = [m for m in self.members.values() if m.category == "youth"]
        youth_counts = [y.total_talks for y in youths]

        # 断食週（12回）を除くと青少年枠は約40回。7人で割ると一人あたり5〜6回前後になるはず
        for y in youths:
            self.assertGreaterEqual(y.total_talks, 4, f"{y.name}の登壇回数が少なすぎます: {y.total_talks}")
            self.assertLessEqual(y.total_talks, 8, f"{y.name}の登壇回数が多すぎます: {y.total_talks}")


if __name__ == "__main__":
    unittest.main()
