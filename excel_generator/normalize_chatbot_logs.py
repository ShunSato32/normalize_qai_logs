import argparse
import sys
import os
import traceback

# Ensure current script directory is in sys.path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from core import Manifest
from reader import read_raw_events
from normalizer import normalize_events
from sessionizer import sessionize
from analytics import compute_overview, compute_daily, compute_category, compute_session_distribution, collect_feedback_events
from integrated import build_integrated_rows
from writer import write_analytics, write_manifest
from excel_writer import write_integrated_to_excel
from datetime import datetime, timezone, timedelta

def main():
    parser = argparse.ArgumentParser(description="YourNavi-QAI Logs Normalization Tool")
    parser.add_argument("INPUT_DIR", nargs="?", default="input_csv", help="Directory containing raw CSV files (default: input_csv)")
    parser.add_argument("OUTPUT_DIR", nargs="?", default="output_run", help="Directory to save the normalized output (default: output_run)")
    parser.add_argument("--anonymize-users", action="store_true", help="Anonymize user names")
    parser.add_argument("--strict", action="store_true", help="Fail if any input file has errors")
    
    args = parser.parse_args()
    
    input_dir = args.INPUT_DIR
    if not os.path.isabs(input_dir) and not os.path.exists(input_dir):
        input_dir = os.path.join(project_root, input_dir)
        
    output_dir = args.OUTPUT_DIR
    if not os.path.isabs(output_dir) and not os.path.exists(output_dir):
        output_dir = os.path.join(project_root, output_dir)
    
    if not os.path.exists(input_dir):
        print(f"Error: Input directory does not exist: {input_dir}", file=sys.stderr)
        sys.exit(2)
        
    os.makedirs(output_dir, exist_ok=True)
    
    manifest = Manifest()
    manifest.input_directory = input_dir
    manifest.output_directory = output_dir
    manifest.strict_mode = args.strict
    manifest.anonymize_users = args.anonymize_users
    
    print(f"Reading raw events from: {input_dir} ...")
    raw_events = read_raw_events(input_dir, manifest, args.anonymize_users)
    print(f"Total valid raw events loaded: {len(raw_events)}")
    
    if manifest.counts.get("skipped_file_count", 0) > 0 and args.strict:
        print("Error: Strict mode enabled and input errors occurred.", file=sys.stderr)
        for w in manifest.warnings:
            print(f"  - {w}", file=sys.stderr)
        sys.exit(1)
        
    try:
        # 3. Normalize Interactions
        interactions, retrieval_results = normalize_events(raw_events, manifest)
        
        # 4. Sessionize
        sessions = sessionize(interactions, manifest)
        
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
        
        # 8. Export requested CSVs and manifest
        write_analytics(output_dir, overview, daily, category, dist)
        write_manifest(output_dir, manifest)
        
        # 9. Generate JST Timestamped Excel Workbook directly into output_dir
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "templates", "【社名】実施記録分析シート.xlsx")
        
        if not os.path.exists(template_path):
            print(f"Warning: Template Excel file not found at {template_path}. Skipping Excel output generation.", file=sys.stderr)
        else:
            jst_tz = timezone(timedelta(hours=9))
            timestamp = datetime.now(jst_tz).strftime('%Y%m%d%H%M%S')
            output_excel_name = f"【社名】実施記録分析シート_統合版_{timestamp}.xlsx"
            output_excel_path = os.path.join(output_dir, output_excel_name)
            
            write_integrated_to_excel(template_path, output_excel_path, integrated_rows)
            print(f"Excel output created at: {output_excel_path}")
            
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
