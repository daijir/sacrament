"""
聖餐会（Sacrament Meeting）お話・お祈り割り当てシミュレーター
40人の架空会員データ（青少年7人含む）をシードし、四半期（13週分）のスケジュールを最適化生成します。
外部ライブラリ不要（Python 3標準ライブラリのみ）で動作します。
"""

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple


# ==========================================
# 1. データ構造の定義
# ==========================================

@dataclass
class Member:
    id: int
    name: str
    gender: str  # 'M' or 'F'
    category: str  # 'youth' or 'adult'
    household_id: int  # 同じ家庭は同じID
    is_bishopric: bool = False  # 進行・司会のため通常割り当て対象外
    couple_talk_together: bool = False  # 夫婦で話すなら同じ日を希望
    has_small_children: bool = False  # 夫婦で同日に役割が重なるのを避けたい
    is_new_member: bool = False  # 新会員（お祈りや短めの話優先）
    
    # 過去の履歴（直近の日付）
    last_talk_date: Optional[date] = None
    last_prayer_date: Optional[date] = None

    # 今回のシミュレーション期間中に割り当てられた履歴
    talk_count: int = 0
    prayer_count: int = 0


@dataclass
class SundayService:
    meeting_date: date
    is_fast_sunday: bool  # 第1日曜日（断食証しの会）：お話なし
    special_notes: str = ""
    
    # 割り当てスロット
    invocation: Optional[Member] = None    # 開会の祈り
    benediction: Optional[Member] = None   # 閉会の祈り
    youth_talk: Optional[Member] = None    # 青少年のお話（通常5分）
    adult_talk_1: Optional[Member] = None  # 成人のお話1（通常10-12分）
    adult_talk_2: Optional[Member] = None  # 成人のお話2（通常10-12分）


# ==========================================
# 2. 会員40名のダミーデータ生成（Seed）
# ==========================================

