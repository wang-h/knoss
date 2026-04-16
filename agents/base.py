"""Base agent class and result types for Knoss agents.

This module provides the foundational Agent abstraction used across all
Knoss knowledge extraction agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


@dataclass
class AgentResult:
    """Standard result type for all agent executions.

    Attributes:
        success: Whether the agent completed successfully
        output: The structured output payload (if successful)
        error: Error message (if failed)
        warnings: Non-blocking warnings discovered during execution
        metadata: Additional metadata about the execution
        executed_at: When the agent execution completed
    """

    success: bool
    output: dict[str, Any] | BaseModel | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_ok(self) -> bool:
        """Alias for success attribute."""
        return self.success

    @property
    def is_error(self) -> bool:
        """Return True if the execution failed."""
        return not self.success

    @classmethod
    def ok(
        cls,
        output: dict[str, Any] | BaseModel,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Create a successful result.

        Args:
            output: The agent's structured output
            warnings: Optional non-blocking warnings
            metadata: Optional execution metadata

        Returns:
            A successful AgentResult
        """
        return cls(
            success=True,
            output=output,
            warnings=warnings or [],
            metadata=metadata or {},
        )

    @classmethod
    def fail(
        cls,
        error: str,
        output: dict[str, Any] | BaseModel | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Create a failed result.

        Args:
            error: Error message describing the failure
            output: Any partial output produced before failure
            warnings: Optional warnings discovered before failure
            metadata: Optional execution metadata

        Returns:
            A failed AgentResult
        """
        return cls(
            success=False,
            output=output,
            error=error,
            warnings=warnings or [],
            metadata=metadata or {},
        )


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Agent(Generic[InputT, OutputT]):
    """Base class for all Knoss agents.

    Agents are stateless transforms that:
    - Consume structured input (Pydantic models)
    - Emit structured output (Pydantic models)
    - Are independently testable
    - Never mutate upstream artifacts

    Subclasses must implement:
        input_model: The Pydantic model for input validation
        output_model: The Pydantic model for output validation
        execute(): The core logic transforming input to output
    """

    input_model: type[InputT]
    output_model: type[OutputT]

    def execute(self, input_data: InputT) -> AgentResult:
        """Execute the agent's core logic.

        Args:
            input_data: Validated input matching input_model schema

        Returns:
            AgentResult with output or error
        """
        raise NotImplementedError("Subclasses must implement execute()")

    def run(self, input_data: dict[str, Any]) -> AgentResult:
        """Run the agent with raw dict input.

        This method validates input against input_model, calls execute(),
        and validates the output against output_model.

        Args:
            input_data: Raw dictionary input to validate

        Returns:
            AgentResult with validated output or validation errors
        """
        # Validate input
        try:
            validated_input = self.input_model.model_validate(input_data)
        except Exception as e:
            return AgentResult.fail(f"Input validation failed: {e}")

        # Execute agent logic
        result = self.execute(validated_input)
        if not result.success:
            return result

        # Validate output
        try:
            is_generic = hasattr(self.output_model, "__origin__")

            if not is_generic and isinstance(result.output, self.output_model):
                pass
            elif isinstance(result.output, dict):
                result.output = self.output_model.model_validate(result.output)
            elif is_generic and isinstance(result.output, list):
                pass
            else:
                return AgentResult.fail(
                    f"Output must be {self.output_model.__name__} or dict, got {type(result.output).__name__}"
                )
        except Exception as e:
            return AgentResult.fail(
                f"Output validation failed: {e}",
                output=result.output,
                warnings=result.warnings,
            )

        return result

    @property
    def name(self) -> str:
        """Return the agent's class name."""
        return self.__class__.__name__


__all__ = ["Agent", "AgentResult", "InputT", "OutputT"]
