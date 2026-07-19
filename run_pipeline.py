import os
import sys
import argparse

def resolve_config_path(config_path):
    if os.path.exists(config_path):
        return config_path
    
    # Check corresponding template path
    dir_name = os.path.dirname(config_path)
    base_name = os.path.basename(config_path)
    name, ext = os.path.splitext(base_name)
    template_path = os.path.join(dir_name, f"{name}_template{ext}")
    
    if os.path.exists(template_path):
        try:
            import shutil
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            shutil.copyfile(template_path, config_path)
            print(f"Initialized active config file from template: {config_path}")
            return config_path
        except Exception as e:
            print(f"Warning: Failed to copy template {template_path} to {config_path}: {e}", file=sys.stderr)
            return template_path
    return config_path

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
            cfg_path = resolve_config_path(cfg_path)
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

    # Step 3: Copy to File Server
    import json
    common_cfg_path = os.path.join(project_root, "config", "common_config.json")
    common_cfg_path = resolve_config_path(common_cfg_path)
    if os.path.exists(common_cfg_path):
        fs_config = {}
        try:
            with open(common_cfg_path, "r", encoding="utf-8") as f:
                common_config = json.load(f)
            fs_config = common_config.get("file_server", {})
            if fs_config.get("enabled", False):
                dest_base = fs_config.get("destination_path", "")
                if dest_base:
                    print("\n--- [Step 3] Copying input and output logs to file server ---")
                    print(f"File Server Path: {dest_base}")
                    
                    import shutil
                    dest_input_dir = os.path.join(dest_base, "input_csv", folder_name)
                    dest_output_dir = os.path.join(dest_base, "output_run", folder_name)
                    
                    # Ensure parent paths exist
                    os.makedirs(os.path.dirname(dest_input_dir), exist_ok=True)
                    os.makedirs(os.path.dirname(dest_output_dir), exist_ok=True)
                    
                    if os.path.exists(input_dir):
                        print(f"Copying input logs: {input_dir} -> {dest_input_dir}")
                        shutil.copytree(input_dir, dest_input_dir, dirs_exist_ok=True)
                    else:
                        print(f"Warning: Input logs directory not found: {input_dir}")
                        
                    if os.path.exists(output_dir):
                        print(f"Copying output logs: {output_dir} -> {dest_output_dir}")
                        shutil.copytree(output_dir, dest_output_dir, dirs_exist_ok=True)
                    else:
                        print(f"Warning: Output logs directory not found: {output_dir}")
                        
                    print("Copying to file server completed successfully.")
        except Exception as e:
            print(f"[Pipeline Error] Failed to copy logs to file server: {e}", file=sys.stderr)
            if fs_config.get("fail_on_copy_error", False):
                sys.exit(1)

    print("\n=====================================================")
    print("   All automated pipeline steps completed successfully! ")
    print("=====================================================")

if __name__ == "__main__":
    main()
