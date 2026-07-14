import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="YourNavi-QAI Analytics End-to-End Automation Pipeline")
    parser.add_argument("--skip-fetch", action="store_true", help="Skip S3 CSV fetching step and only run Excel normalizer.")
    parser.add_argument("--skip-excel", action="store_true", help="Skip Excel normalization step and only run S3 CSV fetch.")
    parser.add_argument("--config", type=str, default=None, help="Custom path to s3_config.json")
    parser.add_argument("--no-template", action="store_true", help="Do not use template Excel file even if present")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.abspath(__file__))
    s3_fetcher_dir = os.path.join(project_root, "s3_fetcher")
    if s3_fetcher_dir not in sys.path:
        sys.path.insert(0, s3_fetcher_dir)

    # 1. Generate local date-dependent JST directory (yyyymmdd_ddd format)
    from datetime import datetime, timezone, timedelta
    jst_tz = timezone(timedelta(hours=9))
    now_jst = datetime.now(jst_tz)
    day_abbrs = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    folder_name = now_jst.strftime(f"%Y%m%d_{day_abbrs[now_jst.weekday()]}")

    input_dir = os.path.join(project_root, "input_csv", folder_name)
    output_dir = os.path.join(project_root, "output_run", folder_name)

    print("=====================================================")
    print("      YourNavi-QAI End-to-End Analytics Pipeline     ")
    print("=====================================================")
    print(f"Target execution directory: {folder_name}")

    # Step 1: S3 Fetch CSV & Archive
    if not args.skip_fetch:
        print("\n--- [Step 1] Fetching CSV logs from S3 & Archiving ---")
        try:
            from fetch_csv import run_s3_fetch
            cfg_path = args.config if args.config else os.path.join(s3_fetcher_dir, "s3_config.json")
            res = run_s3_fetch(config_path=cfg_path, dest_dir=input_dir)
            if res.get("status") == "error":
                print("[Pipeline Error] S3 fetch step encountered an error.")
                sys.exit(1)
        except Exception as e:
            print(f"[Pipeline Error] Failed to run S3 fetch module: {e}")
            sys.exit(1)
    else:
        print("\n--- [Step 1] Skipped S3 Fetching (--skip-fetch) ---")

    # Step 2: Run Excel Normalizer & Generator
    if not args.skip_excel:
        print("\n--- [Step 2] Running Excel Normalization & Generation ---")
        try:
            normalize_script = os.path.join(project_root, "excel_generator", "normalize_chatbot_logs.py")
            import subprocess
            cmd = [sys.executable, normalize_script, input_dir, output_dir]
            if args.no_template:
                cmd.append("--no-template")
            ret = subprocess.run(cmd, cwd=project_root)
            if ret.returncode != 0:
                print(f"[Pipeline Error] Excel generation failed with return code {ret.returncode}")
                sys.exit(1)
        except Exception as e:
            print(f"[Pipeline Error] Failed to run Excel generation script: {e}")
            sys.exit(1)
    else:
        print("\n--- [Step 2] Skipped Excel Generation (--skip-excel) ---")

    print("\n=====================================================")
    print("   All automated pipeline steps completed successfully! ")
    print("=====================================================")

if __name__ == "__main__":
    main()
