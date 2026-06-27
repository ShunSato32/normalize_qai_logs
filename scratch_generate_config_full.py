import os
import sys
import json

# Add current dir to path
sys.path.append(os.path.abspath("."))
from excel_writer import HEADERS

print(f"Total headers: {len(HEADERS)}")

# Let's define descriptions for all headers.
# We will create a dictionary mapping physical names to descriptions.
descriptions = {
    # 15.1
    "output_row_id": "一意の行ID（interaction_id と feedback_seq を結合）",
    "No.": "エクセル上の通し番号（行数に基づく数式）",
    "interaction_id": "message_id と conversation_id の衝突を避けるための対話一意キー（conversation_id::message_id）",
    "message_id": "ユーザーの1回の問い合せ処理に対応するメッセージID（生ログ由来）",
    "conversation_id": "一連の会話セッションを表す会話ID",
    "reset_session_id": "会話リセット判定で区切られたリセットセッションID",
    "reset_session_no": "会話内でリセットが実行された順番を表すセッション番号（1から開始）",
    "interaction_no_in_session": "各セッション内で実行された何番目の対話かを表す連番（1から開始）",
    "is_first_interaction_row": "1つの対話（interaction）に対して複数行出力される場合、最初の行かどうかを示すフラグ（1:最初, 0:その他）",
    # 15.2
    "質問投入者": "質問を投稿したユーザー名（匿名化オプションが有効な場合はハッシュ値化）",
    "team_name": "会話が属するチーム名または会話場所の識別名",
    "質問内容": "ユーザーが入力した質問の本文（自然言語クエリのみ、コマンド等は除外）",
    "user_content_raw": "ユーザーが投稿した生のコンテンツ（[カテゴリ選択]やリセット指示等を含む）",
    "is_natural_language_query": "ユーザーの入力が自然言語での質問かどうかを示すフラグ（1:はい, 0:いいえ）",
    "is_reset_request": "ユーザーの入力が「リセット」指示かどうかを示すフラグ（1:はい, 0:いいえ）",
    "is_category_selection": "ユーザーの入力がカテゴリ選択のアクションかどうかを示すフラグ（1:はい, 0:いいえ）",
    "is_system_command": "ユーザーの入力がシステムコマンド（スラッシュコマンド等）かどうかを示すフラグ（1:はい, 0:いいえ）",
    # 15.3
    "started_at_utc": "対話の開始日時（UTC）",
    "completed_at_utc": "対話の完了日時（UTC）",
    "started_at_jst": "対話の開始日時（JST、日本標準時）",
    "completed_at_jst": "対話の完了日時（JST、日本標準時）",
    "latency_sec": "処理時間（秒単位、完了日時 - 開始日時）",
    # 15.4
    "selected_function": "システムによって選択された処理機能名",
    "predicted_category": "AI/システムによって予測されたカテゴリ",
    "user_selected_category": "ユーザー自身が選択したカテゴリ",
    "第一カテゴリ": "予測カテゴリの最上位階層（最初のレベル）",
    "final_category": "最終決定されたカテゴリ（ユーザー選択優先、予測フォールバック、または未分類）",
    "category_source": "最終カテゴリの決定基準（user_selected, predicted, none）",
    "is_unclassified": "最終カテゴリが「未分類」かどうかを示すフラグ（1:未分類, 0:分類済）",
    # 15.5
    "回答内容": "システムまたはAIから返却された回答文",
    "has_answer": "回答が正常に生成されたかどうか（true / false）",
    "is_no_answer": "回答が見つからなかった（「回答なし」等）かどうかを示すフラグ（1:はい, 0:いいえ）",
    "assistant_event_count": "この対話に含まれるアシスタントのイベント数",
    "has_error": "エラーイベントが発生したかどうかを示すフラグ（true / false）",
    "error_count": "発生したエラーイベントの数",
    "error_message": "発生したエラーメッセージの内容",
    # 15.6
    "retrieval_count": "検索処理でヒットした検索結果の総件数",
    "retrieval_stored_count": "このエクセル行に格納されている検索結果の件数（最大10件）",
    "retrieval_truncated": "ヒットした検索結果が上限10件を超えて切り捨てられたかどうかを示すフラグ（1:切り捨てあり, 0:なし）",
    # 15.8
    "feedback_id": "フィードバック情報の一意ID（対話キー + 連番）",
    "feedback_seq": "この対話に紐づくフィードバックの連番。評価がない場合は0",
    "feedback_count": "この対話に紐づくフィードバックの総件数",
    "回答評価": "ユーザーからの回答に対する評価（good, bad 等）",
    "評価理由": "ユーザーが入力した評価に対するコメントや理由",
    "feedback_at_utc": "評価日時（UTC）",
    "feedback_at_jst": "評価日時（JST、日本標準時）",
    "is_latest_feedback": "このフィードバックが最新の評価かどうかを示すフラグ（1:最新, 0:過去）",
    # 15.9
    "session_ends_with_reset": "このセッションの最後の対話が「リセット」要求で終了したかどうかを示すフラグ（1:はい, 0:いいえ）",
    "source_files": "対話の構成元となったソースCSVファイル名の一覧",
    "source_event_row_count": "対話の処理に含まれる生のイベント件数",
    "source_event_types": "対話に含まれる生イベントのタイプシーケンス（例：user > assistant > tool > assistant）",
    "normalization_version": "ログ正規化処理で使用したツールのバージョン",
    "normalization_warnings": "データパースや整合性チェックで発生した警告メッセージのリスト",
    "質問/回答\n分類": "ビジネス分析・評価用の「質問/回答分類」列（手動分析用空欄）",
    "対象/\n対象外": "分析対象（〇）または対象外（×）を自動判定する数式列",
    "教師データ有無": "教師データの有無（手動分析用空欄）",
    "キーワード1": "分析用キーワード1（手動分析用空欄）",
    "キーワード2": "分析用キーワード2（手動分析用空欄）",
    "キーワード3": "分析用キーワード3（手動分析用空欄）",
    "Hit判定": "検索結果内にキーワードが含まれていたかの判定（数式による自動判定）",
    "回答判定": "回答内容の判定結果（手動分析用空欄）",
    "正答判定": "回答が正しかったかどうかの判定（手動分析用空欄）",
    "分析コメント": "分析者によるコメント欄（手動分析用空欄）",
    "原因": "エラーや誤回答の原因分類（手動分析用空欄）",
    "対応方針": "今後の対応・改善方針（手動分析用空欄）",
    "対応進捗": "改善タスクの対応進捗（手動分析用空欄）",
    "Vantiq相談": "システム開発元への相談要否（手動分析用空欄）",
    "日付": "対話が発生した日付（JST、yyyy/mm/dd 形式の数式）",
    "所属": "社員マスタをキーとした質問投入者の所属組織名（VLOOKUP数式による自動補完）",
    "messageID": "生ログ由来のmessage_id（エクセル書式保存用）"
}

