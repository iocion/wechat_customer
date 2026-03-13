"""WeChat Work AI Customer Service Bot — Flask application entry point."""

from __future__ import annotations

import logging
import threading
import time
from queue import Queue

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
    from skills.base import SkillResponse
    from skills.router import SkillRouter
    from skills.welcome import WelcomeSkill
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
    session_manager = SessionManager()

    glm_client = GLMClient(
        api_key=config.GLM_API_KEY,
        base_url=config.GLM_API_BASE,
        model=config.GLM_MODEL,
    )

    # -- Skill router --
    router = SkillRouter()
    router.register(WelcomeSkill())
    chat_skill = ChatSkill(glm_client=glm_client)
    router.register(chat_skill)
    router.set_default(chat_skill)

    # -- Message queue --
    message_queue: Queue[dict] = Queue()

    # Store in app.config so blueprints / handler can access them
    app.config["crypto"] = crypto
    app.config["message_sender"] = message_sender
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
                skill = router.route(message, session)
                if skill is None:
                    logger.warning("No skill matched for user %s", user_id)
                    continue

                logger.info("Routing user %s → skill '%s'", user_id, skill.name)

                try:
                    response: SkillResponse = skill.handle(message, session)
                except Exception:
                    logger.exception(
                        "Skill '%s' error for user %s", skill.name, user_id
                    )
                    response = SkillResponse(
                        text="抱歉，处理您的消息时出现了问题，请稍后再试。"
                    )

                # Update session state
                if response.next_state:
                    session.state = SessionState[response.next_state]
                if response.should_update_session and message.get("Content"):
                    session.add_message("user", message["Content"])
                    session.add_message("assistant", response.text)
                session.updated_at = time.time()
                session_manager.update(session)

                # Send reply via WeChat Work API
                send_kwargs: dict = {}
                if config.MESSAGE_MODE == "kf":
                    send_kwargs["open_kfid"] = config.KF_OPEN_KFID
                else:
                    send_kwargs["agent_id"] = config.AGENT_ID

                message_sender.send_text(
                    user_id=user_id,
                    content=response.text,
                    mode=config.MESSAGE_MODE,
                    **send_kwargs,
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


if __name__ == "__main__":
    from config import Config

    cfg = Config()
    application = create_app()
    application.run(host=cfg.SERVER_HOST, port=cfg.SERVER_PORT, debug=cfg.DEBUG)
