"""Custom exception hierarchy for TermMind."""

class TermMindError(Exception):
    """Base exception for all TermMind errors."""
    pass

class ConfigError(TermMindError):
    """Configuration-related errors."""
    pass

class ProviderError(TermMindError):
    """LLM provider errors."""
    pass

class ProviderNotFoundError(ProviderError):
    """Provider not found."""
    pass

class ProviderAuthError(ProviderError):
    """Provider authentication failed."""
    pass

class ProviderRateLimitError(ProviderError):
    """Provider rate limit exceeded."""
    pass

class AgentError(TermMindError):
    """Agent-related errors."""
    pass

class WorkflowError(TermMindError):
    """Workflow execution errors."""
    pass

class KnowledgeBaseError(TermMindError):
    """Knowledge base errors."""
    pass

class SecurityError(TermMindError):
    """Security scan errors."""
    pass

class PluginError(TermMindError):
    """Plugin errors."""
    pass

class PluginNotFoundError(PluginError):
    """Plugin not found."""
    pass

class CacheError(TermMindError):
    """Cache errors."""
    pass
