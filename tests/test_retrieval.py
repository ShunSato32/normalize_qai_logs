import pytest
from core import RawEvent, Manifest
from normalizer import normalize_events
from datetime import datetime, timezone

def test_json_similar_records():
    # Test case 4: JSON format
    json_str = '[{"content": "res1", "score": 0.9}, {"content": "res2", "score": 0.8}]'
    events = [
        RawEvent("DM", "c1", "tool", "Tool Result", "Bot", "", json_str, "", "", "2026-05-18T10:00:02Z", "m1")
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(results) == 2
    assert results[0]["retrieved_content"] == "res1"
    assert results[0]["score"] == 0.9

def test_python_literal_similar_records():
    # Test case 5: Python literal
    # Using single quotes and True which JSON wouldn't parse directly
    literal_str = "[{'content': 'res1', 'metadata': {'is_qa': True}}, {'content': 'res2'}]"
    events = [
        RawEvent("DM", "c1", "tool", "Tool Result", "Bot", "", literal_str, "", "", "2026-05-18T10:00:02Z", "m1")
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(results) == 2
    assert results[0]["is_qa"] == "true"

def test_broken_similar_records():
    # Test case 6: broken format
    broken_str = "[{broken"
    events = [
        RawEvent("DM", "c1", "tool", "Tool Result", "Bot", "", broken_str, "", "", "2026-05-18T10:00:02Z", "m1")
    ]
    for e in events:
        e.interaction_key = f"{e.conversation_id}::{e.message_id}"
        e.created_at_utc = datetime.fromisoformat(e.created_at_str.replace("Z", "+00:00")).astimezone(timezone.utc)
        
    manifest = Manifest()
    interactions, results = normalize_events(events, manifest)
    
    assert len(results) == 0
    assert interactions[0].similar_records_parse_failures == 1
