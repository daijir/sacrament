# 聖餐会（Sacrament Meeting）お話・お祈り 推薦＆スケジューラー CLI

末日聖徒イエス・キリスト教会のワード・支部における、聖餐会のお話（Talk）やお祈り（Prayer）の割り当て業務を支援するローカルCLIツールです。

「人間（ビショップリック）が祈りを通して霊感で選定する」プロセスを尊重しつつ、複雑な制約（インターバル、夫婦・家庭の事情、男女比、青少年の育成）を満たす**推薦候補の絞り込みとスケジュール作成**をアシストします。

---

## 🔒 プライバシー保護と多層セキュリティ設計

本リポジトリは、**オープンソースとしてコードを公開しつつ、実際の会員データ（個人情報）を安全に運用できる多層防御設計**を採用しています。

1. **データとコードの完全分離**
   * sample_data/: 公開用の架空会員データ（40人）。Git管理されます。
   * private/: 実際のワードの会員名簿置き場。**.gitignore によりGit追跡から完全に除外**されます。
2. **自動切り替えロジック**
   * private/members.csv が存在すれば自動で **「本番モード」** として起動。
   * なければ sample_data/ の架空データで **「サンプルモード」** として起動。
3. **Pre-commit Hook（手元の誤コミット阻止）**
   * 万が一 private/ 配下のファイルを git add しても、コミットフックが検知してコミットを強制中断します。
4. **GitHub Actions（CIによる自動検査）**
   * pushやPR時に、リポジトリ内に機密ファイルが混入していないかを自動スキャンします。

---

## 📁 ディレクトリ構成

`	ext
sacrament/
├── sample_data/               # 【Git管理】架空の公開サンプルデータ
│   ├── members.csv            # 40人の架空データ
│   └── history.json           # 架空の過去実績
│
├── private/                   # 【.gitignore対象】本物の個人情報置き場
│   ├── members.csv            # 実際のワード名簿 (手動配置)
│   └── history.json           # 実際の過去実績ログ (自動記録)
│
├── .github/workflows/         # CIセキュリティ検査 & 自動テスト
├── sacrament.py               # メインCLIスクリプト
└── README.md                  # 本ドキュメント
`

---

## 🚀 使い方

Python 3 がインストールされていれば、追加ライブラリのインストール（pip install）なしで動作します。

### 1. サンプルモードで試す
リポジトリをクローンしてそのまま実行すると、架空の会員40名データで動作します。
`ash
# 状況確認（ご無沙汰ランキング）
python sacrament.py status

# 特定の日の推薦候補を見る
python sacrament.py recommend 2026-10-11

# ドラフトスケジュール作成
python sacrament.py plan --weeks 8
`

### 2. 実際のワードデータで運用する（本番モード）
1. private/ フォルダを作成します。
2. private/members.csv に実際の会員名簿を配置します。
3. スクリプトを実行すると、自動的に 🔒 【本番モード】 と表示され、実データで計算されます。

`ash
# 本番の初期履歴シード（または空の状態でスタート）
python sacrament.py init
`

---

## 🛠️ CLIコマンド一覧

| コマンド | 用途 |
| :--- | :--- |
| python sacrament.py status | 会員の最終登壇日・経過日数ランキング一覧 |
| python sacrament.py recommend <YYYY-MM-DD> | その日の各スロットの候補トップ3〜5を理由付きで推薦 |
| python sacrament.py replace <YYYY-MM-DD> --role <ROLE> --exclude <名前> | 打診して断られた際の次点候補を即座に再提示 |
| python sacrament.py plan --weeks <週数> | 指定週分のドラフトスケジュールを一括生成 |

---

## 📊 会員データ（members.csv）の仕様

Excelやテキストエディタで直接メンテナンスできます。

| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| id | 数値 | 会員ID（一意の番号） |
| 
ame | 文字列 | 氏名 |
| gender | M / F | 性別（男性: M, 女性: F） |
| category | adult / youth | 区分（成人: adult, 青少年: youth） |
| household_id | 数値 | 世帯ID（同じ家族・夫婦は同じ番号） |
| is_bishopric | True / False | ビショップリックフラグ（Trueなら通常枠から除外） |
| couple_talk_together | True / False | 夫婦登壇希望（Trueなら同じ週へのペアリング優先） |
| has_small_children | True / False | 乳幼児あり（Trueなら夫婦が同日に重なるのを回避） |
| is_new_member | True / False | 新会員（Trueならお祈り優先ボーナス） |

---

## 📜 免責事項
* 本スクリプトは有志による個人開発プロジェクトであり、末日聖徒イエス・キリスト教会の公式ソフトウェアではありません。
* 会員データの取り扱いには十分注意し、個人PCのローカル環境内でのみ運用してください。
