from app.agent.gate import AgentGate
from app.agent.llm import LLMClient
from app.agent.mock_model import MockSalesModel
from app.agent.muse import MuseClient
from app.agent.runner import AgentServices
from app.channels.instagram import GraphSender, RecordingSender
from app.config import Settings
from app.payments.checkout import HostedTestCheckout


def build_agent_services(settings: Settings) -> AgentServices:
    llm: LLMClient = MockSalesModel()
    if settings.llm_provider == "muse" and settings.model_api_key is not None:
        llm = MuseClient(
            api_key=settings.model_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    live_sender = (
        GraphSender(
            access_token=settings.instagram_access_token.get_secret_value(),
            graph_url=settings.instagram_graph_url,
        )
        if settings.instagram_access_token is not None
        else None
    )
    return AgentServices(
        llm=llm,
        recorder=RecordingSender(),
        payments=HostedTestCheckout(settings.public_base_url),
        gate=AgentGate(
            max_concurrent_turns=settings.agent_max_concurrent_turns,
            turns_per_contact_per_day=settings.agent_turns_per_contact_per_day,
        ),
        live_sender=live_sender,
        enabled=settings.agent_enabled,
    )
