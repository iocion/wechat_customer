"""WeChat Work AI Customer Service Bot — Flask application entry point."""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue
from typing import Any

from flask import Flask

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Application factory — wires all components together."""

    from config import Config
    from wecom.crypto import WeChatCrypto
    from wecom.callback import callback_bp
    from wecom.token_manager import TokenManager
    from wecom.message import MessageSender
    from wecom.kf_client import KfClient
    from skills.router import SkillRouter
    from skills.greeting import GreetingSkill
    from skills.stage_router import StageRouterSkill
    from skills.pre_sales import PreSalesSkill
    from skills.mid_sales import MidSalesSkill
    from skills.post_sales import PostSalesSkill
    from skills.chat import ChatSkill
    from session.manager import SessionManager
    from session.models import SessionState
    from ai.glm_client import GLMClient

    app = Flask(__name__)

    # -- Config --
    config = Config()

    # -- Core components --
    crypto = WeChatCrypto(
        token=config.TOKEN,
        encoding_aes_key=config.ENCODING_AES_KEY,
        corp_id=config.CORP_ID,
    )
    token_manager = TokenManager(
        corp_id=config.CORP_ID,
        corp_secret=config.CORP_SECRET,
    )
    message_sender = MessageSender(token_manager=token_manager)
    kf_client = KfClient(token_manager=token_manager)
    session_manager = SessionManager()

    glm_client = GLMClient(
        api_key=config.GLM_API_KEY,
        base_url=config.GLM_API_BASE,
        model=config.GLM_MODEL,
    )

    # -- Skill router --
    # 优先级: Greeting(100) → StageRouter(90) → PreSales(40) → MidSales(30) → PostSales(20) → Chat(0)
    router = SkillRouter()
    router.register(GreetingSkill())
    router.register(StageRouterSkill(glm_client=glm_client))
    router.register(PreSalesSkill(glm_client=glm_client))
    router.register(MidSalesSkill(glm_client=glm_client))
    router.register(PostSalesSkill(glm_client=glm_client))
    chat_skill = ChatSkill(glm_client=glm_client)
    router.register(chat_skill)
    router.set_default(chat_skill)

    # -- Message queue --
    message_queue: Queue[dict[str, Any]] = Queue()

    # Store in app.config so blueprints / handler can access them
    app.config["crypto"] = crypto
    app.config["message_sender"] = message_sender
    app.config["kf_client"] = kf_client
    app.config["session_manager"] = session_manager
    app.config["skill_router"] = router
    app.config["message_queue"] = message_queue
    app.config["app_config"] = config

    # -- Register blueprints --
    app.register_blueprint(callback_bp)

    # -- Background message worker --
    def _process_messages() -> None:
        """Pull messages from the queue and dispatch to skills."""
        while True:
            try:
                item = message_queue.get()
                if item is None:  # poison pill
                    break

                message = item["message"]
                user_id = message.get("FromUserName", "")
                if not user_id:
                    logger.warning("Message without FromUserName — skipping")
                    continue

                session = session_manager.get_or_create(user_id)

                executed_skills = router.route_chain(message, session)
                if not executed_skills:
                    logger.warning("No skill matched for user %s", user_id)
                    continue

                _, response = executed_skills[-1]
                logger.info(
                    "Routing user %s → %s",
                    user_id,
                    [s.name for s, _ in executed_skills],
                )

                if response.next_state:
                    session.state = SessionState[response.next_state]
                if response.should_update_session and message.get("Content"):
                    session.add_message("user", message["Content"])
                    session.add_message("assistant", response.text)
                session.updated_at = time.time()
                session_manager.update(session)

                send_kwargs: dict[str, Any] = {}
                open_kfid = ""
                if config.MESSAGE_MODE == "kf":
                    open_kfid = message.get("OpenKfId") or config.KF_OPEN_KFID
                    send_kwargs["open_kfid"] = open_kfid

                    session_ready = kf_client.ensure_session_serving(
                        open_kfid=open_kfid,
                        external_userid=user_id,
                    )
                    if not session_ready:
                        logger.warning(
                            "Session %s not in a sendable state — dropping reply",
                            user_id,
                        )
                        continue

                else:
                    send_kwargs["agent_id"] = config.AGENT_ID

                message_sender.send_text(
                    user_id=user_id,
                    content=response.text,
                    mode=config.MESSAGE_MODE,
                    **send_kwargs,
                )

                if response.transfer_to_human and config.MESSAGE_MODE == "kf":
                    kf_client.transfer_to_human(
                        open_kfid=open_kfid,
                        external_userid=user_id,
                        servicer_userid=config.KF_SERVICER_USERID,
                    )

            except Exception:
                logger.exception("Message processing error")
            finally:
                message_queue.task_done()

    # Start 2 worker threads
    for i in range(2):
        t = threading.Thread(
            target=_process_messages, daemon=True, name=f"msg-worker-{i}"
        )
        t.start()
        logger.info("Started worker thread: %s", t.name)

    # -- Simple endpoints --
    @app.route("/health")
    def health():  # type: ignore[no-untyped-def]
        return {"status": "ok", "skills": [s.name for s in router.skills]}

    @app.route("/")
    def index():  # type: ignore[no-untyped-def]
        return {"service": "WeChat Work AI Customer Service", "status": "running"}

    logger.info("Application initialised — skills: %s", [s.name for s in router.skills])
    return app


# Create application instance for gunicorn
application = create_app()


if __name__ == "__main__":
    from config import Config

    cfg = Config()
    application.run(host=cfg.SERVER_HOST, port=cfg.SERVER_PORT, debug=cfg.DEBUG)
