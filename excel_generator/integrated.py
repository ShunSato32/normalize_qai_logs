import os
import json
from typing import List, Dict, Any, Tuple
from core import Interaction, ResetSession, Manifest, bool_to_str, JST
from normalizer import safe_parse_similar_records

_CACHED_CATEGORY_MAP = None
_CACHED_TOP_LEVELS = None

def _get_category_tree_map() -> Tuple[List[str], Dict[str, str]]:
    global _CACHED_CATEGORY_MAP, _CACHED_TOP_LEVELS
    if _CACHED_CATEGORY_MAP is not None and _CACHED_TOP_LEVELS is not None:
        return _CACHED_TOP_LEVELS, _CACHED_CATEGORY_MAP
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    paths = [
        os.path.join(project_root, "config", "target_categories.json"),
        os.path.join(script_dir, "config", "target_categories.json"),
        "config/target_categories.json"
    ]
    
    cat_data = []
    config_path = None
    for p in paths:
        if os.path.exists(p):
            config_path = p
            break
            
    if not config_path:
        # Try template fallbacks
        for p in paths:
            dir_name = os.path.dirname(p)
            base_name = os.path.basename(p)
            name, ext = os.path.splitext(base_name)
            template_path = os.path.join(dir_name, f"{name}_template{ext}")
            if os.path.exists(template_path):
                try:
                    import shutil
                    os.makedirs(dir_name, exist_ok=True)
                    shutil.copyfile(template_path, p)
                    print(f"Initialized active config file from template: {p}")
                    config_path = p
                    break
                except Exception as e:
                    import sys
                    print(f"Warning: Failed to copy template {template_path} to {p}: {e}", file=sys.stderr)
                    config_path = template_path
                    break
                    
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cat_data = json.load(f)
        except Exception:
            pass
                
    top_levels = []
    node_to_top = {}
    
    def traverse(node: Dict[str, Any], top_level: str, current_path: List[str]):
        name = node.get("name", "").strip()
        if not name:
            return
        path_list = current_path + [name]
        path_str = " > ".join(path_list)
        
        node_to_top[name] = top_level
        node_to_top[path_str] = top_level
        node_to_top["/".join(path_list)] = top_level
        node_to_top[" | ".join(path_list)] = top_level
        
        for child in node.get("children", []):
            traverse(child, top_level, path_list)
            
    for root_node in cat_data:
        r_name = root_node.get("name", "").strip()
        if r_name:
            top_levels.append(r_name)
            traverse(root_node, r_name, [])
            
    _CACHED_TOP_LEVELS = top_levels
    _CACHED_CATEGORY_MAP = node_to_top
    return top_levels, node_to_top

def resolve_first_category_from_tree(cat_str: str) -> str:
    if not cat_str or cat_str == "未分類":
        return "未分類"
        
    top_levels, node_to_top = _get_category_tree_map()
    
    # 1. Exact match in top level list
    if cat_str in top_levels:
        return cat_str
        
    # 2. Check if starts with a known top level followed by separator
    for tl in top_levels:
        for sep in [" > ", " >", "> ", ">", "/", " | ", "｜"]:
            if cat_str.startswith(tl + sep):
                return tl
                
    # 3. Exact match in full tree node map
    if cat_str in node_to_top:
        return node_to_top[cat_str]
        
    # 4. Try leaf segment or parts
    for sep in [" > ", " >", "> ", ">", "/", " | ", "｜"]:
        if sep in cat_str:
            parts = [p.strip() for p in cat_str.split(sep) if p.strip()]
            # Try leaf first
            if parts and parts[-1] in node_to_top:
                return node_to_top[parts[-1]]
            # Try first part
            if parts and parts[0] in node_to_top:
                return node_to_top[parts[0]]
                
    # 5. Fallback to simple split if no tree match found
    first_part = cat_str.split(" > ")[0].strip()
    if first_part in top_levels or first_part in node_to_top:
        return node_to_top.get(first_part, first_part)
        
    return first_part if first_part else "未分類"

