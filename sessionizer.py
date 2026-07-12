from typing import List, Dict, Tuple
from datetime import datetime
from core import Interaction, ResetSession, Manifest

def sessionize(interactions: List[Interaction], manifest: Manifest) -> List[ResetSession]:
    # Group by conversation_id
    conv_groups: Dict[str, List[Interaction]] = {}
    for i in interactions:
        conv_groups.setdefault(i.conversation_id, []).append(i)
        
    all_sessions: List[ResetSession] = []
    
    # Sort conversations (optional but good for stable overall ordering)
    for conv_id in sorted(conv_groups.keys()):
        conv_interactions = conv_groups[conv_id]
        
        # Sort interactions by started_at_utc and then by global_event_no of the first event
        # (Using started_at_utc from interaction or if not present, the order they were processed)
        def sort_key(i: Interaction):
            # Parse started_at_utc if possible
            ts = float('inf')
            if i.started_at_utc:
                try:
                    dt = datetime.fromisoformat(i.started_at_utc)
                    ts = dt.timestamp()
                except ValueError:
                    pass
            
            first_global_event = i.events[0].global_event_no if i.events else float('inf')
            return (ts, first_global_event)
            
        conv_interactions.sort(key=sort_key)
        
        # Sessionize
        session_no = 1
        current_session_interactions: List[Interaction] = []
        interaction_counter = 0
        
        # セッション内でのカテゴリ引き継ぎ用変数
        active_user_selected_cat = ""
        active_inferred_cat = ""
        
        for idx, interaction in enumerate(conv_interactions):
            # カテゴリのセッション内引き継ぎ（フォワードプロパゲーション）
            if interaction.user_selected_categories:
                active_user_selected_cat = interaction.user_selected_categories
            elif active_user_selected_cat:
                interaction.user_selected_categories = active_user_selected_cat
                
            if interaction.inferred_category:
                active_inferred_cat = interaction.inferred_category
            elif active_inferred_cat:
                interaction.inferred_category = active_inferred_cat
                
            # interaction.final_category を引き継ぎ後の値で同期
            if interaction.user_selected_categories:
                interaction.final_category = interaction.user_selected_categories.split(" | ")[-1]
            elif interaction.inferred_category:
                interaction.final_category = interaction.inferred_category

            current_session_interactions.append(interaction)
            
            # Format session id
            session_id = f"{conv_id}-S{session_no:03d}"
            
            # Assign session info to interaction
            interaction.reset_session_id = session_id
            interaction.reset_session_no = session_no
            if interaction.is_command or interaction.interaction_type == "command":
                interaction.interaction_no_in_session = "-"
            else:
                interaction.interaction_no_in_session = interaction_counter
                interaction_counter += 1
            
            # Also backpropagate to raw events
            for e in interaction.events:
                e.reset_session_id = session_id
            
            if interaction.is_reset_request:
                interaction.ends_session_by_reset = True
                
                # Close the session and create ResetSession object
                rs = finalize_session(session_id, conv_id, session_no, current_session_interactions)
                all_sessions.append(rs)
                
                # Start new session
                session_no += 1
                current_session_interactions = []
                interaction_counter = 0
                active_user_selected_cat = ""
                active_inferred_cat = ""
                
        # If there are interactions left in the current session (meaning it didn't end with a reset)
        if current_session_interactions:
            rs = finalize_session(f"{conv_id}-S{session_no:03d}", conv_id, session_no, current_session_interactions)
            all_sessions.append(rs)
            
    manifest.counts["conversation_count"] = len(conv_groups)
    manifest.counts["reset_session_count"] = len(all_sessions)
    
    # Also we need to backpropagate reset_session_id to retrieval results... we'll do that in the orchestrator or here.
    # The normalizer just returns retrieval results which have interaction_key.
    
    return all_sessions

def finalize_session(session_id: str, conv_id: str, session_no: int, interactions: List[Interaction]) -> ResetSession:
    rs = ResetSession(
        reset_session_id=session_id,
        conversation_id=conv_id,
        reset_session_no=session_no,
        team_name=interactions[0].team_name if interactions else "",
        user_name=interactions[0].user_name if interactions else "",
        user_key=interactions[0].user_key if interactions else ""
    )
    
    if not interactions:
        return rs
        
    # Aggregate stats
    valid_utc_starts = [i.started_at_utc for i in interactions if i.started_at_utc]
    valid_utc_ends = [i.ended_at_utc for i in interactions if i.ended_at_utc]
    
    if valid_utc_starts:
        rs.started_at_utc = min(valid_utc_starts)
    if valid_utc_ends:
        rs.ended_at_utc = max(valid_utc_ends)
        
    valid_jst_starts = [i.started_at_jst for i in interactions if i.started_at_jst]
    valid_jst_ends = [i.ended_at_jst for i in interactions if i.ended_at_jst]
    
    if valid_jst_starts:
        rs.started_at_jst = min(valid_jst_starts)
        rs.session_date_jst = min(valid_jst_starts)[:10] # YYYY-MM-DD
    if valid_jst_ends:
        rs.ended_at_jst = max(valid_jst_ends)
        
    if rs.started_at_utc and rs.ended_at_utc:
        try:
            st = datetime.fromisoformat(rs.started_at_utc)
            en = datetime.fromisoformat(rs.ended_at_utc)
            rs.duration_seconds = f"{(en - st).total_seconds():.3f}"
        except ValueError:
            pass
            
    rs.interaction_count = len(interactions)
    rs.natural_question_count = sum(1 for i in interactions if i.is_natural_question)
    rs.category_selection_count = sum(1 for i in interactions if i.is_category_selection)
    rs.command_count = sum(1 for i in interactions if i.is_command)
    rs.reset_request_count = sum(1 for i in interactions if i.is_reset_request)
    rs.tool_interaction_count = sum(1 for i in interactions if i.has_tool)
    rs.no_answer_count = sum(1 for i in interactions if i.is_no_answer)
    rs.unsupported_count = sum(1 for i in interactions if i.is_unsupported)
    rs.error_count = sum(1 for i in interactions if i.has_error)
    rs.feedback_count = sum(1 for i in interactions if i.has_feedback)
    
    # good/bad counts based on rating
    good = 0
    bad = 0
    for i in interactions:
        if i.feedback_rating:
            ratings = i.feedback_rating.split(" | ")
            good += ratings.count("good")
            bad += ratings.count("bad")
            
    rs.good_feedback_count = good
    rs.bad_feedback_count = bad
    
    # If the last interaction is a reset, ended_by_reset = True
    if interactions[-1].ends_session_by_reset:
        rs.ended_by_reset = True
        
    # first/last natural question
    nat_qs = [i.question for i in interactions if i.is_natural_question and i.question]
    if nat_qs:
        rs.first_question = nat_qs[0]
        rs.last_question = nat_qs[-1]
        
    cats = [i.final_category for i in interactions if i.final_category]
    if cats:
        rs.first_category = cats[0]
        rs.last_category = cats[-1]
        
    source_files = set()
    for i in interactions:
        if i.source_files:
            source_files.update(i.source_files.split(" | "))
    rs.source_files = " | ".join(sorted(list(source_files)))
    
    return rs
