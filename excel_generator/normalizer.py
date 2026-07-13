import ast
import json
import os
import re
from typing import List, Dict, Tuple, Any

from core import RawEvent, Interaction, Manifest, JST

def load_classification_rules(config_path: str = "config/system_commands.json") -> Dict[str, List[str]]:
    defaults = {
        "system_commands": ["カテゴリ", "こんにちは", "ヘルプ", "<at>YourNavi-QAI_Docomo</at>", "テスト"],
        "no_answer_phrases": ["ご質問の内容に関する情報が見つかりませんでした"],
        "unsupported_phrases": ["お答えできません"]
    }
    paths_to_check = [
        config_path,
        os.path.join(os.path.dirname(os.path.abspath(__file__)), config_path),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_path)
    ]
    for path in paths_to_check:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return {
                            "system_commands": data.get("system_commands", defaults["system_commands"]),
                            "no_answer_phrases": data.get("no_answer_phrases", defaults["no_answer_phrases"]),
                            "unsupported_phrases": data.get("unsupported_phrases", defaults["unsupported_phrases"])
                        }
                    elif isinstance(data, list):
                        return {
                            "system_commands": data,
                            "no_answer_phrases": defaults["no_answer_phrases"],
                            "unsupported_phrases": defaults["unsupported_phrases"]
                        }
            except Exception:
                pass
    return defaults

def load_system_commands(config_path: str = "config/system_commands.json") -> List[str]:
    return load_classification_rules(config_path)["system_commands"]

def load_no_answer_phrases(config_path: str = "config/system_commands.json") -> Dict[str, List[str]]:
    rules = load_classification_rules(config_path)
    return {
        "no_answer_phrases": rules["no_answer_phrases"],
        "unsupported_phrases": rules["unsupported_phrases"]
    }

def sort_events(events: List[RawEvent]) -> List[RawEvent]:
    # 1. created_at UTC (if None, push to end but keep stable relative order)
    # 2. source_file
    # 3. source_row_number
    
    def sort_key(e: RawEvent):
        # We use a large timestamp for None to push it to the end
        ts = e.created_at_utc.timestamp() if e.created_at_utc else float('inf')
        return (ts, e.source_file, e.source_row_number)
        
    return sorted(events, key=sort_key)

def extract_selected_functions(content: str) -> str:
    matches = re.findall(r'\[選択された関数\]\[(.*?)\]', content)
    # Deduplicate while preserving order
    seen = set()
    result = []
    for m in matches:
        if m not in seen:
            seen.add(m)
            result.append(m)
    return " | ".join(result)

def safe_parse_similar_records(records_str: str) -> List[Dict[str, Any]]:
    if not records_str:
        return []
    
    try:
        parsed = ast.literal_eval(records_str)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
        
    try:
        parsed = json.loads(records_str)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
        
    return None # Indicates parsing failure


def assign_unique_interaction_keys(events: List[RawEvent]):
    # events are sorted chronologically
    active_keys = {}
    for e in events:
        conv_id = e.conversation_id
        msg_id = e.message_id
        key = (conv_id, msg_id)
        if key not in active_keys:
            active_keys[key] = (1, False)
        
        seq, has_assistant = active_keys[key]
        
        # If we see a user event, and the current interaction already had an assistant event,
        # start a new interaction.
        if e.message_type == 'user' and has_assistant:
            seq += 1
            has_assistant = False
            active_keys[key] = (seq, has_assistant)
            
        if e.message_type == 'assistant':
            has_assistant = True
            active_keys[key] = (seq, has_assistant)
            
        if seq == 1:
            e.interaction_key = f"{conv_id}-{msg_id}"
        else:
            e.interaction_key = f"{conv_id}-{msg_id}-{seq:02d}"

