import pytest
from core import RawEvent, Manifest
from normalizer import normalize_events
from datetime import datetime, timezone

def test_standard_flow():
    # Test case 1: Standard 5 event flow
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "assistant", "[選択された関数][func1]", "Bot", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
        RawEvent("DM", "c1", "tool", "Tool Result", "Bot", "", "", "", "", "2026-05-18T10:00:02Z", "m1"),
        RawEvent("DM", "c1", "assistant", "A", "Bot", "", "", "", "", "2026-05-18T10:00:03Z", "m1"),
        RawEvent("DM", "c1", "feedback", "", "User", "", "", "good", "nice", "2026-05-18T10:00:04Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(interactions) == 1
    i = interactions[0]
    assert i.question == "Q"
    assert i.answer == "A"
    assert i.selected_function == "func1"
    assert i.has_tool is True
    assert i.has_feedback is True
    assert i.feedback_rating == "good"
    assert i.feedback_comment == "nice"

def test_internal_logs_excluded():
    # Test case 2: Internal assistant logs are excluded from answer
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "assistant", "[選択された関数][func1]", "Bot", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
        RawEvent("DM", "c1", "assistant", "A", "Bot", "", "", "", "", "2026-05-18T10:00:03Z", "m1"),
        RawEvent("DM", "c1", "assistant", "[カテゴリ選択]", "Bot", "Cat1", "", "", "", "2026-05-18T10:00:04Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(interactions) == 1
    i = interactions[0]
    assert i.answer == "A"
    assert i.inferred_category == "Cat1"

def test_error_only_no_answer():
    # Test case 3: error only without final answer
    events = [
        RawEvent("DM", "c1", "user", "Q", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c1", "error", "Some error", "System", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(interactions) == 1
    i = interactions[0]
    assert i.answer == ""
    assert i.has_error is True
    assert i.error_text == "Some error"

def test_message_id_collision():
    # Test case 14: same message_id in different conversation_id
    events = [
        RawEvent("DM", "c1", "user", "Q1", "User", "", "", "", "", "2026-05-18T10:00:00Z", "m1"),
        RawEvent("DM", "c2", "user", "Q2", "User", "", "", "", "", "2026-05-18T10:00:01Z", "m1"),
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(interactions) == 2
    assert manifest.counts["message_id_collision_count"] == 1
