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

def test_category_forward_propagation():
    # Verify that user_selected_categories and inferred_category propagate forward in the same session until reset
    events = [
        create_interaction("c1", "m1", "Q1", 0),
        create_interaction("c1", "m2", "Q2", 10),
        create_interaction("c1", "m3", "リセット", 20),
        create_interaction("c1", "m4", "Q3", 30),
    ]
    # Simulate first event having a category selection
    events[0].category = "制度・運用 > 服務"
    events[0].content = "[カテゴリ選択]"
    
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessionize(interactions, manifest)
    
    # Interaction 0: Category selection
    assert interactions[0].user_selected_categories == "制度・運用 > 服務"
    assert interactions[0].final_category == "制度・運用 > 服務"
    
    # Interaction 1: Q2 without explicit category -> inherits from Interaction 0
    assert interactions[1].user_selected_categories == "制度・運用 > 服務"
    assert interactions[1].final_category == "制度・運用 > 服務"
    
    # Interaction 2: Reset request -> inherits within same session
    assert interactions[2].user_selected_categories == "制度・運用 > 服務"
    
    # Interaction 3: New session after reset -> should not inherit
    assert interactions[3].user_selected_categories == ""
    assert interactions[3].final_category == ""


def test_interaction_no_in_session_rules():
    events = [
        create_interaction("c_no", "m1", "[カテゴリ選択]", 0),
        create_interaction("c_no", "m2", "最初の質問", 10),
        create_interaction("c_no", "m3", "[追加評価]", 20),
        create_interaction("c_no", "m4", "次の質問", 30),
    ]
    manifest = Manifest()
    interactions, _ = normalize_events(events, manifest)
    sessionize(interactions, manifest)
    
    assert interactions[0].interaction_no_in_session == "-"
    assert interactions[1].interaction_no_in_session == 0
    assert interactions[2].interaction_no_in_session == "-"
    assert interactions[3].interaction_no_in_session == 1

