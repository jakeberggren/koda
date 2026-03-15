from koda.sessions import Session as CoreSession
from koda_service.types.sessions import SessionInfo


def map_session_to_session_info(core_session: CoreSession) -> SessionInfo:
    """Map core session to contract session info."""
    if core_session.name:
        name = core_session.name
    elif core_session.messages:
        name = f"{core_session.messages[0].content[:30]}..."
    else:
        name = "New session"

    return SessionInfo(
        session_id=core_session.session_id,
        name=name,
        message_count=len(core_session.messages),
        created_at=core_session.created_at,
    )
