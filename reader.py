import csv
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Generator

from core import RawEvent, Manifest, hash_user_name, JST

# OLE/IRM file signature
OLE_SIGNATURE = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])

def parse_datetime(dt_str: str) -> datetime:
    """Parses ISO 8601 datetime strings to UTC datetime."""
    if not dt_str:
        return None
    try:
        # Replace 'Z' with '+00:00' for standard fromisoformat parsing (Python 3.11+)
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        dt = datetime.fromisoformat(dt_str)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None

def is_irm_protected(filepath: str) -> bool:
    try:
        with open(filepath, 'rb') as f:
            header = f.read(8)
            return header == OLE_SIGNATURE
    except Exception:
        return False

def discover_csv_files(input_dir: str) -> List[str]:
    files = [f for f in os.listdir(input_dir) if f.lower().endswith('.csv')]
    # Return full paths sorted by filename
    return sorted([os.path.join(input_dir, f) for f in files])

def read_raw_events(input_dir: str, manifest: Manifest, anonymize: bool) -> List[RawEvent]:
    csv_files = discover_csv_files(input_dir)
    
    raw_events: List[RawEvent] = []
    
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        
        if is_irm_protected(filepath):
            manifest.add_skipped_file(filename, "IRM/OLE protected file detected.")
            if manifest.strict_mode:
                print(f"Error: IRM/OLE protected file found: {filename} in strict mode.", file=sys.stderr)
                sys.exit(1)
            continue
            
        # Try encodings
        encodings_to_try = ['utf-8-sig', 'cp932', 'utf-8']
        file_content = None
        used_encoding = None
        
        for enc in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    file_content = f.read()
                    used_encoding = enc
                    break
            except UnicodeDecodeError:
                continue
                
        if file_content is None:
            manifest.add_skipped_file(filename, "Could not decode file with supported encodings.")
            if manifest.strict_mode:
                print(f"Error: Could not decode {filename} in strict mode.", file=sys.stderr)
                sys.exit(1)
            continue
            
        # Parse CSV
        import io
        reader = csv.DictReader(io.StringIO(file_content))
        
        # Check required columns
        required_cols = [
            'team_name', 'conversation_id', 'message_type', 'content', 
            'user_name', 'category', 'similar_records', 'feedback_rating',
            'feedback_comment', 'created_at', 'message_id'
        ]
        
        if reader.fieldnames is None:
            manifest.add_skipped_file(filename, "File has no header.")
            if manifest.strict_mode:
                sys.exit(1)
            continue
            
        missing_cols = [col for col in required_cols if col not in reader.fieldnames]
        if missing_cols:
            manifest.add_skipped_file(filename, f"Missing required columns: {', '.join(missing_cols)}")
            if manifest.strict_mode:
                sys.exit(1)
            continue
            
        manifest.readable_input_files.append(filename)
        manifest.counts["readable_file_count"] += 1
        
        for row_num, row in enumerate(reader, start=2): # 1 is header
            team_name = (row.get('team_name') or '').strip()
            conversation_id = (row.get('conversation_id') or '').strip()
            message_type = (row.get('message_type') or '').strip()
            content = (row.get('content') or '').strip()
            user_name = (row.get('user_name') or '').strip()
            category = (row.get('category') or '').strip()
            similar_records = (row.get('similar_records') or '').strip()
            feedback_rating = (row.get('feedback_rating') or '').strip()
            feedback_comment = (row.get('feedback_comment') or '').strip()
            created_at_str = (row.get('created_at') or '').strip()
            message_id = (row.get('message_id') or '').strip()
            
            event_id = f"{filename}#{row_num}"
            
            if not conversation_id:
                manifest.add_warning(f"Empty conversation_id at {event_id}. Using fallback.")
                conversation_id = f"UNKNOWN_CONV_{event_id}"
                
            if not message_id:
                manifest.add_warning(f"Empty message_id at {event_id}. Using fallback.")
                message_id = f"UNKNOWN_MSG_{event_id}"
                
            interaction_key = f"{conversation_id}::{message_id}"
            
            # Anonymize if needed
            user_key = hash_user_name(user_name)
            if anonymize:
                user_name = ""
                
            dt_utc = parse_datetime(created_at_str)
            dt_jst = None
            event_date_jst = ""
            event_time_jst = ""
            
            if dt_utc:
                dt_jst = dt_utc.astimezone(JST)
                event_date_jst = dt_jst.strftime('%Y-%m-%d')
                event_time_jst = dt_jst.strftime('%H:%M:%S')
            else:
                manifest.add_warning(f"Failed to parse datetime at {event_id}: {created_at_str}")
                manifest.counts["datetime_parse_error_count"] += 1

            raw_event = RawEvent(
                team_name=team_name,
                conversation_id=conversation_id,
                message_type=message_type,
                content=content,
                user_name=user_name,
                category=category,
                similar_records=similar_records,
                feedback_rating=feedback_rating,
                feedback_comment=feedback_comment,
                created_at_str=created_at_str,
                message_id=message_id,
                event_id=event_id,
                source_file=filename,
                source_row_number=row_num,
                created_at_utc=dt_utc,
                created_at_jst=dt_jst,
                event_date_jst=event_date_jst,
                event_time_jst=event_time_jst,
                interaction_key=interaction_key,
                user_key=user_key
            )
            raw_events.append(raw_event)
            
    manifest.counts["input_file_count"] = len(csv_files)
    
    if len(manifest.readable_input_files) == 0 and len(csv_files) > 0:
        print("Error: No readable files found.", file=sys.stderr)
        sys.exit(1)
        
    return raw_events
