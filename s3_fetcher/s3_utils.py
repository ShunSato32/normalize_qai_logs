import subprocess
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

def run_aws_command(cmd_args: List[str], profile: Optional[str] = None, region: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Execute an AWS CLI command safely using subprocess.
    """
    full_cmd = ["aws"] + cmd_args
    if profile:
        full_cmd.extend(["--profile", profile])
    if region:
        full_cmd.extend(["--region", region])
        
    print(f"[AWS CLI] Running: {' '.join(full_cmd)}")
    return subprocess.run(full_cmd, capture_output=True, text=True)

def list_s3_files(
    bucket_name: str,
    prefix: str,
    archive_folder_name: str,
    file_extension_filter: str = ".csv",
    profile: Optional[str] = None,
    region: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List files in S3 under bucket/prefix, excluding files in the archive folder or non-matching extensions.
    Returns a list of dicts: [{'key': '...', 'size': 1234, 'filename': '...'}, ...]
    """
    s3_path = f"s3://{bucket_name}/{prefix}" if not prefix.endswith("/") else f"s3://{bucket_name}/{prefix}"
    res = run_aws_command(["s3", "ls", s3_path], profile=profile, region=region)
    
    if res.returncode != 0:
        print(f"[Error] Failed to list files in {s3_path}")
        print(f"Error output: {res.stderr}")
        raise RuntimeError(f"AWS CLI command failed: {res.stderr}")
        
    lines = res.stdout.strip().split("\n")
    target_files = []
    
    archive_prefix = archive_folder_name.strip("/") + "/"
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # aws s3 ls output format: YYYY-MM-DD HH:MM:SS    size filename_or_dir
        parts = re.split(r'\s+', line, maxsplit=3)
        if len(parts) < 4:
            continue
            
        date_str, time_str, size_str, filename = parts[0], parts[1], parts[2], parts[3]
        
        # Exclude directories (if size is DIR or PRE)
        if size_str == "PRE" or filename.endswith("/"):
            continue
            
        # Exclude if file is inside the archive folder
        if archive_prefix in filename or filename.startswith(archive_prefix):
            continue
            
        # Exclude if extension doesn't match filter
        if file_extension_filter and not filename.lower().endswith(file_extension_filter.lower()):
            continue
            
        try:
            size_int = int(size_str)
        except ValueError:
            continue
            
        if size_int <= 0:
            print(f"[Warning] Skipping empty file on S3: {filename}")
            continue
            
        full_key = prefix.rstrip("/") + "/" + filename if prefix else filename
        target_files.append({
            "key": full_key,
            "filename": filename,
            "size": size_int,
            "last_modified": f"{date_str} {time_str}"
        })
        
    return target_files

def download_s3_file(
    bucket_name: str,
    s3_key: str,
    dest_path: str,
    profile: Optional[str] = None,
    region: Optional[str] = None
) -> bool:
    """
    Download a single file from S3 to dest_path using aws s3 cp.
    """
    s3_uri = f"s3://{bucket_name}/{s3_key}"
    res = run_aws_command(["s3", "cp", s3_uri, dest_path], profile=profile, region=region)
    
    if res.returncode != 0:
        print(f"[Error] Failed to download {s3_uri}")
        print(f"Error output: {res.stderr}")
        return False
        
    if not os.path.exists(dest_path) or os.path.getsize(dest_path) == 0:
        print(f"[Error] Downloaded file {dest_path} does not exist or is empty.")
        return False
        
    return True

def archive_s3_file(
    bucket_name: str,
    source_key: str,
    archive_folder_name: str,
    append_timestamp: bool = True,
    timestamp_format: str = "_%Y%m%d_%H%M%S",
    profile: Optional[str] = None,
    region: Optional[str] = None
) -> bool:
    """
    Move a file on S3 to the archive folder using aws s3 mv.
    """
    prefix_dir = os.path.dirname(source_key)
    filename = os.path.basename(source_key)
    
    if append_timestamp:
        name_part, ext_part = os.path.splitext(filename)
        ts_str = datetime.now().strftime(timestamp_format)
        archived_filename = f"{name_part}{ts_str}{ext_part}"
    else:
        archived_filename = filename
        
    archive_dir = archive_folder_name.strip("/")
    if prefix_dir:
        dest_key = f"{prefix_dir}/{archive_dir}/{archived_filename}"
    else:
        dest_key = f"{archive_dir}/{archived_filename}"
        
    source_uri = f"s3://{bucket_name}/{source_key}"
    dest_uri = f"s3://{bucket_name}/{dest_key}"
    
    print(f"[Archive] Moving {source_uri} -> {dest_uri}")
    res = run_aws_command(["s3", "mv", source_uri, dest_uri], profile=profile, region=region)
    
    if res.returncode != 0:
        print(f"[Error] Failed to archive file on S3: {res.stderr}")
        return False
        
    return True
