import pytest
from core import RawEvent, Manifest
from normalizer import normalize_events
from sessionizer import sessionize
from datetime import datetime, timezone, timedelta

def create_interaction(conv_id, msg_id, user_content, time_offset_sec):
    base_time = datetime(2026, 5, 18, 10, 0, 0, tzinfo=timezone.utc)
    t = base_time + timedelta(seconds=time_offset_sec)
    
    e = RawEvent("DM", conv_id, "user", user_content, "User", "", "", "", "", t.isoformat(), msg_id)
    e.interaction_key = f"{conv_id}::{msg_id}"
    e.created_at_utc = t
    return e

def test_no_reset():
    # Test case 7: no reset -> all in R001
    events = [
        create_interaction("c1", "m1", "Q1", 0),
        create_interaction("c1", "m2", "Q2", 10),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 1
    assert sessions[0].reset_session_id == "c1-S001"
    assert sessions[0].interaction_count == 2
    assert interactions[0].reset_session_id == "c1-S001"
    assert interactions[1].reset_session_id == "c1-S001"

def test_q_reset_q():
    # Test case 8: Q -> reset -> Q
    events = [
        create_interaction("c1", "m1", "Q1", 0),
        create_interaction("c1", "m2", "リセット", 10),
        create_interaction("c1", "m3", "Q2", 20),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 2
    assert sessions[0].reset_session_id == "c1-S001"
    assert sessions[0].interaction_count == 2
    assert sessions[0].ended_by_reset is True
    
    assert sessions[1].reset_session_id == "c1-S002"
    assert sessions[1].interaction_count == 1
    
    assert interactions[0].reset_session_id == "c1-S001"
    assert interactions[1].reset_session_id == "c1-S001"
    assert interactions[2].reset_session_id == "c1-S002"

def test_start_with_reset():
    # Test case 9: start with reset
    events = [
        create_interaction("c1", "m1", "リセット", 0),
        create_interaction("c1", "m2", "Q1", 10),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 2
    assert sessions[0].reset_session_id == "c1-S001"
    assert sessions[0].interaction_count == 1
    assert sessions[1].reset_session_id == "c1-S002"
    assert sessions[1].interaction_count == 1

def test_end_with_reset():
    # Test case 10: end with reset (no empty R002)
    events = [
        create_interaction("c1", "m1", "Q1", 0),
        create_interaction("c1", "m2", "リセット", 10),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 1
    assert sessions[0].reset_session_id == "c1-S001"
    assert sessions[0].interaction_count == 2
    assert sessions[0].ended_by_reset is True

def test_consecutive_resets():
    # Test case 11: consecutive resets
    events = [
        create_interaction("c1", "m1", "リセット", 0),
        create_interaction("c1", "m2", "リセット", 10),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 2
    assert sessions[0].reset_session_id == "c1-S001"
    assert sessions[0].interaction_count == 1
    assert sessions[1].reset_session_id == "c1-S002"
    assert sessions[1].interaction_count == 1

def test_day_cross_no_reset():
    # Test case 12: crosses day without reset -> same session
    events = [
        create_interaction("c1", "m1", "Q1", 0),
        create_interaction("c1", "m2", "Q2", 24 * 3600 + 10), # 1 day later
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessions = sessionize(interactions, manifest)
    
    assert len(sessions) == 1
    assert sessions[0].interaction_count == 2
