# 聖餐会（Sacrament Meeting）お話・お祈り 推薦＆スケジューラー CLI

末日聖徒イエス・キリスト教会のワード・支部における、聖餐会のお話（Talk）やお祈り（Prayer）の割り当て業務を支援するローカルCLIツールです。

「人間（ビショップリック）が祈りを通して霊感で選定する」プロセスを尊重しつつ、複雑な制約（インターバル、夫婦・家庭の事情、男女比、青少年の育成）を満たす**推薦候補の絞り込みとスケジュール作成**をアシストします。

---

## プライバシー保護と多層セキュリティ設計

本リポジトリは、**オープンソースとしてコードを公開しつつ、実際の会員データ（個人情報）を安全に運用できる多層防御設計**を採用しています。

1. **データとコードの完全分離**
   - `sample_data/`: 公開用の架空会員データ（40人）。Git管理されます。
   - `private/`: 実際のワードの会員名簿置き場。**.gitignore によりGit追跡から完全に除外**されます。
2. **自動切り替えロジック**
   - `private/members.csv` が存在すれば自動で **「本番モード」** として起動。
   - なければ `sample_data/` の架空データで **「サンプルモード」** として起動。
3. **Pre-commit Hook（手元の誤コミット阻止）**
   - 万が一 `private/` 配下のファイルを `git add` しても、コミットフックが検知してコミットを強制中断します。
4. **GitHub Actions（CIによる自動検査）**
   - pushやPR時に、リポジトリ内に機密ファイルが混入していないかを自動スキャンします。

---

## ディレクトリ構成

```text
sacrament/
├── sample_data/               # 【Git管理対象】公開用の架空サンプルデータ
│   ├── members.csv            # 40人の架空会員名簿
│   └── history.json           # 架空の過去登壇・お祈り実績ログ
│
├── private/                   # 【Git追跡完全除外 (.gitignore)】実データ置き場
│   ├── members.csv            # あなたのワードの実際の会員名簿 (手動配置)
│   ├── history.json           # 実際の登壇履歴ログ (スクリプトが自動追記)
│   └── schedule.json          # 確定した聖餐会スケジュール (スクリプトが自動追記)
│
├── .github/workflows/         # CIセキュリティ検査 & 自動テスト
│   └── security-check.yml
├── .git/hooks/                # ローカルPre-commit Hook (誤コミット防止)
├── sacrament.py               # メインCLIスクリプト
└── README.md                  # 本ドキュメント
```

---

## `private/` ディレクトリの仕組みと本番運用ガイド

### なぜ `private/` を使うのか？
教会の公式方針（*General Handbook* 38.8.31）により、会員の個人情報（氏名・家族構成・役職・配慮メモ等）を外部のパブリックなクラウドや第三者サービスに保存・送信することは禁止されています。

本ツールでは、**プログラムコード（GitHubで共有可能）** と **実際の個人情報（手元のPC限定）** を完全に分離することで、情報漏洩リスクをゼロにしています。

### 実際のワードデータで運用する手順

#### ステップ1: `private/` フォルダの確認・作成
リポジトリ直下に `private/` フォルダを作成します（初期状態で既に存在するか、なければ作成してください）。
```bash
mkdir private
```

#### ステップ2: 実データの配置 (`private/members.csv`)
`sample_data/members.csv` をコピーして `private/members.csv` を作成し、実際のワードの会員情報に書き換えます。
```bash
# Windows PowerShell
Copy-Item sample_data\members.csv private\members.csv

# Mac / Linux
cp sample_data/members.csv private/members.csv
```
※ Excelで `private/members.csv` を開いて直接編集・保存できます。

#### ステップ3: スクリプトの実行
設定ファイルの書き換えは不要です。`private/members.csv` を置くだけで、スクリプトが自動で実データモードに切り替わります。
```bash
python sacrament.py status
```
実行時にターミナル最上部に以下のバッジが表示されます：
```text
【本番モード】 private/ の実会員データを使用しています (.gitignore対象)
```

---

## 使い方

Python 3 がインストールされていれば、外部ライブラリ（`pip install`）なしで動作します。

### 1. サンプルモードで試す
`private/members.csv` がない状態では、自動的に架空の40人サンプルで動作します。

```bash
# 会員の「お話ご無沙汰ランキング」を表示
python sacrament.py status

# 特定の日曜日の候補者レコメンド（ビショップリック会議用）
python sacrament.py recommend 2026-10-11

# ドラフトスケジュールの自動生成（向こう8週分）
python sacrament.py plan --weeks 8
```

### 2. 打診して断られたときの「即座の差し替え」 (`replace`)
「加藤兄弟に打診したら、その日は都合が悪くて断られた」という場合に次点候補を再提示します。
```bash
python sacrament.py replace 2026-10-11 --role adult_talk --exclude "加藤 秀樹"
```

---

## CLIコマンド一覧

| コマンド | 引数 | 用途 |
| :--- | :--- | :--- |
| `status` | `--top N` | 会員の最終登壇日・経過日数ランキング一覧を表示 |
| `recommend` | `<YYYY-MM-DD>` | その日の各スロットの候補トップ3〜5を理由付きで推薦 |
| `replace` | `<YYYY-MM-DD> --role <ROLE> --exclude <名前>` | 断られた際の次点候補（Rank 2〜5）を即座に再提示 |
| `plan` | `--weeks N [--start YYYY-MM-DD]` | 指定週分のドラフトスケジュールを一括生成 |
| `init` | なし | 過去実績ログ（`history.json`）の初期ダミーデータを生成 |

---

## 会員データ（`members.csv`）の仕様

| カラム名 | 型 | 説明 |
| :--- | :--- | :--- |
| `id` | 数値 | 会員ID（一意の番号） |
| `name` | 文字列 | 氏名 |
| `gender` | M / F | 性別（男性: M, 女性: F） |
| `category` | adult / youth | 区分（成人: adult, 青少年: youth） |
| `household_id` | 数値 | 世帯ID（同じ家族・夫婦は同じ番号） |
| `is_bishopric` | True / False | ビショップリックフラグ（Trueなら通常枠から除外） |
| `couple_talk_together` | True / False | 夫婦登壇希望（Trueなら同じ週へのペアリング優先） |
| `has_small_children` | True / False | 乳幼児あり（Trueなら夫婦が同日に重なるのを回避） |
| `is_new_member` | True / False | 新会員（Trueならお祈り優先ボーナス） |

---

## 免責事項
* 本スクリプトは有志による個人開発プロジェクトであり、末日聖徒イエス・キリスト教会の公式ソフトウェアではありません。
* 会員データの取り扱いには十分注意し、個人PCのローカル環境内でのみ運用してください。
