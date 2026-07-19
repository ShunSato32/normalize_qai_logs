import argparse
import sys
import os
import json
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
from excel_writer import write_integrated_to_excel, parse_iso_datetime
from datetime import datetime, timezone, timedelta

def main():
    parser = argparse.ArgumentParser(description="YourNavi-QAI Logs Normalization Tool")
    parser.add_argument("INPUT_DIR", nargs="?", default="input_csv", help="Directory containing raw CSV files (default: input_csv)")
    parser.add_argument("OUTPUT_DIR", nargs="?", default="output_run", help="Directory to save the normalized output (default: output_run)")
    parser.add_argument("--anonymize-users", action="store_true", help="Anonymize user names")
    parser.add_argument("--strict", action="store_true", help="Fail if any input file has errors")
    parser.add_argument("--no-template", action="store_true", help="Do not use template Excel file even if present")
    
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
        jst_tz = timezone(timedelta(hours=9))
        timestamp = datetime.now(jst_tz).strftime('%Y%m%d%H%M%S')
        output_excel_name = f"【社名】実施記録分析シート_統合版_{timestamp}.xlsx"
        output_excel_path = os.path.join(output_dir, output_excel_name)
        
        template_path = None
        if not args.no_template:
            template_path = os.path.join(script_dir, "templates", "【社名】実施記録分析シート.xlsx")
            if not os.path.exists(template_path):
                template_path = None
                print("Warning: Template Excel file not found. Generating Excel programmatically without template.", file=sys.stderr)
        
        use_temp_flag = False
        if template_path:
            try:
                write_integrated_to_excel(template_path, output_excel_path, integrated_rows)
                use_temp_flag = True
            except Exception as e:
                print(f"Warning: Failed to load template ({e}). Falling back to programmatic Excel generation.", file=sys.stderr)
                write_integrated_to_excel(None, output_excel_path, integrated_rows)
        else:
            write_integrated_to_excel(None, output_excel_path, integrated_rows)
            
        print(f"Excel output created at: {output_excel_path}")
        
        # 9.5 If template is NOT used (forced or fallback), also write integrated rows as CSV
        if not use_temp_flag:
            output_csv_name = f"【社名】実施記録分析シート_統合版_{timestamp}.csv"
            output_csv_path = os.path.join(output_dir, output_csv_name)
            
            # Load column configurations dynamically
            config_paths_to_try = [
                os.path.join(project_root, "config", "column_config.json"),
                os.path.join(script_dir, "config", "column_config.json"),
                "config/column_config.json"
            ]
            config_file_path = None
            for p in config_paths_to_try:
                if os.path.exists(p):
                    config_file_path = p
                    break
            
            if not config_file_path:
                # Try template fallbacks
                for p in config_paths_to_try:
                    dir_name = os.path.dirname(p)
                    base_name = os.path.basename(p)
                    name, ext = os.path.splitext(base_name)
                    template_path = os.path.join(dir_name, f"{name}_template{ext}")
                    if os.path.exists(template_path):
                        try:
                            import shutil
                            if dir_name:
                                os.makedirs(dir_name, exist_ok=True)
                            shutil.copyfile(template_path, p)
                            print(f"Initialized active config file from template: {p}")
                            config_file_path = p
                            break
                        except Exception as e:
                            print(f"Warning: Failed to copy template {template_path} to {p}: {e}", file=sys.stderr)
                            config_file_path = template_path
                            break

            active_columns = []
            if config_file_path:
                try:
                    with open(config_file_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)
                    for item in config_data:
                        pname = item.get("physical_name")
                        jname = item.get("japanese_name") or pname
                        if pname:
                            active_columns.append((pname, jname))
                except Exception as e:
                    print(f"Warning: Failed to load column_config.json inside CSV generator: {e}", file=sys.stderr)
                    traceback.print_exc()
            else:
                print("Warning: column_config.json not found for CSV generator. Falling back to default headers.", file=sys.stderr)
            
            if not active_columns:
                from excel_writer import HEADERS
                active_columns = [(h, h) for h in HEADERS]
                
            # user_name 列のインデックスを求めてアルファベットに変換する（departmentのVLOOKUP用）
            user_name_col_letter = "K" # デフォルト
            try:
                from openpyxl.utils import get_column_letter
                for idx, (pn, jn) in enumerate(active_columns):
                    if pn == "user_name":
                        user_name_col_letter = get_column_letter(idx + 2) # エクセル上でB列から開始するため idx+2
                        break
            except Exception:
                pass
                
            import csv
            try:
                with open(output_csv_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    # Write header
                    writer.writerow([jname for pname, jname in active_columns])
                    
                    # Write rows
                    for row_idx, row_data in enumerate(integrated_rows, start=1):
                        row_values = []
                        is_sys_cmd = (row_data.get("is_system_command") in (1, "1", True, "true", "True"))
                        
                        # 1. Parse retrievals from retrieval_xx columns
                        parsed_retrievals = {}
                        for rank in range(1, 11):
                            col_name = f"retrieval_{rank:02d}"
                            json_str = row_data.get(col_name)
                            filename = ""
                            content = ""
                            score_val = ""
                            if json_str:
                                try:
                                    data = json.loads(json_str)
                                    filename = data.get("filename") or data.get("fileName") or data.get("display_name") or ""
                                    content = data.get("content", "")
                                    s = data.get("score")
                                    if s is not None and s != "":
                                        score_val = float(s)
                                except Exception:
                                    pass
                            parsed_retrievals[f"ref_doc_{rank}"] = filename
                            parsed_retrievals[f"ref_text_{rank}"] = content
                            parsed_retrievals[f"score_{rank}"] = score_val
                            
                        # 2. Check keywords against retrieved content
                        ref_checks = {}
                        kw1 = str(row_data.get("keyword_1", "")).strip()
                        kw2 = str(row_data.get("keyword_2", "")).strip()
                        kw3 = str(row_data.get("keyword_3", "")).strip()
                        any_hit = False
                        for rank in range(1, 11):
                            text = parsed_retrievals[f"ref_text_{rank}"]
                            hit = False
                            if text:
                                for kw in (kw1, kw2, kw3):
                                    if kw and kw in text:
                                        hit = True
                                        break
                            ref_checks[f"ref_check_{rank}"] = "〇" if hit else ""
                            if hit:
                                any_hit = True
                                
                        for pname, jname in active_columns:
                            if pname == "No.":
                                val = row_idx
                            elif pname == "qa_classification":
                                val = row_data.get("qa_classification", "")
                                if is_sys_cmd and not val:
                                    val = "④集計対象外"
                            elif pname == "is_target":
                                if is_sys_cmd:
                                    val = "×"
                                else:
                                    q_class = row_data.get("qa_classification", "")
                                    if q_class and (q_class.startswith("①") or q_class.startswith("⑤")):
                                        val = "◯"
                                    else:
                                        val = "×"
                            elif pname.startswith("ref_doc_") and len(pname) > 8:
                                val = parsed_retrievals.get(pname, "")
                            elif pname.startswith("ref_text_") and len(pname) > 9:
                                val = parsed_retrievals.get(pname, "")
                            elif pname.startswith("score_") and len(pname) > 6:
                                score_val = parsed_retrievals.get(pname, "")
                                val = f"{score_val:.6f}" if isinstance(score_val, float) else score_val
                            elif pname.startswith("ref_check_") and len(pname) > 10:
                                val = ref_checks.get(pname, "")
                            elif pname == "hit_judgment":
                                val = "〇" if any_hit else ""
                            elif pname == "date_jst":
                                started_jst = row_data.get("started_at_jst", "")
                                if started_jst and len(started_jst) >= 10:
                                    val = started_jst[:10].replace("-", "/")
                                else:
                                    val = ""
                            elif pname == "department":
                                # Row index in Excel JST sheet starts at 4 (row_idx + 3)
                                val = f'=VLOOKUP({user_name_col_letter}{row_idx+3},社員マスタ!C:D,2,0)'
                            elif pname in ("started_at_utc", "completed_at_utc", "started_at_jst", "completed_at_jst", "feedback_at_utc", "feedback_at_jst"):
                                val_str = row_data.get(pname, "")
                                if val_str:
                                    dt = parse_iso_datetime(val_str)
                                    val = dt.strftime('%Y/%m/%d %H:%M:%S') if dt else val_str
                                else:
                                    val = ""
                            else:
                                val = row_data.get(pname, "")
                                
                            row_values.append(val)
                        writer.writerow(row_values)
                print(f"CSV output created at: {output_csv_path}")
            except Exception as csv_err:
                print(f"Warning: Failed to create output CSV: {csv_err}", file=sys.stderr)
            
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
