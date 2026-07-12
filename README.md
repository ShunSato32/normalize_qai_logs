# YourNavi-QAI Logs Normalization Tool

YourNavi-QAIの生イベントログ（CSV）を読み込み、以下の4層へ正規化・セッション化するバッチツールです。

1. `raw_events`: 生ログの縦結合と日時等の補助列付与
2. `interactions`: `message_id` 単位でのやり取りの集約
3. `reset_sessions`: 「リセット」要求を境界としたセッションの分割
4. `analytics`: 各種KPI集計

## 特徴と仕様
- **厳密なセッション化**: 時間間隔や日付変更ではセッションを分割せず、ユーザーの完全一致「リセット」要求でのみセッションを区切ります。リセット要求自体は直前のセッションの終了イベントとして扱われます。
- **安全なパース処理**: `similar_records` は `ast.literal_eval` および `json.loads` で安全に展開し、任意コード実行リスクを排除しています。
- **堅牢なエラーハンドリング**: パースエラー、欠損フィールド、メッセージIDの衝突などは `manifest.json` に記録され、処理は可能な限り継続されます。

## 動作環境
- Python 3.9 以上
- 外部ライブラリとして Excel出力用に **`openpyxl`** が必要です（それ以外の機能はすべてPython標準ライブラリで動作します）。

## セットアップ

### A. 仮想環境を使用せずにご自身のPCのPythonで直接実行する場合（お手軽）
コマンドプロンプトまたはターミナルで一度だけ以下を実行し、`openpyxl` をインストールします。
```bash
pip install openpyxl
```

### B. 仮想環境 (`.venv`) を作成して実行する場合
仮想環境は独立した新しい空のPython環境となるため、仮想環境を有効化した後、その中に `openpyxl`（およびテストを行う場合は `pytest`）をインストールします。
```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsの場合は: .venv\Scripts\activate
pip install openpyxl pytest
```

## 実行方法

```bash
python normalize_chatbot_logs.py [INPUT_DIR] [OUTPUT_DIR] [--anonymize-users] [--strict]
```

- `INPUT_DIR`: 生CSVファイルが格納されているディレクトリ（省略時はデフォルトで `input_csv` を参照します）。
- `OUTPUT_DIR`: 処理結果を出力するディレクトリ（省略時はデフォルトで `output_run` に出力されます。存在しない場合は作成されます）。
- `--anonymize-users`: ユーザー名をハッシュ化して匿名化します。
- `--strict`: 1つでも読み込めないファイル（IRM保護など）があった場合に処理を中断します。

### 実行例
```bash
# デフォルト（input_csv から読み込んで output_run へ出力）
python normalize_chatbot_logs.py

# 明示的にディレクトリを指定する場合
python normalize_chatbot_logs.py ./input_csv ./output_run
```

## 出力ファイル
実行後、`OUTPUT_DIR` に以下のファイルおよびExcelシートが生成されます（CSVはUTF-8 BOM付き）。

1. `analytics_daily.csv`: 日別集計。
2. `analytics_category.csv`: カテゴリ別集計。
3. `manifest.json`: 処理結果、警告、処理件数などのメタデータ。
4. `【生成AI】実施記録分析シート_統合版_202xxxxxxx.xlsx`: 統合版の分析・統計エクセルシート。

## 設定ファイル (`config/`)
各種カスタマイズは `config/` ディレクトリ配下のJSONファイルを編集することで行います。

- **`config/column_config.json`**: Excel出力時の列の順番、ヘッダー表示名（物理名・日本語名）およびスタイル動的制御を定義します。
- **`config/system_commands.json`**: チャットボットへのコマンド発話判定（`system_commands`）、回答なし判定フレーズ（`no_answer_phrases`）、非対応判定フレーズ（`unsupported_phrases`）のリストを管理します。

## 自動テストの実行
```bash
python -m pytest tests/ -v
```

## 既知の制約
- サブディレクトリ内のCSVファイルは探索対象外です。
- 文字コードは `utf-8-sig`, `cp932`, `utf-8` の順でフォールバックして試行しますが、これら以外は読み飛ばされます。
- IRM/OLE保護されたファイルは復号せず読み飛ばします。
