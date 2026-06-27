import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

JST = timezone(timedelta(hours=9), 'JST')

@dataclass
class RawEvent:
    # Original columns
    team_name: str
    conversation_id: str
    message_type: str
    content: str
    user_name: str
    category: str
    similar_records: str
    feedback_rating: str
    feedback_comment: str
    created_at_str: str
    message_id: str

    # Added properties
    global_event_no: int = 0
    event_id: str = ""
    source_file: str = ""
    source_row_number: int = 0
    created_at_utc: Optional[datetime] = None
    created_at_jst: Optional[datetime] = None
    event_date_jst: str = ""
    event_time_jst: str = ""
    interaction_key: str = ""
    reset_session_id: str = ""
    user_key: str = ""

@dataclass
class Interaction:
    interaction_key: str
    message_id: str
    conversation_id: str
    team_name: str
    user_name: str
    user_key: str
    
    events: List[RawEvent] = field(default_factory=list)
    
    interaction_type: str = ""
    question: str = ""
    all_user_messages_json: str = "[]"
    answer: str = ""
    answer_message_type: str = ""
    selected_function: str = ""
    inferred_category: str = ""
    user_selected_categories: str = ""
    final_category: str = ""
    event_sequence: str = ""
    event_count: int = 0
    has_tool: bool = False
    retrieval_count: int = 0
    top_score: str = ""
    similar_records_parse_failures: int = 0
    has_error: bool = False
    error_text: str = ""
    has_feedback: bool = False
    feedback_rating: str = ""
    feedback_comment: str = ""
    
    is_reset_request: bool = False
    is_category_selection: bool = False
    is_command: bool = False
    is_natural_question: bool = False
    is_no_answer: bool = False
    is_unsupported: bool = False
    
    started_at_utc: str = ""
    ended_at_utc: str = ""
    started_at_jst: str = ""
    ended_at_jst: str = ""
    interaction_date_jst: str = ""
    response_latency_seconds: str = ""
    
    source_files: str = ""
    reset_session_no: int = 0
    reset_session_id: str = ""
    interaction_no_in_session: int = 0
    ends_session_by_reset: bool = False

@dataclass
class ResetSession:
    reset_session_id: str
    conversation_id: str
    reset_session_no: int
    team_name: str
    user_name: str
    user_key: str
    started_at_utc: str = ""
    ended_at_utc: str = ""
    started_at_jst: str = ""
    ended_at_jst: str = ""
    session_date_jst: str = ""
    duration_seconds: str = ""
    interaction_count: int = 0
    natural_question_count: int = 0
    category_selection_count: int = 0
    command_count: int = 0
    reset_request_count: int = 0
    ended_by_reset: bool = False
    tool_interaction_count: int = 0
    no_answer_count: int = 0
    unsupported_count: int = 0
    error_count: int = 0
    feedback_count: int = 0
    good_feedback_count: int = 0
    bad_feedback_count: int = 0
    first_question: str = ""
    last_question: str = ""
    first_category: str = ""
    last_category: str = ""
    source_files: str = ""


class Manifest:
    def __init__(self):
        self.generated_at_utc = datetime.utcnow().isoformat() + "Z"
        self.tool_version = "1.0.0"
        self.input_directory = ""
        self.output_directory = ""
        self.anonymize_users = False
        self.strict_mode = False
        self.readable_input_files = []
        self.skipped_input_errors = []
        self.warnings = []
        self.counts = {
            "input_file_count": 0,
            "readable_file_count": 0,
            "skipped_file_count": 0,
            "raw_event_count": 0,
            "interaction_count": 0,
            "conversation_count": 0,
            "reset_session_count": 0,
            "reset_request_count": 0,
            "natural_question_count": 0,
            "tool_interaction_count": 0,
            "no_answer_count": 0,
            "error_interaction_count": 0,
            "feedback_count": 0,
            "retrieval_result_count": 0,
            "message_id_collision_count": 0,
            "datetime_parse_error_count": 0
        }
        self.session_rule = "ユーザー発話が完全一致で『リセット』のinteractionを現セッション末尾に含め、次interactionから新セッション"

    def add_warning(self, message: str):
        self.warnings.append(message)

    def add_skipped_file(self, filename: str, reason: str):
        self.skipped_input_errors.append({"file": filename, "reason": reason})
        self.counts["skipped_file_count"] += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at_utc": self.generated_at_utc,
            "tool_version": self.tool_version,
            "input_directory": self.input_directory,
            "output_directory": self.output_directory,
            "anonymize_users": self.anonymize_users,
            "strict_mode": self.strict_mode,
            "readable_input_files": self.readable_input_files,
            "skipped_input_errors": self.skipped_input_errors,
            "warnings": self.warnings,
            "counts": self.counts,
            "session_rule": self.session_rule
        }

def hash_user_name(user_name: str) -> str:
    if not user_name:
        return ""
    return hashlib.sha256(user_name.encode('utf-8')).hexdigest()[:16]

def bool_to_str(val: bool) -> str:
    return "true" if val else "false"