def seed_members(base_date: date) -> List[Member]:
    random.seed(42)  # 再現性のためのシード
    
    members: List[Member] = []
    current_id = 1
    
    # 世帯1: ビショップ家庭（夫婦 + 青少年1人）
    members.append(Member(id=current_id, name="佐藤 健一 (ビショップ)", gender="M", category="adult", household_id=1, is_bishopric=True))
    current_id += 1
    members.append(Member(id=current_id, name="佐藤 真弓", gender="F", category="adult", household_id=1))
    current_id += 1
    members.append(Member(id=current_id, name="佐藤 蓮", gender="M", category="youth", household_id=1))
    current_id += 1

    # 世帯2: 第1顧問家庭（夫婦）
    members.append(Member(id=current_id, name="鈴木 雄大 (第1顧問)", gender="M", category="adult", household_id=2, is_bishopric=True))
    current_id += 1
    members.append(Member(id=current_id, name="鈴木 恵子", gender="F", category="adult", household_id=2))
    current_id += 1

    # 世帯3: 第2顧問家庭（夫婦 + 青少年1人）
    members.append(Member(id=current_id, name="高橋 誠 (第2顧問)", gender="M", category="adult", household_id=3, is_bishopric=True))
    current_id += 1
    members.append(Member(id=current_id, name="高橋 幸恵", gender="F", category="adult", household_id=3))
    current_id += 1
    members.append(Member(id=current_id, name="高橋 結衣", gender="F", category="youth", household_id=3))
    current_id += 1

    # 世帯4: 夫婦で話したい希望の夫婦 + 青少年1人
    members.append(Member(id=current_id, name="田中 弘", gender="M", category="adult", household_id=4, couple_talk_together=True))
    current_id += 1
    members.append(Member(id=current_id, name="田中 美穂", gender="F", category="adult", household_id=4, couple_talk_together=True))
    current_id += 1
    members.append(Member(id=current_id, name="田中 颯太", gender="M", category="youth", household_id=4))
    current_id += 1

    # 世帯5: 乳幼児がいる家庭（同日重複NG）
    members.append(Member(id=current_id, name="渡辺 拓也", gender="M", category="adult", household_id=5, has_small_children=True))
    current_id += 1
    members.append(Member(id=current_id, name="渡辺 香織", gender="F", category="adult", household_id=5, has_small_children=True))
    current_id += 1

    # 世帯6: 夫婦 + 青少年2人（兄妹）
    members.append(Member(id=current_id, name="伊藤 直樹", gender="M", category="adult", household_id=6))
    current_id += 1
    members.append(Member(id=current_id, name="伊藤 由香", gender="F", category="adult", household_id=6))
    current_id += 1
    members.append(Member(id=current_id, name="伊藤 陸", gender="M", category="youth", household_id=6))
    current_id += 1
    members.append(Member(id=current_id, name="伊藤 葵", gender="F", category="youth", household_id=6))
    current_id += 1

    # 世帯7: 母子家庭（母 + 青少年1人）
    members.append(Member(id=current_id, name="山本 明美", gender="F", category="adult", household_id=7))
    current_id += 1
    members.append(Member(id=current_id, name="山本 翔太", gender="M", category="youth", household_id=7))
    current_id += 1

    # 世帯8: 青少年1人（親は未会員/送迎のみ想定）
    members.append(Member(id=current_id, name="中村 莉乃", gender="F", category="youth", household_id=8))
    current_id += 1

    # 世帯9: 新会員（最近バプテスマ）
    members.append(Member(id=current_id, name="小林 健二 (新会員)", gender="M", category="adult", household_id=9, is_new_member=True))
    current_id += 1

    # 世帯10〜19: その他の成人会員（夫婦または単身者）
    adult_couples_and_singles = [
        ("加藤 秀樹", "M", 10, True), ("加藤 陽子", "F", 10, True),  # 夫婦登壇希望
        ("吉田 誠司", "M", 11, False), ("吉田 智子", "F", 11, False),
        ("山田 太郎", "M", 12, False), ("山田 花子", "F", 12, False),
        ("佐々木 亮", "M", 13, False), ("佐々木 晴美", "F", 13, False),
        ("山口 大地", "M", 14, False),
        ("松本 美紀", "F", 15, False),
        ("井上 浩平", "M", 16, False), ("井上 裕子", "F", 16, False),
        ("木村 純一", "M", 17, False),
        ("林 さくら", "F", 18, False),
        ("清水 俊介", "M", 19, False), ("清水 友理", "F", 19, False),
        ("斎藤 和彦", "M", 20, False),
        ("池田 麻衣", "F", 21, False),
        ("橋本 勇", "M", 22, False),
    ]

    for name, gender, hid, couple_pref in adult_couples_and_singles:
        members.append(Member(
            id=current_id,
            name=name,
            gender=gender,
            category="adult",
            household_id=hid,
            couple_talk_together=couple_pref
        ))
        current_id += 1

    # 過去の履歴をランダムシード（1ヶ月〜18ヶ月前）
    for m in members:
        if not m.is_bishopric:
            # 前回の話（120日〜400日前）
            talk_days_ago = random.randint(120, 450)
            m.last_talk_date = base_date - timedelta(days=talk_days_ago)
            
            # 前回のお祈り（30日〜180日前）
            prayer_days_ago = random.randint(30, 200)
            m.last_prayer_date = base_date - timedelta(days=prayer_days_ago)

    # 青少年は7人になっているか確認
    youth_count = sum(1 for m in members if m.category == "youth")
    adult_count = sum(1 for m in members if m.category == "adult")
    assert len(members) == 40, f"会員数合計: {len(members)}"
    assert youth_count == 7, f"青少年数: {youth_count}"

    return members


# ==========================================
# 3. 日曜日カレンダーの生成
# ==========================================

def generate_sundays(start_date: date, weeks: int = 13) -> List[SundayService]:
    """直近の日曜日から指定週分の日曜日リストを生成"""
    sundays = []
    # 直近の日曜日を探す
    cur = start_date
    while cur.weekday() != 6:  # 6 is Sunday in Python
        cur += timedelta(days=1)
        
    for _ in range(weeks):
        # その月の最初の日曜日かどうか判定（第1日曜日 = 断食証しの会）
        is_first_sunday = (cur.day <= 7)
        note = "【断食証しの会】" if is_first_sunday else "通常聖餐会"
        sundays.append(SundayService(
            meeting_date=cur,
            is_fast_sunday=is_first_sunday,
            special_notes=note
        ))
        cur += timedelta(days=7)
    return sundays


# ==========================================
# 4. 割り当てアルゴリズム（スコアリング＆制約充足）
# ==========================================

