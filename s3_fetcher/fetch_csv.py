import json
import os
import sys
import glob
from typing import Optional, List, Dict, Any

# Ensure local module import regardless of current working directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from s3_utils import list_s3_files, download_s3_file, archive_s3_file

def run_s3_fetch(config_path: Optional[str] = None, dest_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute S3 CSV fetch and archive workflow based on config file.
    Returns summary dict of downloaded and archived files.
    """
    if not config_path:
        config_path = os.path.join(current_dir, "s3_config.json")
        
    print(f"=== Starting S3 Fetcher ===")
    print(f"Config path: {config_path}")
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    profile = config.get("aws_profile")
    if profile == "default":
        profile = None # Use default credentials without passing explicit --profile flag if it is "default"
        
    region = config.get("aws_region")
    s3_cfg = config.get("s3", {})
    bucket_name = s3_cfg.get("bucket_name", "")
    prefix = s3_cfg.get("source_prefix", "")
    archive_folder = s3_cfg.get("archive_folder_name", "archive/")
    ext_filter = s3_cfg.get("file_extension_filter", ".csv")
    
    local_cfg = config.get("local", {})
    if not dest_dir:
        dest_dir = local_cfg.get("download_destination_dir", "../input_csv")
    if not os.path.isabs(dest_dir):
        dest_dir = os.path.abspath(os.path.join(current_dir, dest_dir))
        
    clear_before_dl = local_cfg.get("clear_destination_before_download", False)
    
    arch_cfg = config.get("archive_behavior", {})
    append_ts = arch_cfg.get("append_timestamp_on_archive", True)
    ts_fmt = arch_cfg.get("archive_timestamp_format", "_%Y%m%d_%H%M%S")
    
    if not bucket_name or bucket_name == "your-company-qai-logs-bucket":
        print("[Warning] Bucket name is not configured properly in s3_config.json.")
        
    os.makedirs(dest_dir, exist_ok=True)
    
    if clear_before_dl:
        print(f"[Local] Cleaning destination directory before download: {dest_dir}")
        for old_file in glob.glob(os.path.join(dest_dir, f"*{ext_filter}")):
            try:
                os.remove(old_file)
            except Exception as e:
                print(f"[Warning] Failed to remove old file {old_file}: {e}")
                
    # 1. List target files on S3
    print(f"[S3] Searching target CSV files in s3://{bucket_name}/{prefix} ...")
    try:
        files_to_download = list_s3_files(
            bucket_name=bucket_name,
            prefix=prefix,
            archive_folder_name=archive_folder,
            file_extension_filter=ext_filter,
            profile=profile,
            region=region
        )
    except Exception as e:
        print(f"[Error] Failed to list S3 files: {e}")
        return {"status": "error", "message": str(e), "downloaded": []}
        
    if not files_to_download:
        print("[S3] No new target CSV files found on S3.")
        return {"status": "success", "downloaded_count": 0, "downloaded": []}
        
    print(f"[S3] Found {len(files_to_download)} new CSV file(s) to download.")
    
    downloaded_records = []
    
    # 2. Download and Archive each file
    for file_info in files_to_download:
        s3_key = file_info["key"]
        filename = file_info["filename"]
        local_path = os.path.join(dest_dir, filename)
        
        print(f"[Download] {filename} ({file_info['size']} bytes) -> {local_path} ...")
        success = download_s3_file(
            bucket_name=bucket_name,
            s3_key=s3_key,
            dest_path=local_path,
            profile=profile,
            region=region
        )
        
        if success:
            print(f"[Success] Downloaded {filename} successfully.")
            # Move to archive only after verification
            archived = archive_s3_file(
                bucket_name=bucket_name,
                source_key=s3_key,
                archive_folder_name=archive_folder,
                append_timestamp=append_ts,
                timestamp_format=ts_fmt,
                profile=profile,
                region=region
            )
            downloaded_records.append({
                "filename": filename,
                "local_path": local_path,
                "size": file_info["size"],
                "archived_on_s3": archived
            })
        else:
            print(f"[Error] Failed to verify download for {filename}. Skipping archive.")
            
    print("=== S3 Fetch Workflow Completed ===")
    print(f"Total files downloaded: {len(downloaded_records)} / {len(files_to_download)}")
    
    return {
        "status": "success",
        "downloaded_count": len(downloaded_records),
        "downloaded": downloaded_records
    }

if __name__ == "__main__":
    try:
        res = run_s3_fetch()
        if res.get("status") == "error":
            sys.exit(1)
    except Exception as ex:
        print(f"Fatal error during S3 fetch workflow: {ex}")
        sys.exit(1)
