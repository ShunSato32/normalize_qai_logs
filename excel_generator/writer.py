import csv
import json
import os
from typing import List, Dict, Any
from dataclasses import asdict

from core import RawEvent, Interaction, ResetSession, Manifest, bool_to_str

def write_csv(filepath: str, data: List[Dict[str, Any]], fieldnames: List[str]):
    # Note: Using utf-8-sig for Excel compatibility as per the note in the plan
    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

def write_raw_events(output_dir: str, events: List[RawEvent]):
    fieldnames = [
        "global_event_no", "event_id", "source_file", "source_row_number",
        "team_name", "conversation_id", "message_type", "content",
        "user_name", "category", "similar_records", "feedback_rating",
        "feedback_comment", "created_at_str", "created_at_utc", "created_at_jst",
        "event_date_jst", "event_time_jst", "message_id", "interaction_key",
        "reset_session_id", "user_key"
    ]
    
    data = []
    for e in events:
        d = asdict(e)
        d["created_at_utc"] = e.created_at_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00') if e.created_at_utc else ""
        d["created_at_jst"] = e.created_at_jst.strftime('%Y-%m-%dT%H:%M:%S+09:00') if e.created_at_jst else ""
        data.append(d)
        
    write_csv(os.path.join(output_dir, "raw_events.csv"), data, fieldnames)

def write_interactions(output_dir: str, interactions: List[Interaction]):
    fieldnames = [
        "interaction_key", "message_id", "conversation_id", "team_name", "user_name", "user_key",
        "interaction_type", "question", "all_user_messages_json", "answer", "answer_message_type",
        "selected_function", "inferred_category", "user_selected_categories", "final_category",
        "event_sequence", "event_count", "has_tool", "retrieval_count", "top_score",
        "similar_records_parse_failures", "has_error", "error_text", "has_feedback",
        "feedback_rating", "feedback_comment", "is_reset_request", "is_category_selection",
        "is_command", "is_natural_question", "is_no_answer", "is_unsupported",
        "started_at_utc", "ended_at_utc", "started_at_jst", "ended_at_jst", "interaction_date_jst",
        "response_latency_seconds", "source_files", "reset_session_no", "reset_session_id",
        "interaction_no_in_session", "ends_session_by_reset"
    ]
    
    data = []
    for i in interactions:
        d = asdict(i)
        # Convert booleans to "true"/"false" string
        for k in ["has_tool", "has_error", "has_feedback", "is_reset_request", 
                  "is_category_selection", "is_command", "is_natural_question", 
                  "is_no_answer", "is_unsupported", "ends_session_by_reset"]:
            d[k] = bool_to_str(d[k])
            
        del d["events"] # Remove list of RawEvent
        data.append(d)
        
    write_csv(os.path.join(output_dir, "interactions.csv"), data, fieldnames)

def write_reset_sessions(output_dir: str, sessions: List[ResetSession]):
    fieldnames = [
        "reset_session_id", "conversation_id", "reset_session_no", "team_name",
        "user_name", "user_key", "started_at_utc", "ended_at_utc", "started_at_jst",
        "ended_at_jst", "session_date_jst", "duration_seconds", "interaction_count",
        "natural_question_count", "category_selection_count", "command_count",
        "reset_request_count", "ended_by_reset", "tool_interaction_count",
        "no_answer_count", "unsupported_count", "error_count", "feedback_count",
        "good_feedback_count", "bad_feedback_count", "first_question", "last_question",
        "first_category", "last_category", "source_files"
    ]
    
    data = []
    for s in sessions:
        d = asdict(s)
        d["ended_by_reset"] = bool_to_str(d["ended_by_reset"])
        data.append(d)
        
    write_csv(os.path.join(output_dir, "reset_sessions.csv"), data, fieldnames)

def write_retrieval_results(output_dir: str, results: List[Dict[str, Any]]):
    if not results:
        fieldnames = [
            "interaction_key", "message_id", "conversation_id", "reset_session_id",
            "tool_event_id", "rank_in_tool_event", "score", "retrieved_content",
            "filename", "display_name", "filetype", "metadata_categories",
            "category_depth", "is_qa", "can_open", "uploaded_at", "metadata_id",
            "collection_name", "source_file"
        ]
    else:
        fieldnames = list(results[0].keys())
        
    write_csv(os.path.join(output_dir, "retrieval_results.csv"), results, fieldnames)

def write_feedback(output_dir: str, feedback: List[Dict[str, str]]):
    fieldnames = [
        "event_id", "interaction_key", "message_id", "conversation_id", "reset_session_id",
        "user_name", "user_key", "feedback_rating", "feedback_comment", "feedback_at_utc",
        "feedback_at_jst", "source_file"
    ]
    write_csv(os.path.join(output_dir, "feedback.csv"), feedback, fieldnames)

def write_analytics(output_dir: str, overview: List[Dict], daily: List[Dict], category: List[Dict], dist: List[Dict]):
    if daily:
        write_csv(os.path.join(output_dir, "analytics_daily.csv"), daily, list(daily[0].keys()))
    else:
        write_csv(os.path.join(output_dir, "analytics_daily.csv"), [], [])
        
    if category:
        write_csv(os.path.join(output_dir, "analytics_category.csv"), category, list(category[0].keys()))
    else:
        write_csv(os.path.join(output_dir, "analytics_category.csv"), [], [])

def write_integrated(output_dir: str, rows: List[Dict[str, Any]]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    write_csv(os.path.join(output_dir, "integrated.csv"), rows, fieldnames)

def write_manifest(output_dir: str, manifest: Manifest):
    filepath = os.path.join(output_dir, "manifest.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(manifest.to_dict(), f, indent=2, ensure_ascii=False)
        
def write_data_dictionary(output_dir: str):
    # This just generates a simple documentation file
    content = """# Data Dictionary

| テーブル | 粒度 | 論理キー | 説明 |
|---|---|---|---|
| `raw_events` | 入力CSVの1行 | `event_id` | 入力データの統合原本 |
| `interactions` | 1問い合わせ処理 | `interaction_key` | message_idでグループ化した質問回答単位 |
| `retrieval_results` | 検索結果1件 | `interaction_key` + `tool_event_id` + `rank_in_tool_event` | similar_recordsの展開結果 |
| `feedback` | feedbackイベント1件 | `event_id` | ユーザーからの評価 |
| `reset_sessions` | リセットで区切った区間 | `reset_session_id` | リセット要求を境界としたセッション |
| `integrated` | interaction × feedbackの交差行 | `output_row_id` | 問い合わせ、評価、検索結果、セッションを結合した統合データ |
"""
    with open(os.path.join(output_dir, "data_dictionary.csv"), "w", encoding='utf-8-sig') as f:
        f.write("table,granularity,logical_key,description\n")
        f.write("raw_events,入力CSVの1行,event_id,入力データの統合原本\n")
        f.write("interactions,1問い合わせ処理,interaction_key,message_idでグループ化した質問回答単位\n")
        f.write("retrieval_results,検索結果1件,interaction_key + tool_event_id + rank_in_tool_event,similar_recordsの展開結果\n")
        f.write("feedback,feedbackイベント1件,event_id,ユーザーからの評価\n")
        f.write("reset_sessions,リセットで区切った区間,reset_session_id,リセット要求を境界としたセッション\n")
        f.write("integrated,interaction × feedbackの交差行,output_row_id,問い合わせ・評価・検索結果・セッションを結合した統合データ\n")

