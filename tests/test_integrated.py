import pytest
import json
from datetime import datetime, timezone
from core import RawEvent, Manifest
from normalizer import normalize_events
from sessionizer import sessionize
from integrated import build_integrated_rows

def test_integrated_no_feedback():
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "assistant", "A", "Bot", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}-{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    rows = build_integrated_rows(interactions, sessions, manifest)
    
    assert len(rows) == 1
    row = rows[0]
    assert row["unique_row_id"] == "c1-m1-FB000"
    assert row["interaction_id"] == "c1-m1"
    assert row["feedback_seq"] == 0
    assert row["is_first_interaction_row"] == 1
    assert row["feedback_rating"] == ""
    assert row["feedback_comment"] == ""
    assert row["feedback_at_utc"] == ""
    assert row["feedback_at_jst"] == ""
    assert row["has_retrieval"] == "false"
    assert row["retrieval_count"] == 0

def test_integrated_multiple_feedbacks():
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "assistant", "A", "Bot", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
        # Second feedback is sorted by timestamp (or row number)
        RawEvent("DM", "c1", "feedback", "", "User", "", "", "bad", "comment2", "2026-05-18T10:00:05Z", "m1"),
        RawEvent("DM", "c1", "feedback", "", "User", "", "", "good", "comment1", "2026-05-18T10:00:03Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}-{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    rows = build_integrated_rows(interactions, sessions, manifest)
    
    assert len(rows) == 2
    
    # First row is good (10:00:03Z)
    row1 = rows[0]
    assert row1["unique_row_id"] == "c1-m1-FB001"
    assert row1["feedback_seq"] == 1
    assert row1["is_first_interaction_row"] == 1
    assert row1["feedback_rating"] == "good"
    assert row1["feedback_comment"] == "comment1"
    assert row1["feedback_at_utc"] == "2026-05-18T10:00:03+00:00"
    
    # Second row is bad (10:00:05Z)
    row2 = rows[1]
    assert row2["unique_row_id"] == "c1-m1-FB002"
    assert row2["feedback_seq"] == 2
    assert row2["is_first_interaction_row"] == 0
    assert row2["feedback_rating"] == "bad"
    assert row2["feedback_comment"] == "comment2"
    assert row2["feedback_at_utc"] == "2026-05-18T10:00:05+00:00"
    
    # For subsequent rows, base interaction details are cleared, and question is set to [追加評価]
    assert row1["user_content_raw"] == "Q"
    assert row2["user_content_raw"] == ""
    assert row1["question"] == "Q"
    assert row2["question"] == "[追加評価]"
    assert row1["answer"] == "A"
    assert row2["answer"] == ""
    assert row1["reset_session_id"] == row2["reset_session_id"]

def test_integrated_retrieval_truncation():
    # Build a list of 12 retrieval results
    records = []
    for r in range(12):
        records.append({
            "score": 0.9 - (r * 0.05),
            "content": f"content {r}",
            "metadata": {
                "filename": f"file_{r}.md",
                "categories": ["cat", f"sub_{r}"]
            }
        })
    similar_records_str = json.dumps(records)
    
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "tool", "", "Bot", "", similar_records_str, "", "", "2026-05-18T10:00:01Z", "m1"),
        RawEvent("DM", "c1", "assistant", "A", "Bot", "", "", "", "", "2026-05-18T10:00:02Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}-{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    rows = build_integrated_rows(interactions, sessions, manifest)
    
    assert len(rows) == 1
    row = rows[0]
    
    assert row["has_retrieval"] == "true"
    assert row["retrieval_count"] == 12
    assert row["retrieval_stored_count"] == 10
    assert row["retrieval_truncated"] == 1
    assert row["top_retrieval_score"] == "0.9"
    assert row["top_retrieval_filename"] == "file_0.md"
    assert "similar_records truncated to 10" in row["normalization_warnings"]
    
    # Test column contents
    retrieval_01_parsed = json.loads(row["retrieval_01"])
    assert retrieval_01_parsed["rank"] == 1
    assert retrieval_01_parsed["filename"] == "file_0.md"
    assert retrieval_01_parsed["categories"] == ["cat", "sub_0"]
    
    retrieval_10_parsed = json.loads(row["retrieval_10"])
    assert retrieval_10_parsed["rank"] == 10
    assert retrieval_10_parsed["filename"] == "file_9.md"
    
    # retrieval_11 should not exist in column names (columns end at 10)
    assert "retrieval_11" not in row
    assert row["retrieval_10"] != ""

def test_integrated_classification_rules():
    from core import RawEvent, Manifest
    from normalizer import normalize_events
    from sessionizer import sessionize
    from integrated import build_integrated_rows
    from datetime import datetime, timezone
    
    events = [
        # 1. System command
        RawEvent("DM", "c1", "user", "[カテゴリ選択]", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        # 2. No answer
        RawEvent("DM", "c1", "user", "Q2", "User", "", "", "", "", "2026-05-18T10:01:00Z", "m2"),
        RawEvent("DM", "c1", "assistant", "ご質問の内容に関する情報が見つかりませんでした", "Bot", "", "", "", "", "2026-05-18T10:01:01Z", "m2"),
        # 3. Standard question
        RawEvent("DM", "c1", "user", "Q3", "User", "", "", "", "", "2026-05-18T10:02:00Z", "m3"),
        RawEvent("DM", "c1", "assistant", "通常の回答です", "Bot", "", "", "", "", "2026-05-18T10:02:01Z", "m3"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    rows = build_integrated_rows(interactions, sessions, manifest)
    
    assert len(rows) == 3
    # Row 1: System command
    assert rows[0]["qa_classification"] == "④集計対象外"
    assert rows[0]["is_target"] == "×"
    # Row 2: No answer
    assert rows[1]["qa_classification"] == "①該当無"
    assert rows[1]["is_target"] == "⚪︎"
    # Row 3: Standard question
    assert rows[2]["qa_classification"] == "⑤その他"
    assert rows[2]["is_target"] == "⚪︎"


def test_integrated_unclassified_propagation():
    from core import RawEvent, Manifest
    from normalizer import normalize_events
    from sessionizer import sessionize
    from integrated import build_integrated_rows
    from datetime import datetime, timezone
    
    events = [
        RawEvent("DM", "c_unclass", "user", "Q1", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c_unclass", "assistant", "A1", "Bot", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    rows = build_integrated_rows(interactions, sessions, manifest)
    
    assert len(rows) == 1
    assert rows[0]["final_category"] == "未分類"
    assert rows[0]["predicted_category"] == "未分類"
    assert rows[0]["fist_category"] == "未分類"