class SacramentScheduler:
    def __init__(self, members: List[Member]):
        self.members = members

    def _calculate_priority_score(
        self,
        member: Member,
        target_date: date,
        role: str,  # 'talk' or 'prayer'
        assigned_today: List[Member]
    ) -> float:
        """
        候補者の適性スコアを計算（高いほど優先）
        """
        # ハード制約チェック
        # 1. ビショップリックは除外
        if member.is_bishopric:
            return -99999.0

        # 2. 本日すでに役割を持っている場合は除外
        if member in assigned_today:
            return -99999.0

        # 3. 小さい子どもがいる家庭で、配偶者が本日すでにアサインされている場合は除外
        if member.has_small_children:
            if any(m.household_id == member.household_id for m in assigned_today):
                return -99999.0

        # 4. インターバル間隔のチェック
        if role == "talk":
            if member.last_talk_date:
                days_since = (target_date - member.last_talk_date).days
                if days_since < 60:  # 最低2ヶ月（約8週）は空ける
                    return -99999.0
            else:
                days_since = 365

            # スコア計算: 前回からの経過日数が長いほど高スコア
            # 今回すでに話した回数が増えるごとに超大幅ペナルティ
            score = days_since * 1.0 - (member.talk_count * 10000.0)

            # 新会員への配慮（いきなりメイントークにしない）
            if member.is_new_member:
                score -= 200.0

        else:  # 'prayer'
            if member.last_prayer_date:
                days_since = (target_date - member.last_prayer_date).days
                if days_since < 28:  # 最低4週間は空ける
                    return -99999.0
            else:
                days_since = 180

            score = days_since * 1.0 - (member.prayer_count * 5000.0)

            # 新会員はお祈りで参加しやすいようボーナス
            if member.is_new_member:
                score += 150.0

        return score

    def schedule_quarter(self, services: List[SundayService]):
        """四半期スケジュールを週ごとに最適化して割り振る"""
        for service in services:
            d = service.meeting_date
            assigned_today: List[Member] = []

            # ----------------------------------------------------
            # 1. お話（Talk）の割り当て（断食証しの会でない場合）
            # ----------------------------------------------------
            if not service.is_fast_sunday:
                # (1) 青少年のお話（1名）
                youth_candidates = [m for m in self.members if m.category == "youth"]
                youth_candidates.sort(
                    key=lambda m: self._calculate_priority_score(m, d, "talk", assigned_today),
                    reverse=True
                )
                if youth_candidates:
                    chosen_youth = youth_candidates[0]
                    service.youth_talk = chosen_youth
                    assigned_today.append(chosen_youth)

                # (2) 成人のお話（2名）
                # 夫婦で同じ日に話したい人を優先ペアリングするか確認
                couple_assigned = False
                couple_candidates = [
                    m for m in self.members
                    if m.category == "adult" and m.couple_talk_together
                ]
                
                # 夫婦ペアを探す
                household_groups: Dict[int, List[Member]] = {}
                for cm in couple_candidates:
                    household_groups.setdefault(cm.household_id, []).append(cm)

                for hid, pair in household_groups.items():
                    if len(pair) == 2:
                        p1, p2 = pair[0], pair[1]
                        score1 = self._calculate_priority_score(p1, d, "talk", assigned_today)
                        score2 = self._calculate_priority_score(p2, d, "talk", assigned_today)
                        # 夫婦両方が条件を満たしている場合
                        if score1 > 0 and score2 > 0 and p1.talk_count == 0 and p2.talk_count == 0:
                            # 一定の確率または高優先ならペアで登壇
                            if (score1 + score2) > 300:
                                service.adult_talk_1 = p1
                                service.adult_talk_2 = p2
                                assigned_today.extend([p1, p2])
                                couple_assigned = True
                                break

                # 夫婦ペアにならなかった場合、通常の成人から男女バランスよく選抜
                if not couple_assigned:
                    adult_candidates = [m for m in self.members if m.category == "adult"]
                    adult_candidates.sort(
                        key=lambda m: self._calculate_priority_score(m, d, "talk", assigned_today),
                        reverse=True
                    )
                    
                    # 1人目
                    speaker1 = adult_candidates[0]
                    service.adult_talk_1 = speaker1
                    assigned_today.append(speaker1)

                    # 2人目: 異性を優先（男女バランス）
                    other_gender = 'F' if speaker1.gender == 'M' else 'M'
                    speaker2_candidates = [
                        m for m in adult_candidates[1:]
                        if self._calculate_priority_score(m, d, "talk", assigned_today) > -1000
                    ]
                    # できれば異性
                    preferred_gender_candidates = [m for m in speaker2_candidates if m.gender == other_gender]
                    speaker2 = preferred_gender_candidates[0] if preferred_gender_candidates else speaker2_candidates[0]
                    
                    service.adult_talk_2 = speaker2
                    assigned_today.append(speaker2)

            # ----------------------------------------------------
            # 2. お祈り（開会・閉会）の割り当て
            # ----------------------------------------------------
            # 開会・閉会の祈りは、男女1名ずつになるように配慮
            # 青少年も大人も含めて候補とする
            prayer_candidates = [m for m in self.members if not m.is_bishopric]
            
            # 開会の祈り（Invocation）の候補選定
            prayer_candidates.sort(
                key=lambda m: self._calculate_priority_score(m, d, "prayer", assigned_today),
                reverse=True
            )
            invocator = prayer_candidates[0]
            service.invocation = invocator
            assigned_today.append(invocator)

            # 閉会の祈り（Benediction）: 異性を優先
            other_prayer_gender = 'F' if invocator.gender == 'M' else 'M'
            benediction_pool = [
                m for m in prayer_candidates
                if self._calculate_priority_score(m, d, "prayer", assigned_today) > -1000
            ]
            preferred_benediction = [m for m in benediction_pool if m.gender == other_prayer_gender]
            benedictor = preferred_benediction[0] if preferred_benediction else benediction_pool[0]

            service.benediction = benedictor
            assigned_today.append(benedictor)

            # ----------------------------------------------------
            # 3. 履歴の更新
            # ----------------------------------------------------
            for speaker in [service.youth_talk, service.adult_talk_1, service.adult_talk_2]:
                if speaker:
                    speaker.last_talk_date = d
                    speaker.talk_count += 1
            
            for prayer in [service.invocation, service.benediction]:
                if prayer:
                    prayer.last_prayer_date = d
                    prayer.prayer_count += 1


