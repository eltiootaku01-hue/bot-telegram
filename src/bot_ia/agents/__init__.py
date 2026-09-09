"""Adaptadores de agentes locales; no tienen acceso a providers ni archivos."""

from .adapters import EditorAgent, HistorianAgent, IAChanAgent, ResearcherAgent
from .conversation_policy import ConversationAct, ConversationGuidance, ConversationPolicy
from .models import AgentRequest, AgentResult, AgentStatus, ExternalReference
from .output_contract import ContractValidation, IAChanOutputContract, ResponseType, RuleCheck
from .registry import AgentRegistry
from .rule_hierarchy import PolicyRule, RuleConflict, RuleHierarchy, RulePriority, RuleResolution

__all__ = ["AgentRegistry", "AgentRequest", "AgentResult", "AgentStatus", "ContractValidation", "ConversationAct", "ConversationGuidance", "ConversationPolicy", "EditorAgent", "ExternalReference", "HistorianAgent", "IAChanAgent", "IAChanOutputContract", "PolicyRule", "ResearcherAgent", "ResponseType", "RuleCheck", "RuleConflict", "RuleHierarchy", "RulePriority", "RuleResolution"]