def build_integrated_rows(
    interactions: List[Interaction],
    sessions: List[ResetSession],
    manifest: Manifest
) -> List[Dict[str, Any]]:
    # Map reset_session_id to session details
    session_map: Dict[str, ResetSession] = {s.reset_session_id: s for s in sessions}
    
    integrated_rows: List[Dict[str, Any]] = []
    
    for i in interactions:
        # 1. Extract session metadata
        session = session_map.get(i.reset_session_id)
        session_date_jst = session.session_date_jst if session else ""
        
        # 2. Extract and parse retrieval results from tool events
        tool_events = [e for e in i.events if e.message_type == 'tool']
        all_parsed_records = []
        for te in tool_events:
            if te.similar_records:
                parsed = safe_parse_similar_records(te.similar_records)
                if parsed:
                    all_parsed_records.extend(parsed)
                    
        retrieval_count = len(all_parsed_records)
        has_retrieval = "true" if retrieval_count > 0 else "false"
        retrieval_stored_count = min(retrieval_count, 10)
        retrieval_truncated = 1 if retrieval_count > 10 else 0
        
        normalization_warnings = []
        if retrieval_count > 10:
            warn_msg = f"Interaction {i.interaction_key} has {retrieval_count} retrieval results, which exceeds the limit of 10. Truncating to 10."
            manifest.add_warning(warn_msg)
            normalization_warnings.append("similar_records truncated to 10")
            
        if all_parsed_records:
            first_rec = all_parsed_records[0]
            first_metadata = first_rec.get("metadata", {})
            top_retrieval_score = str(first_rec.get("score", ""))
            top_retrieval_filename = first_metadata.get("filename") or first_metadata.get("fileName") or first_metadata.get("display_name") or ""
        else:
            top_retrieval_score = ""
            top_retrieval_filename = ""
            
        # Build retrieval columns retrieval_01 to retrieval_10
        retrieval_cols = {}
        for idx in range(10):
            col_name = f"retrieval_{idx+1:02d}"
            if idx < len(all_parsed_records):
                rec = all_parsed_records[idx]
                metadata = rec.get("metadata", {})
                filename = metadata.get("filename") or metadata.get("fileName") or metadata.get("display_name") or ""
                col_data = {
                    "rank": idx + 1,
                    "score": rec.get("score"),
                    "filename": filename,
                    "categories": metadata.get("categories", []),
                    "content": rec.get("content", ""),
                    "metadata": metadata
                }
                retrieval_cols[col_name] = json.dumps(col_data, ensure_ascii=False)
            else:
                retrieval_cols[col_name] = ""
                
        # 3. Extract and sort feedback events
        feedback_events = [e for e in i.events if e.message_type == 'feedback']
        
        def sort_key(e):
            ts = e.created_at_utc.timestamp() if e.created_at_utc else float('inf')
            return (ts, e.global_event_no)
            
        feedback_events.sort(key=sort_key)
        feedback_count = len(feedback_events)
        
        # 4. Generate rows based on feedback count
        row_templates = []
        
        if not feedback_events:
            # Case: 0 feedback
            row_templates.append({
                "feedback_id": "",
                "feedback_seq": 0,
                "feedback_count": 0,
                "is_latest_feedback": 0,
                "is_first_interaction_row": 1,
                "feedback_rating": "未設定",
                "feedback_comment": "",
                "feedback_at_utc": "",
                "feedback_at_jst": ""
            })
        else:
            # Case: 1 or more feedbacks
            for idx, fb in enumerate(feedback_events):
                fb_at_utc = fb.created_at_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00') if fb.created_at_utc else ""
                fb_at_jst = fb.created_at_jst.strftime('%Y-%m-%dT%H:%M:%S+09:00') if fb.created_at_jst else ""
                fb_seq = idx + 1
                rating_str = fb.feedback_rating or ""
                rating_clean = rating_str.strip().lower()
                rating_display = rating_str if rating_clean in ("good", "bad") else "未設定"
                row_templates.append({
                    "feedback_id": f"{i.interaction_key}-FB{fb_seq:03d}",
                    "feedback_seq": fb_seq,
                    "feedback_count": feedback_count,
                    "is_latest_feedback": 1 if fb_seq == feedback_count else 0,
                    "is_first_interaction_row": 1 if idx == 0 else 0,
                    "feedback_rating": rating_display,
                    "feedback_comment": fb.feedback_comment or "",
                    "feedback_at_utc": fb_at_utc,
                    "feedback_at_jst": fb_at_jst
                })
                
        # Collect rich warnings checklist
        has_empty_msg_id = any(not getattr(e, 'message_id', '') or getattr(e, 'message_id', '').startswith('UNKNOWN_MSG_') for e in i.events)
        if has_empty_msg_id:
            normalization_warnings.append("message_id is empty")
            
        has_empty_conv_id = any(not getattr(e, 'conversation_id', '') or getattr(e, 'conversation_id', '').startswith('UNKNOWN_CONV_') for e in i.events)
        if has_empty_conv_id:
            normalization_warnings.append("conversation_id is empty")
            
        has_unparseable_dt = any(e.created_at_utc is None for e in i.events)
        if has_unparseable_dt:
            normalization_warnings.append("created_at is unparseable")
            
        if getattr(i, 'similar_records_parse_failures', 0) > 0:
            normalization_warnings.append("similar_records is unparseable")
            
        user_queries = [e.content for e in i.events if e.message_type == 'user' and e.content and e.content != "[カテゴリ選択]" and e.content != "リセット"]
        if len(set(user_queries)) > 1:
            normalization_warnings.append("multiple user queries")
            
        assist_answers = [e.content for e in i.events if e.message_type == 'assistant' and e.content and not e.content.startswith("[選択された関数]") and e.content != "[カテゴリ選択]"]
        if not assist_answers and not i.is_reset_request and not i.is_category_selection:
            normalization_warnings.append("no answer found")
            
        fb_dates = [e.created_at_utc for e in feedback_events]
        if any(d is None for d in fb_dates):
            normalization_warnings.append("feedback date is empty")
            
        # check duplicate feedback (same timestamp)
        if len(fb_dates) != len(set(fb_dates)):
            normalization_warnings.append("duplicate feedback suspected")
            
        unknown_types = [e.message_type for e in i.events if e.message_type not in ('user', 'assistant', 'tool', 'feedback', 'error')]
        if unknown_types:
            normalization_warnings.append("unknown message type")
            
        if '-' in i.interaction_key and len(i.interaction_key.split('-')[-1]) == 2 and i.interaction_key.split('-')[-1].isdigit():
            # if has trailing sequence, it indicates a chronological collision split
            normalization_warnings.append("multiple independent processes suspected")
            
        # Determine final category priority rules
        user_sel = i.user_selected_categories
        pred_cat = i.inferred_category
        if user_sel:
            final_cat = user_sel.split(" | ")[-1]
            cat_src = "user_selected"
        elif pred_cat:
            final_cat = pred_cat
            cat_src = "predicted"
        else:
            final_cat = "未分類"
            cat_src = "none"
        is_unclassified = 1 if final_cat == "未分類" else 0
        
        # Segment predicted category to first level using target_categories.json mapping
        if final_cat == "未分類":
            pred_cat_out = "未分類"
            first_category = "未分類"
        else:
            pred_cat_out = pred_cat
            first_category = resolve_first_category_from_tree(pred_cat or final_cat)
            
        # Determine user query extract variables
        is_nat_q = 1 if i.interaction_type == "question" else 0
        is_reset = 1 if i.interaction_type == "reset" else 0
        is_cat_sel = 1 if i.interaction_type == "category_selection" else 0
        is_sys_cmd = 1 if i.interaction_type == "command" else 0
        
        # 5. Populate and merge rows
        for t in row_templates:
            fb_seq = t["feedback_seq"]
            output_row_id = f"{i.interaction_key}-FB{fb_seq:03d}"
            is_first = (t["is_first_interaction_row"] == 1)
            
            if not is_first:
                qa_class = ""
                target_str = ""
            elif is_sys_cmd:
                qa_class = "④集計対象外"
                target_str = "×"
            elif i.is_no_answer:
                qa_class = "①該当無"
                target_str = "◯"
            else:
                qa_class = "⑤その他"
                target_str = "◯"
            
            row = {
                "unique_row_id": output_row_id,
                "interaction_id": i.interaction_key,
                "message_id": i.message_id,
                "conversation_id": i.conversation_id,
                "reset_session_id": i.reset_session_id,
                "reset_session_no": i.reset_session_no,
                "interaction_no_in_session": i.interaction_no_in_session,
                "is_first_interaction_row": t["is_first_interaction_row"],
                
                # User and Query fields
                "user_name": i.user_name,
                "team_name": i.team_name,
                "question": i.question if is_first else "[追加評価]",
                "user_content_raw": i.question if is_first else "",
                "is_natural_language_query": is_nat_q if is_first else 0,
                "is_reset_request": is_reset if is_first else 0,
                "is_category_selection": is_cat_sel if is_first else 0,
                "is_system_command": is_sys_cmd if is_first else 0,
                
                # Datetimes & Latency
                "started_at_jst": i.started_at_jst if is_first else "",
                "completed_at_jst": i.ended_at_jst if is_first else "",
                "latency_sec": i.response_latency_seconds if is_first else "",
                
                # Category Processing
                "selected_function": i.selected_function if is_first else "",
                "predicted_category": pred_cat_out if is_first else "",
                "user_selected_category": i.user_selected_categories if is_first else "",
                "fist_category": first_category if is_first else "",
                "final_category": final_cat if is_first else "",
                "category_source": cat_src if is_first else "",
                "is_unclassified": is_unclassified if is_first else 0,
                "qa_classification": qa_class,
                "is_target": target_str,
                
                # Answer & Errors
                "answer": i.answer if is_first else "",
                "has_answer": (1 if i.answer else 0) if is_first else 0,
                "is_no_answer": (1 if i.is_no_answer else 0) if is_first else 0,
                "assistant_event_count": sum(1 for e in i.events if e.message_type == 'assistant') if is_first else 0,
                "has_error": (1 if i.has_error else 0) if is_first else 0,
                "error_count": sum(1 for e in i.events if e.message_type == 'error') if is_first else 0,
                "error_message": i.error_text if is_first else "",
                
                # Retrieval counts
                "has_retrieval": has_retrieval if is_first else "false",
                "retrieval_count": retrieval_count if is_first else 0,
                "retrieval_stored_count": retrieval_stored_count if is_first else 0,
                "retrieval_truncated": retrieval_truncated if is_first else 0,
                "top_retrieval_score": top_retrieval_score if is_first else "",
                "top_retrieval_filename": top_retrieval_filename if is_first else "",
                
                # Feedback specific fields
                "feedback_id": t["feedback_id"],
                "feedback_seq": fb_seq,
                "feedback_count": t["feedback_count"],
                "feedback_rating": t["feedback_rating"],
                "feedback_comment": t["feedback_comment"],
                "feedback_at_utc": t["feedback_at_utc"],
                "feedback_at_jst": t["feedback_at_jst"],
                "is_latest_feedback": t["is_latest_feedback"],
                
                # Session and traceability
                "session_ends_with_reset": (1 if (session and session.ended_by_reset) else 0) if is_first else 0,
                "source_files": i.source_files,
                "source_event_row_count": i.event_count if is_first else 0,
                "source_event_types": i.event_sequence if is_first else "",
                "normalization_version": manifest.tool_version,
                "normalization_warnings": " | ".join(normalization_warnings) if is_first else ""
            }
            
            # Merge retrieval_01 to retrieval_10 (JSON serialization logic for raw csv)
            if is_first:
                row.update(retrieval_cols)
            else:
                # Add empty retrieval columns
                empty_retrieval = {f"retrieval_{idx+1:02d}": "" for idx in range(10)}
                row.update(empty_retrieval)
            integrated_rows.append(row)
            
    return integrated_rows