# ==========================================
# 5. 結果の表示・出力
# ==========================================

def print_schedule(services: List[SundayService], members: List[Member]):
    print("=" * 88)
    print("                 聖餐会（Sacrament Meeting）四半期割り当てスケジュール")
    print("=" * 88)
    print(f"{'日付':<12} | {'開会の祈り':<12} | {'青少年のお話':<12} | {'成人のお話1':<14} | {'成人のお話2':<14} | {'閉会の祈り':<12}")
    print("-" * 88)

    for s in services:
        d_str = s.meeting_date.strftime("%Y-%m-%d")
        inv = f"{s.invocation.name} ({s.invocation.gender})" if s.invocation else "-"
        ben = f"{s.benediction.name} ({s.benediction.gender})" if s.benediction else "-"
        
        if s.is_fast_sunday:
            yt = "【断食証】"
            at1 = "-"
            at2 = "-"
        else:
            yt = f"{s.youth_talk.name}" if s.youth_talk else "-"
            at1 = f"{s.adult_talk_1.name}" if s.adult_talk_1 else "-"
            at2 = f"{s.adult_talk_2.name}" if s.adult_talk_2 else "-"

        print(f"{d_str:<12} | {inv:<12} | {yt:<12} | {at1:<14} | {at2:<14} | {ben:<12}")

    print("=" * 88)
    print("\n【集計・統計情報】")
    youths = [m for m in members if m.category == "youth"]
    adults = [m for m in members if m.category == "adult" and not m.is_bishopric]
    bishopric = [m for m in members if m.is_bishopric]

    print(f"・会員総数: {len(members)}名 (大人: {len(adults)}名, ビショップリック: {len(bishopric)}名, 青少年: {len(youths)}名)")
    print(f"・青少年のお話担当回数:")
    for y in youths:
        print(f"    - {y.name}: お話 {y.talk_count}回, 祈り {y.prayer_count}回")

    print(f"\n・大人の割り当て偏りチェック (お話 2回以上の会員):")
    multi_talk = [m for m in adults if m.talk_count >= 2]
    if not multi_talk:
        print("    -> なし（全員1回以下で公平に分散されています！）")
    else:
        for m in multi_talk:
            print(f"    - {m.name}: お話 {m.talk_count}回")


if __name__ == "__main__":
    start_date = date(2026, 10, 1)  # 2026年第4四半期スタート
    members = seed_members(start_date)
    sundays = generate_sundays(start_date, weeks=13)

    scheduler = SacramentScheduler(members)
    scheduler.schedule_quarter(sundays)

    print_schedule(sundays, members)
