from typing import Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot produce a usable response.

    Every adapter translates its SDK-specific failure (bad key, timeout, rate
    limit, malformed reply) into this single exception, so the agent layer can
    handle "the model did not answer" without importing any vendor SDK.  This
    keeps the dependency direction pointing at the contract, not at Groq.

    Messages must never contain credentials -- they end up in logs and in
    error responses.
    """


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Provider-independent contract for text generation.

    The architecture requires "a configured external LLM provider through a
    provider-independent interface", so callers depend on this shape rather
    than on any particular vendor.  A local-inference adapter added later
    only has to satisfy this protocol to be a drop-in replacement.
    """

    def generate(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.0
    ) -> str:
        """Return the model's answer to ``user_prompt``.

        ``system_prompt`` sets the role and constraints (for example the
        audit reviewer persona and the rule that it must cite provenance),
        while ``user_prompt`` carries the question and the retrieved
        financial context.

        ``temperature`` defaults to ``0.0`` deliberately.  Audit output has
        to be reproducible and defensible: the same evidence and the same
        question should produce the same answer on every run, so a reviewer
        can re-run a finding and get an identical result, and so that an
        answer can be traced back to the inputs that produced it.  Callers
        should only raise it for explicitly creative tasks such as drafting
        alternative query phrasings.
        """
        ...
