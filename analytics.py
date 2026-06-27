from typing import List, Dict, Any
from core import Interaction, ResetSession, Manifest

def compute_overview(manifest: Manifest) -> List[Dict[str, str]]:
    c = manifest.counts
    data = [
        {"metric": "input_file_count", "value": str(c["input_file_count"]), "definition": "Total CSV files found"},
        {"metric": "readable_file_count", "value": str(c["readable_file_count"]), "definition": "Files successfully parsed"},
        {"metric": "skipped_file_count", "value": str(c["skipped_file_count"]), "definition": "Files skipped due to errors or IRM/OLE"},
        {"metric": "raw_event_count", "value": str(c["raw_event_count"]), "definition": "Total raw events extracted"},
        {"metric": "interaction_count", "value": str(c["interaction_count"]), "definition": "Total interactions created"},
        {"metric": "conversation_count", "value": str(c["conversation_count"]), "definition": "Total unique conversations"},
        {"metric": "reset_session_count", "value": str(c["reset_session_count"]), "definition": "Total sessions after reset boundary division"},
        {"metric": "reset_request_count", "value": str(c["reset_request_count"]), "definition": "Total interactions of type 'reset'"},
        {"metric": "natural_question_count", "value": str(c["natural_question_count"]), "definition": "Total interactions of type 'question'"},
        {"metric": "tool_interaction_count", "value": str(c["tool_interaction_count"]), "definition": "Interactions containing tool events"},
        {"metric": "no_answer_count", "value": str(c["no_answer_count"]), "definition": "Interactions where the bot found no answer"},
        {"metric": "error_interaction_count", "value": str(c["error_interaction_count"]), "definition": "Interactions containing error events"},
        {"metric": "feedback_count", "value": str(c["feedback_count"]), "definition": "Total feedback events"},
        {"metric": "retrieval_result_count", "value": str(c["retrieval_result_count"]), "definition": "Total retrieved similar records extracted"},
        {"metric": "message_id_collision_count", "value": str(c["message_id_collision_count"]), "definition": "Number of message_ids appearing in multiple conversations"},
        {"metric": "datetime_parse_error_count", "value": str(c["datetime_parse_error_count"]), "definition": "Rows with unparsable datetime"},
    ]
    return data

def compute_daily(interactions: List[Interaction]) -> List[Dict[str, Any]]:
    # JST daily aggregations
    daily: Dict[str, Dict[str, Any]] = {}
    
    for i in interactions:
        d = i.interaction_date_jst
        if not d:
            d = "(unknown_date)"
            
        if d not in daily:
            daily[d] = {
                "interaction_date_jst": d,
                "interaction_count": 0,
                "natural_question_count": 0,
                "reset_request_count": 0,
                "tool_interaction_count": 0,
                "no_answer_count": 0,
                "error_count": 0,
                "feedback_count": 0,
                "sum_latency": 0.0,
                "latency_count": 0
            }
            
        daily[d]["interaction_count"] += 1
        if i.is_natural_question:
            daily[d]["natural_question_count"] += 1
        if i.is_reset_request:
            daily[d]["reset_request_count"] += 1
        if i.has_tool:
            daily[d]["tool_interaction_count"] += 1
        if i.is_no_answer:
            daily[d]["no_answer_count"] += 1
        if i.has_error:
            daily[d]["error_count"] += 1
        if i.has_feedback:
            daily[d]["feedback_count"] += 1
            
        if i.response_latency_seconds:
            try:
                val = float(i.response_latency_seconds)
                daily[d]["sum_latency"] += val
                daily[d]["latency_count"] += 1
            except ValueError:
                pass
                
    result = []
    for d in sorted(daily.keys()):
        row = daily[d]
        nq = row["natural_question_count"]
        row["no_answer_rate"] = f"{(row['no_answer_count'] / nq):.3f}" if nq > 0 else "0.000"
        row["avg_latency_seconds"] = f"{(row['sum_latency'] / row['latency_count']):.3f}" if row["latency_count"] > 0 else ""
        
        # clean up intermediate metrics
        del row["sum_latency"]
        del row["latency_count"]
        
        result.append(row)
        
    return result

def compute_category(interactions: List[Interaction]) -> List[Dict[str, Any]]:
    cat_agg: Dict[str, Dict[str, Any]] = {}
    
    # Only natural_question
    for i in interactions:
        if not i.is_natural_question:
            continue
            
        c = i.final_category if i.final_category else "(カテゴリなし)"
        
        if c not in cat_agg:
            cat_agg[c] = {
                "final_category": c,
                "natural_question_count": 0,
                "tool_interaction_count": 0,
                "no_answer_count": 0,
                "error_count": 0,
                "good_feedback_count": 0,
                "bad_feedback_count": 0
            }
            
        row = cat_agg[c]
        row["natural_question_count"] += 1
        if i.has_tool:
            row["tool_interaction_count"] += 1
        if i.is_no_answer:
            row["no_answer_count"] += 1
        if i.has_error:
            row["error_count"] += 1
            
        if i.feedback_rating:
            ratings = i.feedback_rating.split(" | ")
            row["good_feedback_count"] += ratings.count("good")
            row["bad_feedback_count"] += ratings.count("bad")
            
    result = []
    for c in sorted(cat_agg.keys()):
        row = cat_agg[c]
        nq = row["natural_question_count"]
        row["no_answer_rate"] = f"{(row['no_answer_count'] / nq):.3f}" if nq > 0 else "0.000"
        
        result.append(row)
        
    return result

def compute_session_distribution(sessions: List[ResetSession]) -> List[Dict[str, Any]]:
    dist: Dict[int, int] = {}
    
    for s in sessions:
        nq = s.natural_question_count
        dist[nq] = dist.get(nq, 0) + 1
        
    result = []
    for nq in sorted(dist.keys()):
        result.append({
            "natural_questions_per_session": nq,
            "session_count": dist[nq]
        })
        
    return result

def collect_feedback_events(interactions: List[Interaction]) -> List[Dict[str, str]]:
    result = []
    
    for i in interactions:
        # filter feedback events from raw events in interaction
        for e in i.events:
            if e.message_type == 'feedback':
                result.append({
                    "event_id": e.event_id,
                    "interaction_key": i.interaction_key,
                    "message_id": i.message_id,
                    "conversation_id": i.conversation_id,
                    "reset_session_id": i.reset_session_id,
                    "user_name": e.user_name,
                    "user_key": e.user_key,
                    "feedback_rating": e.feedback_rating,
                    "feedback_comment": e.feedback_comment,
                    "feedback_at_utc": e.created_at_utc.strftime('%Y-%m-%dT%H:%M:%S+00:00') if e.created_at_utc else "",
                    "feedback_at_jst": e.created_at_jst.strftime('%Y-%m-%dT%H:%M:%S+09:00') if e.created_at_jst else "",
                    "source_file": e.source_file
                })
    return result
