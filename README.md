# YourNavi-QAI End-to-End Analytics & Normalization Tool

YourNavi-QAIの生ログ（CSV）を S3 から自動取得し、厳密なルールに基づいて正規化・セッション化を行い、エクセル分析シートを自動生成するエンドツーエンド（End-to-End）自動化パイプラインツールです。

---

## 1. 全体ディレクトリ構成とツールの役割分離

本ツールはメンテナンス性と運用性を高めるため、**「① S3自動取得ツール (`s3_fetcher`)」** と **「② エクセル正規化・生成ツール (`excel_generator`)」** にフォルダとプログラムを完全に分離して格納しています。また、それらをワンアクションで回す統合パイプライン (`run_pipeline.py`) を備えています。

```text
normalize_qai_logs/
│
├── run_pipeline.py            <--- 【統合パイプライン】S3取得〜エクセルシート生成を一連実行する自動化ランナー
│
├── s3_fetcher/                <--- 【① S3自動取得ツール】
│   ├── s3_config.json         <--- AWS S3バケット名・パス・アーカイブ設定
│   ├── s3_utils.py            <--- AWS CLIコマンド実行・検証ラッパー
│   └── fetch_csv.py           <--- CSV自動ダウンロード＆S3アーカイブフォルダへの自動移動実行スクリプト
│
├── excel_generator/           <--- 【② エクセル正規化・生成ツール】
│   ├── normalize_chatbot_logs.py <--- エクセル化処理のメイン実行ファイル
│   ├── excel_writer.py        <--- エクセル書込みおよび動的書式・計算ロジック
│   ├── integrated.py          <--- 対話集約およびQA分類・指標算出ロジック
│   ├── normalizer.py          <--- イベント正規化および類似検索データ抽出
│   ├── sessionizer.py         <--- セッション分割処理
│   ├── analytics.py           <--- KPI集計処理
│   └── templates/             <--- テンプレートExcel（【社名】実施記録分析シート.xlsx）
│
├── config/                    <--- 設定ファイルフォルダ（カテゴリ定義や列設定など）
├── input_csv/                 <--- S3からダウンロードされたCSVファイルの格納先（エクセル化インプット）
└── output_run/                <--- 生成された分析エクセルシートおよびCSVの保存先
```

---

## 2. 動作環境・セットアップ

### 必須要件
- **Python 3.9 以上**
- **openpyxl**: Excelファイルの読み書きおよび書式設定に必須。
- **AWS CLI (v2推奨)**: S3自動取得機能 (`s3_fetcher`) を利用する場合のみインストール・初期設定(`aws configure`)が必要です。

### セットアップ手順（初回のみ）
コマンドプロンプトまたはターミナルを開き、以下を実行して `openpyxl` をインストールします。

```bash
# 直接インストールする場合
pip install openpyxl

# または仮想環境 (.venv) を作成してインストールする場合
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install openpyxl
```
*(※ 共有先の運用PCなどでツールを実行するのみの場合は、開発用の `tests/` フォルダ等は共有・構成不要です)*

---

## 3. 実行方法・使い方

### A. ワンクリック統合実行（推奨）
S3からの新しいログCSVの自動ダウンロード → S3上でのアーカイブ移動 → ローカルでのエクセルシート自動生成までを自動で一気通貫実行します。

```bash
python run_pipeline.py
```

### B. 各ステップの個別実行・分割実行

#### S3からのCSV取得・移動のみを実行する場合
```bash
python run_pipeline.py --skip-excel
# または直接スクリプトを実行:
python s3_fetcher/fetch_csv.py
```

#### ローカル (input_csv/) のCSVファイルのエクセル化のみを実行する場合
```bash
python run_pipeline.py --skip-fetch
# または直接スクリプトを実行:
python excel_generator/normalize_chatbot_logs.py
```

※ 入力ディレクトリや出力ディレクトリを明示的に指定してエクセル化を実行したい場合は以下のように指定可能です：
```bash
python excel_generator/normalize_chatbot_logs.py ./input_csv ./output_run --strict
```

---

## 4. S3自動取得ツール (`s3_fetcher`) の仕様と設定

`s3_fetcher/s3_config.json` を編集することで、バケット名やパス設定をノーコードで変更できます。

```json
{
  "aws_profile": "default",
  "aws_region": "ap-northeast-1",
  "s3": {
    "bucket_name": "your-company-qai-logs-bucket",
    "source_prefix": "exports/daily_logs/",
    "archive_folder_name": "archive/",
    "file_extension_filter": ".csv"
  },
  "local": {
    "download_destination_dir": "../input_csv",
    "clear_destination_before_download": false
  },
  "archive_behavior": {
    "append_timestamp_on_archive": true,
    "archive_timestamp_format": "_%Y%m%d_%H%M%S"
  }
}
```

- **二重取り込み防止（アーカイブ移動）**: ダウンロードしたファイルは、破損や空ファイルでないことを正常検証した**直後にのみ**、S3上の `archive/` フォルダへ自動移動 (`aws s3 mv`) されます。
- **ファイル保護**: 万が一ダウンロード中にエラーや通信切断が発生した場合は、S3上の元ファイルの移動を自動停止し、データの消失を防ぎます。
- **再実行時の除外**: S3上のパスに `archive/` が含まれるファイルは、一覧取得時に自動でスキップされます。

---

## 5. エクセル正規化・集計ロジックの厳密な定義

本ツールの出力する分析エクセルシート (`【社名】実施記録分析シート_統合版_*.xlsx`) は、統計母数に1ミリのズレも生じないよう、厳密な判定および合計一致ロジックを採用しています。

### 投入質問（件）の算出と 100% 完全整合性
ユーザーからの「自然言語での質問」をカウントし、ボタン操作・リセット依頼・追加フィードバック（2回目以降の評価行）を除外した「各対話の最初の行 (`is_first_interaction_row = 1`)」のうち、システムコマンドなどの「④集計対象外」を除外した件数を **B列「投入質問（件）」** として計上します。

これに基づき、全日別行において以下の4大指標の合計値が **100%完全一致** するように設計されています：

$$\mathbf{B列\text{（投入質問数）}} \ = \ \mathbf{D+E列\text{（分類の内訳）}} \ = \ \mathbf{K列\text{（評価の内訳）}} \ = \ \mathbf{O+P+Q列\text{（カテゴリ第1階層の合計）}}$$

- **分類の内訳 (`D+E列`)**: 「①該当無」と「⑤その他」の和
- **評価の内訳 (`K列`)**: 「bad」＋「good」＋「未設定 (`unset`)」の和
- **カテゴリ第1階層の合計 (`O+P+Q列`)**: 構造化JSON定義に基づいた「未分類」＋「システム操作」＋「制度・運用」の和

---

## 6. 設定ファイル (`config/`) の解説

- **`config/target_categories.json`**: カテゴリ階層ツリーおよびエクセルシートの「集計詳細」「集計概要」のヘッダー名と数式を自動定義します。
- **`config/column_config.json`**: 実施記録シートにおける列の並び順や物理名/日本語名変換、文字の折り返しなどのスタイル定義を行います。
- **`config/system_commands.json`**: 「④集計対象外」と判定するコマンド発話リストや、「①該当無」と判定するシステム回答フレーズの辞書を管理します。