# Add dynamic retrieval and evaluation check column descriptions
for k in range(1, 11):
    circle = "①②➂④⑤⑥⑦⑧➈➉"[k-1]
    descriptions[f"参照文書{circle}"] = f"第{k}順位でヒットした検索結果の参照ファイル名"
    descriptions[f"参考箇所{circle}"] = f"第{k}順位でヒットした検索結果のテキスト抜粋"
    # score circling character could be different
    circle_score = "①②③④⑤⑥⑦⑧➈➉"[k-1]
    descriptions[f"score{circle_score}"] = f"第{k}順位でヒットした検索結果の類似度スコア"
    descriptions[f"参照箇所{circle}"] = f"第{k}順位の参照箇所に特定のキーワードが含まれているかの自動判定フラグ（数式による判定）"

config_list = []
for idx, h in enumerate(HEADERS, start=1):
    desc = descriptions.get(h, "分析用カスタム列または数式列")
    config_list.append({
        "physical_name": h,
        "japanese_name": h.replace("\n", " "),
        "description": desc,
        "sort_order": idx
    })

print(f"Generated config entries: {len(config_list)}")
with open("column_config.json", "w", encoding="utf-8") as f:
    json.dump(config_list, f, indent=2, ensure_ascii=False)
print("Saved column_config.json")
