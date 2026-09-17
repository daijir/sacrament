#!/usr/bin/env python3
"""
聖餐会（Sacrament Meeting）お話・お祈り 推薦＆スケジューリング CLIツール
Church Data Privacy Safe - 100% Local CLI
"""

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = DATA_DIR / "private"
SAMPLE_DIR = DATA_DIR / "sample_data"

# private/members.csv があれば本番モード、なければ sample_data/ を使用
if (PRIVATE_DIR / "members.csv").exists():
    MEMBERS_CSV = PRIVATE_DIR / "members.csv"
    HISTORY_JSON = PRIVATE_DIR / "history.json"
    SCHEDULE_JSON = PRIVATE_DIR / "schedule.json"
    IS_PRIVATE_MODE = True
else:
    MEMBERS_CSV = SAMPLE_DIR / "members.csv"
    HISTORY_JSON = SAMPLE_DIR / "history.json"
    SCHEDULE_JSON = SAMPLE_DIR / "schedule.json"
    IS_PRIVATE_MODE = False


def print_mode_badge():
    """実行モードのバッジを表示"""
    if IS_PRIVATE_MODE:
        print("[本番モード] private/ の実会員データを使用しています (.gitignore対象)")
    else:
        print("[サンプルモード] sample_data/ の架空データを使用しています")


# ==========================================
# 1. データモデル
# ==========================================

@dataclass
class Member:
    id: int
    name: str
    gender: str          # 'M' or 'F'
    category: str        # 'youth' or 'adult'
    household_id: int
    is_bishopric: bool = False
    couple_talk_together: bool = False
    has_small_children: bool = False
    is_new_member: bool = False
    is_high_councilor: bool = False  # 高等評議員フラグ（ステーク巡回のため自ワード通常話者枠から除外）

    # 履歴から計算される項目
    last_talk_date: Optional[date] = None
    last_prayer_date: Optional[date] = None
    total_talks: int = 0
    total_prayers: int = 0


# ==========================================
# 2. ストレージ（CSV/JSONの読み書き）
# ==========================================

