import os
import pytest
import csv
from reader import read_raw_events, is_irm_protected
from core import Manifest

def test_cp932_input(tmp_path):
    # Test case 15: CP932 input
    csv_file = tmp_path / "cp932.csv"
    content = "team_name,conversation_id,message_type,content,user_name,category,similar_records,feedback_rating,feedback_comment,created_at,message_id\n"
    content += "DM,conv1,user,テスト,,,,,2026-05-18T22:13:52.919Z,msg1\n"
    csv_file.write_text(content, encoding='cp932')
    
    manifest = Manifest()
    events = read_raw_events(str(tmp_path), manifest, False)
    
    assert len(events) == 1
    assert events[0].content == "テスト"

def test_irm_file_skipped(tmp_path):
    # Test case 16: IRM/OLE file skipped in normal mode
    irm_file = tmp_path / "irm.csv"
    with open(irm_file, 'wb') as f:
        f.write(bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + b"dummy")
        
    normal_csv = tmp_path / "normal.csv"
    content = "team_name,conversation_id,message_type,content,user_name,category,similar_records,feedback_rating,feedback_comment,created_at,message_id\n"
    content += "DM,conv1,user,テスト,,,,,2026-05-18T22:13:52.919Z,msg1\n"
    normal_csv.write_text(content, encoding='utf-8')
    
    manifest = Manifest()
    events = read_raw_events(str(tmp_path), manifest, False)
    
    assert len(events) == 1
    assert len(manifest.skipped_input_errors) == 1
    assert manifest.skipped_input_errors[0]['file'] == 'irm.csv'

def test_strict_mode_fails_on_irm(tmp_path):
    # Test case 17: All files IRM, or strict mode with IRM
    irm_file = tmp_path / "irm.csv"
    with open(irm_file, 'wb') as f:
        f.write(bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1]) + b"dummy")
        
    manifest = Manifest()
    manifest.strict_mode = True
    
    with pytest.raises(SystemExit):
        read_raw_events(str(tmp_path), manifest, False)

def test_anonymize_users(tmp_path):
    # Test case 18: Anonymization
    csv_file = tmp_path / "anon.csv"
    content = "team_name,conversation_id,message_type,content,user_name,category,similar_records,feedback_rating,feedback_comment,created_at,message_id\n"
    content += "DM,conv1,user,テスト,John Doe,,,,2026-05-18T22:13:52.919Z,msg1\n"
    csv_file.write_text(content, encoding='utf-8')
    
    manifest = Manifest()
    events = read_raw_events(str(tmp_path), manifest, True)
    
    assert len(events) == 1
    assert events[0].user_name == ""
    assert events[0].user_key != ""

def test_csv_newlines(tmp_path):
    # Test case 20: CSV cell newlines
    csv_file = tmp_path / "newlines.csv"
    content = 'team_name,conversation_id,message_type,content,user_name,category,similar_records,feedback_rating,feedback_comment,created_at,message_id\n'
    content += 'DM,conv1,user,"Multi\nLine",,,,,2026-05-18T22:13:52.919Z,msg1\n'
    csv_file.write_text(content, encoding='utf-8')
    
    manifest = Manifest()
    events = read_raw_events(str(tmp_path), manifest, False)
    
    assert len(events) == 1
    assert events[0].content == "Multi\nLine"

def test_same_time_events(tmp_path):
    # Test case 19: Same time events
    csv_file = tmp_path / "sametime.csv"
    content = 'team_name,conversation_id,message_type,content,user_name,category,similar_records,feedback_rating,feedback_comment,created_at,message_id\n'
    content += 'DM,conv1,user,A,,,,,2026-05-18T22:13:52.919Z,msg1\n'
    content += 'DM,conv1,assistant,B,,,,,2026-05-18T22:13:52.919Z,msg1\n'
    csv_file.write_text(content, encoding='utf-8')
    
    manifest = Manifest()
    events = read_raw_events(str(tmp_path), manifest, False)
    from normalizer import sort_events
    sorted_events = sort_events(events)
    
    assert sorted_events[0].content == "A"
    assert sorted_events[1].content == "B"