def normalize_events(events: List[RawEvent], manifest: Manifest) -> Tuple[List[Interaction], List[Dict[str, Any]]]:
    # Load system commands and response flags keywords from config files
    cmd_list = load_system_commands()
    response_phrases = load_no_answer_phrases()
    no_answer_list = response_phrases.get("no_answer_phrases", [])
    unsupported_list = response_phrases.get("unsupported_phrases", [])
    
    
    # Sort globally
    events = sort_events(events)
    
    # Assign global_event_no
    for i, e in enumerate(events, start=1):
        e.global_event_no = i
        
    manifest.counts["raw_event_count"] = len(events)
    
    # Assign unique chronological interaction keys (formats conversation_id-message_id[-seq])
    assign_unique_interaction_keys(events)
    
    # Group by interaction_key
    grouped: Dict[str, List[RawEvent]] = {}
    for e in events:
        grouped.setdefault(e.interaction_key, []).append(e)
        
    interactions: List[Interaction] = []
    retrieval_results: List[Dict[str, Any]] = []
    
    for interaction_key, i_events in grouped.items():
        # Check for message_id collision (same message_id, different conversation_id)
        # By definition, interaction_key includes conversation_id, so if multiple conversation_ids existed for a message_id,
        # they will be split into different interaction_keys. 
        # But we need to track if we see the same message_id across different conversations.
        
        i_events = sort_events(i_events) # already sorted globally, but sorting again for safety
        
        first_event = i_events[0]
        
        # Check if conversation_ids are mixed in this interaction (should not happen due to grouping by key, but good to check)
        conv_ids = set(e.conversation_id for e in i_events)
        if len(conv_ids) > 1:
            manifest.add_warning(f"Multiple conversation_ids in interaction {interaction_key}")
            
        interaction = Interaction(
            interaction_key=interaction_key,
            message_id=first_event.message_id,
            conversation_id=first_event.conversation_id,
            team_name=first_event.team_name,
            user_name="", # to be populated
            user_key="",
            events=i_events
        )
        
        user_names = []
        user_keys = []
        questions = []
        answers = []
        answer_types = []
        categories = []
        user_selected_cats = []
        inferred_category = ""
        
        selected_funcs = []
        feedback_ratings = []
        feedback_comments = []
        
        seq = []
        has_tool = False
        has_error = False
        has_feedback = False
        
        for e in i_events:
            seq.append(e.message_type)
            
            if e.user_name and e.user_name not in user_names:
                user_names.append(e.user_name)
            if e.user_key and e.user_key not in user_keys:
                user_keys.append(e.user_key)
                
            if e.category:
                categories.append(e.category)
                
            if e.message_type == 'user':
                if e.content:
                    questions.append(e.content)
                if e.category and e.content == "[カテゴリ選択]":
                    if e.category not in user_selected_cats:
                        user_selected_cats.append(e.category)
                        
            elif e.message_type == 'assistant':
                # Check for internal logs
                if e.content.startswith("[選択された関数]"):
                    funcs = extract_selected_functions(e.content)
                    if funcs:
                        selected_funcs.extend(funcs.split(" | "))
                elif e.content == "[カテゴリ選択]":
                    if e.category:
                        inferred_category = e.category
                elif e.content:
                    answers.append(e.content)
                    answer_types.append(e.message_type)
                    
            elif e.message_type == 'tool':
                has_tool = True
                
                # Parse similar_records
                if e.similar_records:
                    parsed = safe_parse_similar_records(e.similar_records)
                    if parsed is None:
                        interaction.similar_records_parse_failures += 1
                        manifest.counts["datetime_parse_error_count"] += 0 # Just a placeholder if we wanted to count parsing errors
                        manifest.add_warning(f"similar_records parse failure at {e.event_id}")
                    else:
                        for rank, rec in enumerate(parsed, start=1):
                            metadata = rec.get("metadata", {})
                            cats = metadata.get("categories", [])
                            cat_str = " > ".join([c for c in cats if c]) if isinstance(cats, list) else str(cats)
                            
                            score = rec.get("score", "")
                            if score != "" and interaction.top_score == "":
                                interaction.top_score = str(score)
                            
                            rr = {
                                "interaction_key": interaction_key,
                                "message_id": e.message_id,
                                "conversation_id": e.conversation_id,
                                "reset_session_id": "", # to be filled later
                                "tool_event_id": e.event_id,
                                "rank_in_tool_event": rank,
                                "score": score,
                                "retrieved_content": rec.get("content", ""),
                                "filename": metadata.get("filename") or metadata.get("fileName") or metadata.get("display_name") or "",
                                "display_name": metadata.get("display_name", ""),
                                "filetype": metadata.get("filetype", ""),
                                "metadata_categories": cat_str,
                                "category_depth": metadata.get("category_depth", ""),
                                "is_qa": bool_to_str(metadata.get("is_qa", False)),
                                "can_open": bool_to_str(metadata.get("can_open", False)),
                                "uploaded_at": metadata.get("uploaded_at", ""),
                                "metadata_id": metadata.get("id", ""),
                                "collection_name": metadata.get("_collection_name", ""),
                                "source_file": e.source_file
                            }
                            retrieval_results.append(rr)
                            interaction.retrieval_count += 1
                            
            elif e.message_type == 'feedback':
                has_feedback = True
                if e.feedback_rating:
                    feedback_ratings.append(e.feedback_rating)
                if e.feedback_comment:
                    feedback_comments.append(e.feedback_comment)
                    
            elif e.message_type == 'error':
                has_error = True
                if e.content:
                    if interaction.error_text:
                        interaction.error_text += "\n" + e.content
                    else:
                        interaction.error_text = e.content

        interaction.user_name = " | ".join(user_names)
        interaction.user_key = " | ".join(user_keys)
        interaction.event_sequence = " > ".join(seq)
        interaction.event_count = len(i_events)
        interaction.has_tool = has_tool
        interaction.has_error = has_error
        interaction.has_feedback = has_feedback
        
        if feedback_ratings:
            interaction.feedback_rating = " | ".join(feedback_ratings)
        if feedback_comments:
            interaction.feedback_comment = " | ".join(feedback_comments)
            
        if questions:
            interaction.question = questions[0]
            import json
            interaction.all_user_messages_json = json.dumps(questions, ensure_ascii=False)
            
        if answers:
            interaction.answer = answers[-1]
            interaction.answer_message_type = answer_types[-1]
            
        if selected_funcs:
            # deduplicate and preserve order
            seen = set()
            sf = []
            for f in selected_funcs:
                if f not in seen:
                    seen.add(f)
                    sf.append(f)
            interaction.selected_function = " | ".join(sf)
            
        interaction.inferred_category = inferred_category
        interaction.user_selected_categories = " | ".join(user_selected_cats)
        if categories:
            interaction.final_category = categories[-1]
            
        # Determine Interaction Type
        q_trim = interaction.question.strip()
        
        if has_feedback and not questions:
            interaction.interaction_type = "feedback_only"
        elif q_trim in cmd_list:
            interaction.interaction_type = "command"
            interaction.is_command = True
            if q_trim in ("リセット", "[リセット]"):
                interaction.is_reset_request = True
            elif q_trim == "[カテゴリ選択]":
                interaction.is_category_selection = True
        elif q_trim in ("リセット", "[リセット]"):
            interaction.interaction_type = "reset"
            interaction.is_reset_request = True
        elif q_trim == "[カテゴリ選択]":
            interaction.interaction_type = "category_selection"
            interaction.is_category_selection = True
        elif q_trim != "":
            interaction.interaction_type = "question"
            interaction.is_natural_question = True
        else:
            interaction.interaction_type = "system_or_orphan"
            
        if any(phrase in interaction.answer for phrase in no_answer_list if phrase):
            interaction.is_no_answer = True
        if any(phrase in interaction.answer for phrase in unsupported_list if phrase):
            interaction.is_unsupported = True
            
        # Times and Latency
        valid_dts_utc = [e.created_at_utc for e in i_events if e.created_at_utc]
        non_feedback_dts = [e.created_at_utc for e in i_events if e.created_at_utc and e.message_type != 'feedback']
        
        if valid_dts_utc:
            started_dt = min(valid_dts_utc)
            ended_dt = max(non_feedback_dts) if non_feedback_dts else max(valid_dts_utc)
            
            interaction.started_at_utc = started_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            interaction.ended_at_utc = ended_dt.strftime('%Y-%m-%dT%H:%M:%S+00:00')
            
            st_jst = started_dt.astimezone(JST)
            en_jst = ended_dt.astimezone(JST)
            interaction.started_at_jst = st_jst.strftime('%Y-%m-%dT%H:%M:%S+09:00')
            interaction.ended_at_jst = en_jst.strftime('%Y-%m-%dT%H:%M:%S+09:00')
            interaction.interaction_date_jst = st_jst.strftime('%Y-%m-%d')
            
            # Latency is completed_at_utc - started_at_utc
            latency = (ended_dt - started_dt).total_seconds()
            if latency < 0:
                manifest.add_warning(f"Negative latency for {interaction_key}: {latency}s")
                interaction.response_latency_seconds = ""
            else:
                interaction.response_latency_seconds = f"{latency:.3f}"
            
        source_files = list(set([e.source_file for e in i_events]))
        interaction.source_files = " | ".join(sorted(source_files))
        
        if interaction.is_reset_request:
            manifest.counts["reset_request_count"] += 1
        if interaction.is_natural_question:
            manifest.counts["natural_question_count"] += 1
        if interaction.has_tool:
            manifest.counts["tool_interaction_count"] += 1
        if interaction.is_no_answer:
            manifest.counts["no_answer_count"] += 1
        if interaction.has_error:
            manifest.counts["error_interaction_count"] += 1
            
        interactions.append(interaction)
        
    manifest.counts["interaction_count"] = len(interactions)
    manifest.counts["retrieval_result_count"] = len(retrieval_results)
    
    # message_id collision check
    msg_to_conv = {}
    for i in interactions:
        msg_to_conv.setdefault(i.message_id, set()).add(i.conversation_id)
        
    collisions = 0
    for msg, convs in msg_to_conv.items():
        if len(convs) > 1:
            collisions += 1
            manifest.add_warning(f"message_id collision: {msg} found in conversations {convs}")
            
    manifest.counts["message_id_collision_count"] = collisions
    
    return interactions, retrieval_results

def bool_to_str(val: bool) -> str:
    return "true" if val else "false"