def load_members() -> Dict[int, Member]:
    """members.csvから会員名簿を読み込む"""
    if not MEMBERS_CSV.exists():
        print(f"[エラー] 会員ファイルが見つかりません: {MEMBERS_CSV}")
        print("サンプルを使用する場合は sample_data/members.csv を配置してください。")
        print("本番データを使用する場合は private/members.csv を配置してください。")
        sys.exit(1)

    members = {}
    with open(MEMBERS_CSV, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            m = Member(
                id=int(row["id"]),
                name=row["name"].strip(),
                gender=row["gender"].strip().upper(),
                category=row["category"].strip().lower(),
                household_id=int(row["household_id"]),
                is_bishopric=row.get("is_bishopric", "false").strip().lower() == "true",
                couple_talk_together=row.get("couple_talk_together", "false").strip().lower() == "true",
                has_small_children=row.get("has_small_children", "false").strip().lower() == "true",
                is_new_member=row.get("is_new_member", "false").strip().lower() == "true",
                is_high_councilor=row.get("is_high_councilor", "false").strip().lower() == "true",
            )
            members[m.id] = m

    # 履歴をマッピング
    history = load_history()
    for record in history:
        mid = record["member_id"]
        if mid in members:
            m = members[mid]
            rec_date = datetime.strptime(record["date"], "%Y-%m-%d").date()
            if record["role"] == "talk":
                m.total_talks += 1
                if m.last_talk_date is None or rec_date > m.last_talk_date:
                    m.last_talk_date = rec_date
            elif record["role"] == "prayer":
                m.total_prayers += 1
                if m.last_prayer_date is None or rec_date > m.last_prayer_date:
                    m.last_prayer_date = rec_date

    return members


def load_history() -> List[Dict]:
    """history.jsonを読み込む"""
    if not HISTORY_JSON.exists():
        return []
    with open(HISTORY_JSON, mode="r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return []


def save_history(history: List[Dict]):
    """history.jsonに保存"""
    HISTORY_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_JSON, mode="w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def load_schedule() -> Dict[str, Dict]:
    """schedule.jsonを読み込む"""
    if not SCHEDULE_JSON.exists():
        return {}
    with open(SCHEDULE_JSON, mode="r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}


def save_schedule(schedule: Dict[str, Dict]):
    """schedule.jsonに保存"""
    SCHEDULE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULE_JSON, mode="w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)


# ==========================================
# 3. アルゴリズム・スコアリング
# ==========================================

def get_sunday_type(d: date, hc_week: int = 3) -> Tuple[str, str]:
    """
    日曜日の種別を判定
    戻り値: (type_id, 日本語タイトル)
    - "fast": 第1日曜日（断食証しの会）
    - "high_council": 高等評議員登壇週（指定週、デフォルト第3日曜日）
    - "regular": 通常聖餐会
    """
    nth_sunday = (d.day - 1) // 7 + 1
    if nth_sunday == 1:
        return "fast", "【断食証しの会】"
    elif hc_week > 0 and nth_sunday == hc_week:
        return "high_council", "【高等評議員登壇週】"
    else:
        return "regular", "【通常聖餐会】"


def calculate_score(
    member: Member,
    target_date: date,
    role: str,  # 'talk' or 'prayer'
    assigned_members: List[Member],
    exclude_ids: Optional[List[int]] = None
) -> Tuple[float, str]:
    """
    指定日のスロットにおける適性スコアと選考理由を算出
    戻り値: (スコア, 理由テキスト)
    """
    exclude_ids = exclude_ids or []
    if member.id in exclude_ids:
        return -99999.0, "除外指定"

    # ハード制約
    if member.is_bishopric:
        return -99999.0, "ビショップリックのため対象外"

    if role == "talk" and member.is_high_councilor:
        return -99999.0, "高等評議員のため自ワード枠外"

    if any(m.id == member.id for m in assigned_members):
        return -99999.0, "同日に他の役割ですでに決定済み"

    if member.has_small_children:
        if any(m.household_id == member.household_id for m in assigned_members):
            return -99999.0, "乳幼児がいるため夫婦同日重複不可"

    reasons = []

    if role == "talk":
        if member.last_talk_date:
            days_since = (target_date - member.last_talk_date).days
            if days_since < 60:
                return -99999.0, f"前回から間もない ({days_since}日前)"
            reasons.append(f"前回のお話から {days_since}日経過")
            score = float(days_since)
        else:
            days_since = 365
            reasons.append("過去に登壇記録なし (最優先)")
            score = 500.0

        if member.is_new_member:
            score -= 150.0
            reasons.append("新会員 (配慮)")

    else:  # prayer
        if member.last_prayer_date:
            days_since = (target_date - member.last_prayer_date).days
            if days_since < 28:
                return -99999.0, f"前回のお祈りから間もない ({days_since}日前)"
            reasons.append(f"前回のお祈りから {days_since}日経過")
            score = float(days_since)
        else:
            days_since = 180
            reasons.append("過去にお祈り記録なし")
            score = 300.0

        if member.is_new_member:
            score += 100.0
            reasons.append("新会員ボーナス")

    return score, ", ".join(reasons)


# ==========================================
# 4. コマンド実装
# ==========================================

def cmd_init(args):
    """初期データのシード（過去履歴の自動生成）"""
    print_mode_badge()
    members = load_members()
    base_date = date.today()
    random.seed(42)

    history = []
    for m in members.values():
        if not m.is_bishopric:
            # 前回の話
            talk_days = random.randint(100, 420)
            t_date = base_date - timedelta(days=talk_days)
            history.append({
                "date": t_date.strftime("%Y-%m-%d"),
                "member_id": m.id,
                "member_name": m.name,
                "role": "talk"
            })
            # 前回のお祈り
            pray_days = random.randint(30, 180)
            p_date = base_date - timedelta(days=pray_days)
            history.append({
                "date": p_date.strftime("%Y-%m-%d"),
                "member_id": m.id,
                "member_name": m.name,
                "role": "prayer"
            })

    save_history(history)
    print(f"[完了] 初期化完了: {len(history)} 件の過去履歴を {HISTORY_JSON} に生成しました。")


def get_member_notes(m: Member) -> str:
    """会員の配慮フラグを日本語テキスト化"""
    notes = []
    if m.is_bishopric:
        notes.append("ビショップリック")
    if m.is_high_councilor:
        notes.append("高等評議員")
    if m.couple_talk_together:
        notes.append("夫婦希望")
    if m.has_small_children:
        notes.append("乳幼児あり")
    if m.is_new_member:
        notes.append("新会員")
    return ", ".join(notes) if notes else "-"


def cmd_status(args):
    """会員ごとの登壇・お祈り実績および『ご無沙汰』ランキング表示"""
    print_mode_badge()
    members = load_members()
    today = date.today()

    print("\n" + "=" * 70)
    print("      【会員ステータス & お話ご無沙汰ランキング】")
    print("=" * 70)
    
    # 通常登壇対象（ビショップリック・高等評議員以外）
    active_pool = [m for m in members.values() if not m.is_bishopric and not m.is_high_councilor]
    active_pool.sort(
        key=lambda m: (m.last_talk_date is not None, m.last_talk_date or date.min)
    )

    print(f"{'順位':<4} | {'氏名':<16} | {'区分':<6} | {'最終登壇日':<12} | {'経過日数':<8} | {'備考'}")
    print("-" * 70)

    for i, m in enumerate(active_pool[:args.top], 1):
        if m.last_talk_date:
            days = (today - m.last_talk_date).days
            days_str = f"{days}日"
            last_date_str = m.last_talk_date.strftime("%Y-%m-%d")
        else:
            days_str = "未登壇"
            last_date_str = "記録なし"

        note_str = get_member_notes(m)
        print(f"{i:<4} | {m.name:<16} | {m.category:<6} | {last_date_str:<12} | {days_str:<8} | {note_str}")
    print("=" * 70 + "\n")


def format_elapsed(days: Optional[int], is_talk: bool = True) -> str:
    """経過日数を直感的なテキスト（○ヶ月前、○年前）に変換"""
    if days is None:
        return "未登壇 (最優先)" if is_talk else "未担当 (最優先)"
    if days < 30:
        return f"{days}日前"
    elif days < 365:
        months = max(1, days // 30)
        return f"{days}日 (約{months}ヶ月前)"
    else:
        years = days // 365
        rem_months = (days % 365) // 30
        month_str = f"{rem_months}ヶ月" if rem_months > 0 else ""
        return f"{days}日 (約{years}年{month_str}前)"


def cmd_list(args):
    """ビショップリック会議・支部会長会用の縦長ご無沙汰リストを出力"""
    print_mode_badge()
    members = load_members()
    today = date.today()
    is_prayer = (args.role == "prayer")

    # 対象グループの定義（お話の場合は高等評議員を除外、お祈りは参加可能）
    groups = []
    if args.category in ("all", "adult-m"):
        if is_prayer:
            m_adults = [m for m in members.values() if m.category == "adult" and m.gender == "M" and not m.is_bishopric]
        else:
            m_adults = [m for m in members.values() if m.category == "adult" and m.gender == "M" and not m.is_bishopric and not m.is_high_councilor]
        groups.append(("成人男性（兄弟）", m_adults))
    if args.category in ("all", "adult-f"):
        f_adults = [m for m in members.values() if m.category == "adult" and m.gender == "F" and not m.is_bishopric]
        groups.append(("成人女性（姉妹）", f_adults))
    if args.category in ("all", "youth"):
        youths = [m for m in members.values() if m.category == "youth"]
        groups.append(("青少年（ユース）", youths))

    role_title = "お祈り" if is_prayer else "お話"

    # TSVフォーマットの場合
    if args.format == "tsv":
        print(f"グループ\t順位\t氏名\t性別\t区分\t最終{role_title}日\t経過日数\t経過目安\t累計回数\t備考")
        for group_name, m_list in groups:
            # ソート
            if is_prayer:
                m_list.sort(key=lambda m: (m.last_prayer_date is not None, m.last_prayer_date or date.min, m.total_prayers))
            else:
                m_list.sort(key=lambda m: (m.last_talk_date is not None, m.last_talk_date or date.min, m.total_talks))

            limit = args.top if args.top > 0 else len(m_list)
            for i, m in enumerate(m_list[:limit], 1):
                rec_date = m.last_prayer_date if is_prayer else m.last_talk_date
                total_cnt = m.total_prayers if is_prayer else m.total_talks
                days = (today - rec_date).days if rec_date else None
                days_num = str(days) if days is not None else ""
                elapsed_str = format_elapsed(days, is_talk=not is_prayer)
                date_str = rec_date.strftime("%Y-%m-%d") if rec_date else "記録なし"
                note_str = get_member_notes(m)

                print(f"{group_name}\t{i}\t{m.name}\t{m.gender}\t{m.category}\t{date_str}\t{days_num}\t{elapsed_str}\t{total_cnt}\t{note_str}")
        return

    # Markdownフォーマットの場合
    if args.format == "markdown":
        print(f"\n# 聖餐会 {role_title} ご無沙汰リスト（{today.strftime('%Y-%m-%d')} 時点）\n")
        for group_name, m_list in groups:
            if is_prayer:
                m_list.sort(key=lambda m: (m.last_prayer_date is not None, m.last_prayer_date or date.min, m.total_prayers))
            else:
                m_list.sort(key=lambda m: (m.last_talk_date is not None, m.last_talk_date or date.min, m.total_talks))

            print(f"### ■ {group_name} ({len(m_list)}名)")
            print(f"| 順位 | 氏名 | 最終{role_title}日 | 経過 | 累計 | 備考 |")
            print("| :---: | :--- | :---: | :--- | :---: | :--- |")

            limit = args.top if args.top > 0 else len(m_list)
            for i, m in enumerate(m_list[:limit], 1):
                rec_date = m.last_prayer_date if is_prayer else m.last_talk_date
                total_cnt = m.total_prayers if is_prayer else m.total_talks
                days = (today - rec_date).days if rec_date else None
                elapsed_str = format_elapsed(days, is_talk=not is_prayer)
                date_str = rec_date.strftime("%Y-%m-%d") if rec_date else "記録なし"
                note_str = get_member_notes(m)

                print(f"| {i} | {m.name} | {date_str} | {elapsed_str} | {total_cnt}回 | {note_str} |")
            print()
        return

    # テーブル表示（デフォルト）
    print("\n" + "=" * 80)
    print(f"        【会議用縦長リスト】 聖餐会 {role_title} ご無沙汰順一覧 ({today.strftime('%Y-%m-%d')} 時点)")
    print("=" * 80)

    for group_name, m_list in groups:
        if is_prayer:
            m_list.sort(key=lambda m: (m.last_prayer_date is not None, m.last_prayer_date or date.min, m.total_prayers))
        else:
            m_list.sort(key=lambda m: (m.last_talk_date is not None, m.last_talk_date or date.min, m.total_talks))

        print(f"\n▶ ■ {group_name} (対象: {len(m_list)}名)")
        print(f"{'順位':<4} | {'氏名':<16} | {'最終実績日':<12} | {'経過（目安）':<22} | {'累計':<4} | {'備考'}")
        print("-" * 80)

        limit = args.top if args.top > 0 else len(m_list)
        for i, m in enumerate(m_list[:limit], 1):
            rec_date = m.last_prayer_date if is_prayer else m.last_talk_date
            total_cnt = m.total_prayers if is_prayer else m.total_talks
            days = (today - rec_date).days if rec_date else None
            elapsed_str = format_elapsed(days, is_talk=not is_prayer)
            date_str = rec_date.strftime("%Y-%m-%d") if rec_date else "記録なし"
            note_str = get_member_notes(m)

            print(f"{i:<4} | {m.name:<16} | {date_str:<12} | {elapsed_str:<22} | {total_cnt:>2}回 | {note_str}")

    print("\n" + "=" * 80)
    print("※ 会議のポイント: 上位から順に検討しつつ、レッスン担当・家庭の状況・霊感に合わせて調整してください。")
    print("※ Excel貼り付け用: `python sacrament.py list --format tsv`")
    print("=" * 80 + "\n")


def cmd_recommend(args):
    """指定された日曜日の各スロットの候補トップ3〜5をレコメンド"""
    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("[エラー] 日付は YYYY-MM-DD 形式で入力してください (例: 2026-10-11)")
        return

    hc_week = getattr(args, "hc_week", 3)
    sunday_type, type_title = get_sunday_type(target_date, hc_week=hc_week)
    print_mode_badge()
    members = load_members()
    assigned = []

    d_str = target_date.strftime("%Y-%m-%d")

    print("\n" + "=" * 76)
    print(f"   聖餐会レコメンド: {d_str} {type_title}")
    print("=" * 76)

    # 1. 青少年のお話（断食証しの会でない場合）
    if sunday_type != "fast":
        print("\n■ 【青少年のお話 (5分枠)】 候補推薦:")
        youths = [m for m in members.values() if m.category == "youth"]
        scored_youths = []
        for y in youths:
            s, reason = calculate_score(y, target_date, "talk", assigned)
            if s > 0:
                scored_youths.append((s, y, reason))
        scored_youths.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, m, reason) in enumerate(scored_youths[:3], 1):
            print(f"  {rank}. {m.name} ({m.gender}) -> {reason}")

    # 2. 成人のお話
    if sunday_type == "high_council":
        print("\n■ 【成人のお話 (10-12分枠: 1名)】 候補推薦:")
        print("  ※ ステーク派遣の高等評議員が登壇予定のため、自ワードからの成人話者は【1名のみ】選出します。")
        adults = [m for m in members.values() if m.category == "adult" and not m.is_bishopric and not m.is_high_councilor]
        scored_adults = []
        for a in adults:
            s, reason = calculate_score(a, target_date, "talk", assigned)
            if s > 0:
                scored_adults.append((s, a, reason))
        scored_adults.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, m, reason) in enumerate(scored_adults[:5], 1):
            print(f"  {rank}. {m.name} ({m.gender}) -> {reason}")

    elif sunday_type == "regular":
        print("\n■ 【成人のお話 (10-12分枠: 2名)】 候補推薦:")
        couples: Dict[int, List[Member]] = {}
        for m in members.values():
            if m.category == "adult" and m.couple_talk_together and not m.is_bishopric and not m.is_high_councilor:
                couples.setdefault(m.household_id, []).append(m)

        couple_recommendations = []
        for hid, pair in couples.items():
            if len(pair) == 2:
                s1, r1 = calculate_score(pair[0], target_date, "talk", assigned)
                s2, r2 = calculate_score(pair[1], target_date, "talk", assigned)
                if s1 > 0 and s2 > 0:
                    couple_recommendations.append((s1 + s2, pair[0], pair[1], r1))
        
        if couple_recommendations:
            couple_recommendations.sort(key=lambda x: x[0], reverse=True)
            best_c = couple_recommendations[0]
            print(f"  [夫婦ペア推薦]: {best_c[1].name} & {best_c[2].name} (夫婦登壇希望フラグあり)")

        adults = [m for m in members.values() if m.category == "adult" and not m.is_bishopric and not m.is_high_councilor]
        scored_adults = []
        for a in adults:
            s, reason = calculate_score(a, target_date, "talk", assigned)
            if s > 0:
                scored_adults.append((s, a, reason))
        scored_adults.sort(key=lambda x: x[0], reverse=True)

        print("  --- 個別候補 (上位5名) ---")
        for rank, (score, m, reason) in enumerate(scored_adults[:5], 1):
            print(f"  {rank}. {m.name} ({m.gender}) -> {reason}")

    # 3. お祈り（開会・閉会）
    print("\n■ 【開会・閉会の祈り】 候補推薦 (男女バランス配慮):")
    prayers = [m for m in members.values() if not m.is_bishopric]
    males, females = [], []
    for p in prayers:
        s, reason = calculate_score(p, target_date, "prayer", assigned)
        if s > 0:
            if p.gender == "M":
                males.append((s, p, reason))
            else:
                females.append((s, p, reason))

    males.sort(key=lambda x: x[0], reverse=True)
    females.sort(key=lambda x: x[0], reverse=True)

    print("  [男性候補 上位]:")
    for rank, (score, m, reason) in enumerate(males[:2], 1):
        print(f"    - {m.name} -> {reason}")

    print("  [女性候補 上位]:")
    for rank, (score, m, reason) in enumerate(females[:2], 1):
        print(f"    - {m.name} -> {reason}")

    print("\n" + "=" * 76 + "\n")


def cmd_replace(args):
    """打診して断られた場合の即座の次点候補を表示"""
    try:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("[エラー] 日付形式は YYYY-MM-DD です。")
        return

    print_mode_badge()
    members = load_members()
    exclude_names = [n.strip() for n in args.exclude.split(",") if n.strip()]
    exclude_ids = [m.id for m in members.values() if m.name in exclude_names]

    print("\n" + "=" * 70)
    print(f"【差し替え候補検索】 {args.date} | 役割: {args.role}")
    print(f"除外対象: {', '.join(exclude_names)}")
    print("=" * 70)

    category = "youth" if "youth" in args.role else "adult"
    is_prayer = "prayer" in args.role

    pool = [m for m in members.values() if not m.is_bishopric]
    if not is_prayer:
        pool = [m for m in pool if m.category == category]

    scored = []
    for m in pool:
        s, reason = calculate_score(
            m, target_date, "prayer" if is_prayer else "talk", [], exclude_ids=exclude_ids
        )
        if s > 0:
            scored.append((s, m, reason))

    scored.sort(key=lambda x: x[0], reverse=True)

    print(f"\n[次点候補リスト] (上位5名):")
    for rank, (score, m, reason) in enumerate(scored[:5], 1):
        print(f"  {rank}. {m.name} ({m.gender}, {m.category}) -> {reason}")
    print("=" * 70 + "\n")


@dataclass
class ServiceSlot:
    meeting_date: date
    sunday_type: str
    type_title: str
    invocation: Optional[Member] = None
    benediction: Optional[Member] = None
    youth_talk: Optional[Member] = None
    adult_talk_1: Optional[Member] = None
    adult_talk_2: Optional[Member] = None
    is_high_council_slot: bool = False


def select_best_candidate(
    candidates: List[Member],
    target_date: date,
    role: str,
    assigned_today: List[Member],
    allow_fallback: bool = True
) -> Optional[Member]:
    """
    候補リストからスコア最大の会員を安全に選出。
    全員がインターバル等の制約に引っかかる場合でも、allow_fallback=Trueなら
    ハード制約（同日重複等）を破らない範囲で最もご無沙汰な会員をフォールバック選出。
    """
    if not candidates:
        return None

    scored = []
    for m in candidates:
        s, reason = calculate_score(m, target_date, role, assigned_today)
        if s > 0:
            scored.append((s, m))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    # 有効候補がいない場合のフォールバック（同日重複やビショップリック等は厳格に除外）
    if allow_fallback:
        fallback_pool = [
            m for m in candidates
            if not m.is_bishopric
            and not (role == "talk" and m.is_high_councilor)
            and not any(a.id == m.id for a in assigned_today)
            and not (m.has_small_children and any(a.household_id == m.household_id for a in assigned_today))
        ]
        if fallback_pool:
            if role == "talk":
                fallback_pool.sort(key=lambda m: (m.last_talk_date is not None, m.last_talk_date or date.min))
            else:
                fallback_pool.sort(key=lambda m: (m.last_prayer_date is not None, m.last_prayer_date or date.min))
            return fallback_pool[0]

    return None


def generate_schedule(
    members: Dict[int, Member],
    weeks: int = 12,
    start_date: Optional[date] = None,
    hc_week: int = 3
) -> List[ServiceSlot]:
    """指定週分のスケジュールを生成してServiceSlotのリストを返す（テスト・CLI共通コア）"""
    current = start_date or date.today()
    while current.weekday() != 6:
        current += timedelta(days=1)

    schedule: List[ServiceSlot] = []

    for _ in range(weeks):
        sunday_type, type_title = get_sunday_type(current, hc_week=hc_week)
        is_fast = (sunday_type == "fast")
        is_hc = (sunday_type == "high_council")

        slot = ServiceSlot(
            meeting_date=current,
            sunday_type=sunday_type,
            type_title=type_title,
            is_high_council_slot=is_hc
        )
        assigned_today: List[Member] = []

        # 1. お祈り (男女ペア選出)
        prayers = [m for m in members.values() if not m.is_bishopric]
        m_pool = [m for m in prayers if m.gender == "M"]
        f_pool = [m for m in prayers if m.gender == "F"]

        inv = select_best_candidate(m_pool, current, "prayer", assigned_today)
        if inv:
            slot.invocation = inv
            assigned_today.append(inv)
            inv.last_prayer_date = current
            inv.total_prayers += 1

        ben = select_best_candidate(f_pool, current, "prayer", assigned_today)
        if ben:
            slot.benediction = ben
            assigned_today.append(ben)
            ben.last_prayer_date = current
            ben.total_prayers += 1

        # 2. お話（断食証しの会でない場合）
        if not is_fast:
            # 青少年枠
            youths = [m for m in members.values() if m.category == "youth"]
            y = select_best_candidate(youths, current, "talk", assigned_today)
            if y:
                slot.youth_talk = y
                assigned_today.append(y)
                y.last_talk_date = current
                y.total_talks += 1

            # 成人枠1
            adults = [m for m in members.values() if m.category == "adult" and not m.is_bishopric and not m.is_high_councilor]
            sp1 = select_best_candidate(adults, current, "talk", assigned_today)
            if sp1:
                slot.adult_talk_1 = sp1
                assigned_today.append(sp1)
                sp1.last_talk_date = current
                sp1.total_talks += 1

            # 成人枠2（高等評議員週でない場合）
            if not is_hc and sp1:
                other_g = "F" if sp1.gender == "M" else "M"
                adults_sub = [m for m in adults if m.id != sp1.id]
                g_pref = [m for m in adults_sub if m.gender == other_g]
                pool2 = g_pref if g_pref else adults_sub

                sp2 = select_best_candidate(pool2, current, "talk", assigned_today)
                if sp2:
                    slot.adult_talk_2 = sp2
                    assigned_today.append(sp2)
                    sp2.last_talk_date = current
                    sp2.total_talks += 1

        schedule.append(slot)
        current += timedelta(days=7)

    return schedule


def cmd_plan(args):
    """指定週分のドラフトスケジュールを一括生成"""
    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else date.today()
    except ValueError:
        print("[エラー] 日付形式は YYYY-MM-DD です。")
        return

    print_mode_badge()
    members = load_members()
    hc_week = getattr(args, "hc_week", 3)
    slots = generate_schedule(members, weeks=args.weeks, start_date=start_date, hc_week=hc_week)

    print("\n" + "=" * 90)
    print(f"            聖餐会スケジュール ドラフト生成 ({args.weeks}週間)")
    print("=" * 90)
    print(f"{'日付':<12} | {'開会お祈り':<14} | {'青少年話':<12} | {'成人話1':<14} | {'成人話2':<14} | {'閉会お祈り':<14}")
    print("-" * 90)

    for slot in slots:
        d_str = slot.meeting_date.strftime("%Y-%m-%d")
        inv_str = slot.invocation.name if slot.invocation else "-"
        ben_str = slot.benediction.name if slot.benediction else "-"
        
        if slot.sunday_type == "fast":
            yt_str = "【証し会】"
            at1_str = "-"
            at2_str = "-"
        else:
            yt_str = slot.youth_talk.name if slot.youth_talk else "-"
            at1_str = slot.adult_talk_1.name if slot.adult_talk_1 else "-"
            at2_str = "【高等評議員】" if slot.is_high_council_slot else (slot.adult_talk_2.name if slot.adult_talk_2 else "-")

        print(f"{d_str:<12} | {inv_str:<14} | {yt_str:<12} | {at1_str:<14} | {at2_str:<14} | {ben_str:<14}")

    print("=" * 90 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="聖餐会（Sacrament Meeting）お話・お祈り 推薦＆スケジューリング CLI",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="実行コマンド")

    p_init = subparsers.add_parser("init", help="過去履歴の初期シードデータを生成")
    p_init.set_defaults(func=cmd_init)

    p_status = subparsers.add_parser("status", help="会員のお話ご無沙汰状況・履歴を表示")
    p_status.add_argument("--top", type=int, default=15, help="表示件数 (デフォルト: 15)")
    p_status.set_defaults(func=cmd_status)

    p_list = subparsers.add_parser("list", help="【会議用】成人男女・青少年別の縦長ご無沙汰リスト（印刷・Excel共有向け）")
    p_list.add_argument("--role", type=str, default="talk", choices=["talk", "prayer"], help="役割 (talk: お話, prayer: お祈り, デフォルト: talk)")
    p_list.add_argument("--category", type=str, default="all", choices=["all", "adult-m", "adult-f", "youth"], help="表示グループ (デフォルト: all)")
    p_list.add_argument("--top", type=int, default=0, help="各グループの表示件数 (0で全員表示, デフォルト: 0)")
    p_list.add_argument("--format", type=str, default="table", choices=["table", "tsv", "markdown"], help="出力フォーマット (table, tsv, markdown, デフォルト: table)")
    p_list.set_defaults(func=cmd_list)

    p_rec = subparsers.add_parser("recommend", help="特定の日曜日の候補者レコメンド（霊感で選ぶ用）")
    p_rec.add_argument("date", type=str, help="対象日 (YYYY-MM-DD)")
    p_rec.add_argument("--hc-week", type=int, default=3, choices=[0, 2, 3], help="高等評議員の訪問週 (2: 第2日曜, 3: 第3日曜, 0: 訪問なし, デフォルト: 3)")
    p_rec.set_defaults(func=cmd_recommend)

    p_rep = subparsers.add_parser("replace", help="断られた場合の次点候補を再検索")
    p_rep.add_argument("date", type=str, help="対象日 (YYYY-MM-DD)")
    p_rep.add_argument("--role", type=str, required=True, choices=["youth_talk", "adult_talk", "prayer"], help="役割")
    p_rep.add_argument("--exclude", type=str, required=True, help="断られた会員名（カンマ区切りで複数可）")
    p_rep.set_defaults(func=cmd_replace)

    p_plan = subparsers.add_parser("plan", help="向こうN週間のドラフトを一括生成")
    p_plan.add_argument("--start", type=str, default="", help="開始日 (YYYY-MM-DD, 省略時は直近の日曜)")
    p_plan.add_argument("--weeks", type=int, default=12, help="生成週数 (デフォルト: 12)")
    p_plan.add_argument("--hc-week", type=int, default=3, choices=[0, 2, 3], help="高等評議員の訪問週 (2: 第2日曜, 3: 第3日曜, 0: 訪問なし, デフォルト: 3)")
    p_plan.set_defaults(func=cmd_plan)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
