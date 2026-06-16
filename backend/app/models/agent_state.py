from typing import TypedDict, List, Dict, Optional, Literal, Any, Annotated
import operator
from enum import Enum


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    RESEARCHER = "researcher"
    INTEGRATOR = "integrator"
    WRITER = "writer"
    REVIEWER_ACCURACY = "reviewer_accuracy"
    REVIEWER_READABILITY = "reviewer_readability"
    ARBITER = "arbiter"
    EDITOR = "editor"
    LINKER = "linker"


class CompilationState(TypedDict, total=False):
    # Input
    memo_ids: List[str]
    memos_content: List[str]
    compilation_config: Dict
    _model_config: Dict
    job_id: str

    # L0
    memo_groups: List[List[str]]
    group_results: List[Dict]
    # L1
    research_results: List[Dict]
    integrated_knowledge: Dict
    # L2
    wiki_draft: str
    wiki_structure: Dict
    # L3
    reviews: Annotated[List[Dict], operator.add]
    arbitration_result: Dict
    final_score: float
    review_passed: bool
    # L4
    revision_count: int
    wiki_revised: str
    suggested_links: List[Dict]
    # Output
    final_wiki: str
    compilation_log: List[Dict]
    # Control
    current_layer: str
    current_agent: AgentRole
    next_action: Literal["continue", "revise", "finish"]
    human_reviewed: bool
