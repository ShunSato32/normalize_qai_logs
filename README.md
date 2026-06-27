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
- 標準ライブラリのみで動作します（テスト実行には `pytest` が必要です）。

## セットアップ

仮想環境を作成し、必要なパッケージ（テスト用）をインストールします。
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
```

## 実行方法

```bash
python normalize_chatbot_logs.py INPUT_DIR OUTPUT_DIR [--anonymize-users] [--strict]
```

- `INPUT_DIR`: 生CSVファイルが格納されているディレクトリ。
- `OUTPUT_DIR`: 処理結果を出力するディレクトリ（存在しない場合は作成されます）。
- `--anonymize-users`: ユーザー名をハッシュ化して匿名化します。
- `--strict`: 1つでも読み込めないファイル（IRM保護など）があった場合に処理を中断します。

### 実行例
```bash
python normalize_chatbot_logs.py ../csv ./output_data
```

## 出力ファイル
実行後、`OUTPUT_DIR` に以下の11ファイルが生成されます（CSVはUTF-8 BOM付き）。

1. `raw_events.csv`: 全イベントの統合原本。
2. `interactions.csv`: `message_id`単位の正規化結果。
3. `retrieval_results.csv`: `similar_records` の展開結果。
4. `feedback.csv`: フィードバックイベントの抽出。
5. `reset_sessions.csv`: リセット区間ごとの集計。
6. `analytics_overview.csv`: 全体KPI。
7. `analytics_daily.csv`: 日別集計。
8. `analytics_category.csv`: カテゴリ別集計。
9. `analytics_session_distribution.csv`: セッション毎の自然質問数分布。
10. `data_dictionary.csv`: データ辞書。
11. `manifest.json`: 処理結果、警告、処理件数などのメタデータ。

## 自動テストの実行
```bash
python -m pytest tests/ -v
```

## 既知の制約
- サブディレクトリ内のCSVファイルは探索対象外です。
- 文字コードは `utf-8-sig`, `cp932`, `utf-8` の順でフォールバックして試行しますが、これら以外は読み飛ばされます。
- IRM/OLE保護されたファイルは復号せず読み飛ばします。
