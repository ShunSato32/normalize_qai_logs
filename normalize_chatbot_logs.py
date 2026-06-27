import argparse
import sys
import os
import traceback

from core import Manifest
from reader import read_raw_events
from normalizer import normalize_events
from sessionizer import sessionize
from analytics import compute_overview, compute_daily, compute_category, compute_session_distribution, collect_feedback_events
from integrated import build_integrated_rows
from writer import (
    write_raw_events, write_interactions, write_reset_sessions,
    write_retrieval_results, write_feedback, write_analytics,
    write_manifest, write_data_dictionary, write_integrated
)
from excel_writer import write_integrated_to_excel
from datetime import datetime, timezone, timedelta

def main():
    parser = argparse.ArgumentParser(description="YourNavi-QAI Logs Normalization Tool")
    parser.add_argument("INPUT_DIR", help="Directory containing raw CSV files")
    parser.add_argument("OUTPUT_DIR", help="Directory to save the normalized output")
    parser.add_argument("--anonymize-users", action="store_true", help="Anonymize user names")
    parser.add_argument("--strict", action="store_true", help="Fail if any input file has errors")
    
    args = parser.parse_args()
    
    input_dir = args.INPUT_DIR
    output_dir = args.OUTPUT_DIR
    
    if not os.path.exists(input_dir):
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(2)
        
    os.makedirs(output_dir, exist_ok=True)
    
    manifest = Manifest()
    manifest.input_directory = input_dir
    manifest.output_directory = output_dir
    manifest.anonymize_users = args.anonymize_users
    manifest.strict_mode = args.strict
    
    try:
        # 1. Read events
        raw_events = read_raw_events(input_dir, manifest, args.anonymize_users)
        
        # 2. Normalize into interactions and extract retrieval results
        interactions, retrieval_results = normalize_events(raw_events, manifest)
        
        # 3. Sessionize
        sessions = sessionize(interactions, manifest)
        
        # 4. Backpropagate session_id to retrieval_results
        # Build mapping from interaction_key to reset_session_id
        session_map = {i.interaction_key: i.reset_session_id for i in interactions}
        for rr in retrieval_results:
            rr["reset_session_id"] = session_map.get(rr["interaction_key"], "")
            
        # 5. Extract feedback
        feedback_events = collect_feedback_events(interactions)
        manifest.counts["feedback_count"] = len(feedback_events)
        
        # 6. Integrated Rows
        integrated_rows = build_integrated_rows(interactions, sessions, manifest)
        
        # 7. Analytics
        overview = compute_overview(manifest)
        daily = compute_daily(interactions)
        category = compute_category(interactions)
        dist = compute_session_distribution(sessions)
        
        # 8. Export
        write_raw_events(output_dir, raw_events)
        write_interactions(output_dir, interactions)
        write_reset_sessions(output_dir, sessions)
        write_retrieval_results(output_dir, retrieval_results)
        write_feedback(output_dir, feedback_events)
        write_integrated(output_dir, integrated_rows)
        write_analytics(output_dir, overview, daily, category, dist)
        write_data_dictionary(output_dir)
        write_manifest(output_dir, manifest)
        
        # 9. Generate JST Timestamped Excel Workbook
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "..", "【生成AI】実施記録分析シート_20260610132229.xlsx")
        
        if not os.path.exists(template_path):
            print(f"Warning: Template Excel file not found at {template_path}. Skipping Excel output generation.", file=sys.stderr)
        else:
            jst_tz = timezone(timedelta(hours=9))
            timestamp = datetime.now(jst_tz).strftime('%Y%m%d%H%M%S')
            output_excel_name = f"【生成AI】実施記録分析シート_統合版_{timestamp}.xlsx"
            
            # Save copy in the parent directory (next to the template)
            parent_output_excel_path = os.path.join(script_dir, "..", output_excel_name)
            write_integrated_to_excel(template_path, parent_output_excel_path, integrated_rows)
            print(f"Excel output created at: {parent_output_excel_path}")
            
            # Also save copy in the output directory
            output_dir_excel_path = os.path.join(output_dir, output_excel_name)
            import shutil
            shutil.copy2(parent_output_excel_path, output_dir_excel_path)
            
        # Validation checks
        if len(raw_events) != manifest.counts["raw_event_count"]:
            print(f"Warning: Raw event count mismatch. Expected {manifest.counts['raw_event_count']}, got {len(raw_events)}", file=sys.stderr)
            
        print("Processing completed successfully.")
        sys.exit(0)
        
    except Exception as e:
        print(f"Fatal error during processing: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
