"""Provider-independent model interface for agent planning."""

from abc import (
    ABC,
    abstractmethod,
)

from app.services.agentic.contracts import (
    AgentDecision,
    AgentState,
)

from app.services.agentic.tool_registry import (
    ToolSpec,
)


class AgentModelAdapter(ABC):
    """Interface implemented later by Ollama/API providers."""

    @property
    @abstractmethod
    def provider_name(self):
        raise NotImplementedError

    @abstractmethod
    def decide(
        self,
        state: AgentState,
        allowed_tools: list[ToolSpec],
    ) -> AgentDecision:
        """Return one structured decision.

        The adapter receives tool metadata only.
        It does not receive executable Python functions.
        """

        raise NotImplementedError
