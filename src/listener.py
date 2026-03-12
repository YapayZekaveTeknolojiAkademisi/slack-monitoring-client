from __future__ import annotations

from typing import Optional

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.error import BoltUnhandledRequestError
from slack_bolt.response import BoltResponse

from src.queue import QueueServer, build_message_event
from src.core.settings import get_settings
from src.core.logger import get_logger

logger = get_logger()
settings = get_settings()

# Bolt kendi logger'ını kullanır; app logger sadece bizim mesajlarımız için (system.log sade kalır).
app = App(
    token=settings.slack_app_token,
    raise_error_for_unhandled_request=True,
)

queue_server = QueueServer()
_socket_handler: Optional[SocketModeHandler] = None


def _enqueue(event_type: str, item: dict) -> None:
    try:
        queue_server.put(item)
        logger.info("event=%s", event_type, extra={"queue_event": item})
    except Exception:
        logger.exception("Kuyruğa yazılamadı (event_type=%s)", event_type)
        raise


@app.error
def _handle_unhandled(error, request, response):
    if isinstance(error, BoltUnhandledRequestError):
        return BoltResponse(status=200, body="")
    logger.exception("Slack event işlenirken hata: %s", error)
    return BoltResponse(status=200, body="")


# -----------------------------------------------------------------------------
# 1. Mesaj ve içerik
# -----------------------------------------------------------------------------

@app.event("message")
def handle_message(event: dict, say, ack):
    ack()
    channel_id = event.get("channel")
    ts = event.get("ts")
    subtype = event.get("subtype")

    if subtype == "message_deleted":
        prev = event.get("previous_message") or {}
        item = build_message_event(
            event_type="message_deleted",
            user_id=prev.get("user"),
            channel_id=channel_id,
            text=prev.get("text"),
            ts=event.get("deleted_ts") or ts,
        )
        _enqueue("message_deleted", item)
        return

    if subtype == "message_changed":
        msg = event.get("message") or {}
        item = build_message_event(
            event_type="message_changed",
            user_id=msg.get("user"),
            channel_id=channel_id,
            text=msg.get("text"),
            ts=msg.get("ts"),
            thread_ts=msg.get("thread_ts"),
        )
        _enqueue("message_changed", item)
        return

    if subtype == "thread_broadcast":
        msg = event.get("message") or event
        item = build_message_event(
            event_type="thread_broadcast",
            user_id=msg.get("user"),
            channel_id=channel_id,
            text=msg.get("text"),
            ts=msg.get("ts"),
            thread_ts=msg.get("thread_ts"),
        )
        _enqueue("thread_broadcast", item)
        return

    if subtype == "bot_message":
        item = build_message_event(
            event_type="bot_message",
            user_id=event.get("bot_id"),
            channel_id=channel_id,
            text=event.get("text"),
            ts=ts,
            thread_ts=event.get("thread_ts"),
        )
        _enqueue("bot_message", item)
        return

    user_id = event.get("user")
    if not user_id:
        logger.warning("message event without user_id")
        return

    thread_ts = event.get("thread_ts")
    event_type = "thread_reply" if thread_ts else "message"
    item = build_message_event(
        event_type=event_type,
        user_id=user_id,
        channel_id=channel_id,
        text=event.get("text"),
        ts=ts,
        thread_ts=thread_ts,
    )
    _enqueue(event_type, item)


@app.event("app_mention")
def handle_app_mention(event: dict, say, ack):
    ack()
    item = build_message_event(
        event_type="app_mention",
        user_id=event.get("user"),
        channel_id=event.get("channel"),
        text=event.get("text"),
        ts=event.get("ts"),
        thread_ts=event.get("thread_ts"),
    )
    _enqueue("app_mention", item)


@app.event("reaction_added")
def handle_reaction_added(event: dict, ack):
    ack()
    item_payload = event.get("item", {})
    item = build_message_event(
        event_type="reaction_added",
        user_id=event.get("user"),
        channel_id=item_payload.get("channel"),
        ts=item_payload.get("ts"),
        reaction=event.get("reaction"),
    )
    _enqueue("reaction_added", item)


@app.event("reaction_removed")
def handle_reaction_removed(event: dict, ack):
    ack()
    item_payload = event.get("item", {})
    item = build_message_event(
        event_type="reaction_removed",
        user_id=event.get("user"),
        channel_id=item_payload.get("channel"),
        ts=item_payload.get("ts"),
        reaction=event.get("reaction"),
    )
    _enqueue("reaction_removed", item)


@app.event("pin_added")
def handle_pin_added(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="pin_added",
        user_id=event.get("user"),
        channel_id=event.get("channel_id"),
        ts=event.get("message", {}).get("ts") if isinstance(event.get("message"), dict) else None,
    )
    _enqueue("pin_added", item)


@app.event("pin_removed")
def handle_pin_removed(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="pin_removed",
        user_id=event.get("user"),
        channel_id=event.get("channel_id"),
    )
    _enqueue("pin_removed", item)


@app.event("link_shared")
def handle_link_shared(event: dict, ack):
    ack()
    links = event.get("links", [])
    item = build_message_event(
        event_type="link_shared",
        user_id=event.get("user"),
        channel_id=event.get("channel"),
        ts=event.get("message_ts"),
        links=[{"url": l.get("url"), "domain": l.get("domain")} for l in links],
    )
    _enqueue("link_shared", item)


# -----------------------------------------------------------------------------
# 2. Kanal / grup etkinlikleri
# -----------------------------------------------------------------------------

@app.event("member_joined_channel")
def handle_member_joined_channel(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="member_joined",
        user_id=event.get("user"),
        channel_id=event.get("channel"),
    )
    _enqueue("member_joined", item)


@app.event("member_left_channel")
def handle_member_left_channel(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="member_left",
        user_id=event.get("user"),
        channel_id=event.get("channel"),
    )
    _enqueue("member_left", item)


@app.event("channel_created")
def handle_channel_created(event: dict, ack):
    ack()
    ch = event.get("channel") or {}
    item = build_message_event(
        event_type="channel_created",
        user_id=ch.get("creator"),
        channel_id=ch.get("id"),
        channel_name=ch.get("name"),
    )
    _enqueue("channel_created", item)


@app.event("channel_deleted")
def handle_channel_deleted(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="channel_deleted",
        channel_id=event.get("channel"),
    )
    _enqueue("channel_deleted", item)


@app.event("channel_joined")
def handle_channel_joined(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="channel_joined",
        channel_id=event.get("channel", {}).get("id") if isinstance(event.get("channel"), dict) else event.get("channel"),
    )
    _enqueue("channel_joined", item)


@app.event("channel_left")
def handle_channel_left(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="channel_left",
        channel_id=event.get("channel"),
    )
    _enqueue("channel_left", item)


@app.event("channel_rename")
def handle_channel_rename(event: dict, ack):
    ack()
    ch = event.get("channel") or {}
    item = build_message_event(
        event_type="channel_rename",
        channel_id=ch.get("id"),
        channel_name=ch.get("name"),
    )
    _enqueue("channel_rename", item)


@app.event("group_rename")
def handle_group_rename(event: dict, ack):
    ack()
    ch = event.get("channel") or {}
    item = build_message_event(
        event_type="group_rename",
        channel_id=ch.get("id"),
        channel_name=ch.get("name"),
    )
    _enqueue("group_rename", item)


@app.event("channel_archive")
def handle_channel_archive(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="channel_archive",
        channel_id=event.get("channel"),
        user_id=event.get("user"),
    )
    _enqueue("channel_archive", item)


@app.event("channel_unarchive")
def handle_channel_unarchive(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="channel_unarchive",
        channel_id=event.get("channel"),
        user_id=event.get("user"),
    )
    _enqueue("channel_unarchive", item)


@app.event("group_archive")
def handle_group_archive(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="group_archive",
        channel_id=event.get("channel"),
        user_id=event.get("user"),
    )
    _enqueue("group_archive", item)


@app.event("group_unarchive")
def handle_group_unarchive(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="group_unarchive",
        channel_id=event.get("channel"),
        user_id=event.get("user"),
    )
    _enqueue("group_unarchive", item)


# -----------------------------------------------------------------------------
# 3. Kullanıcı etkinlikleri
# -----------------------------------------------------------------------------

@app.event("user_change")
def handle_user_change(event: dict, ack):
    ack()
    user = event.get("user") or {}
    item = build_message_event(
        event_type="user_change",
        user_id=user.get("id"),
        text=user.get("name"),
        **{"profile": user.get("profile"), "deleted": user.get("deleted")},
    )
    _enqueue("user_change", item)


@app.event("user_typing")
def handle_user_typing(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="user_typing",
        user_id=event.get("user"),
        channel_id=event.get("channel"),
    )
    _enqueue("user_typing", item)


@app.event("presence_change")
def handle_presence_change(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="presence_change",
        user_id=event.get("user"),
        **{"presence": event.get("presence")},
    )
    _enqueue("presence_change", item)


@app.event("dnd_updated_user")
def handle_dnd_updated(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="dnd_updated_user",
        user_id=event.get("user"),
        **{"dnd_status": event.get("dnd_status")},
    )
    _enqueue("dnd_updated_user", item)


@app.event("user_huddle_changed")
def handle_user_huddle_changed(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="user_huddle_changed",
        user_id=event.get("user"),
        **{"is_huddle": event.get("is_huddle")},
    )
    _enqueue("user_huddle_changed", item)


# -----------------------------------------------------------------------------
# 4. Dosya ve içerik paylaşımı
# -----------------------------------------------------------------------------

@app.event("file_created")
def handle_file_created(event: dict, ack):
    ack()
    f = event.get("file") or {}
    item = build_message_event(
        event_type="file_created",
        user_id=f.get("user") or event.get("user_id"),
        channel_id=event.get("channel_id") or (f.get("channels", [None])[0] if f.get("channels") else None),
        **{"file_id": f.get("id"), "name": f.get("name")},
    )
    _enqueue("file_created", item)


@app.event("file_deleted")
def handle_file_deleted(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="file_deleted",
        channel_id=event.get("channel_id"),
        **{"file_id": event.get("file_id")},
    )
    _enqueue("file_deleted", item)


@app.event("file_shared")
def handle_file_shared(event: dict, ack):
    ack()
    f = event.get("file") or {}
    item = build_message_event(
        event_type="file_shared",
        user_id=event.get("user_id"),
        channel_id=event.get("channel_id"),
        **{"file_id": f.get("id"), "name": f.get("name")},
    )
    _enqueue("file_shared", item)


@app.event("file_unshared")
def handle_file_unshared(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="file_unshared",
        channel_id=event.get("channel_id"),
        **{"file_id": event.get("file_id")},
    )
    _enqueue("file_unshared", item)


@app.event("file_comment_added")
def handle_file_comment_added(event: dict, ack):
    ack()
    comment = event.get("comment") or {}
    item = build_message_event(
        event_type="file_comment_added",
        user_id=comment.get("user") or event.get("user_id"),
        channel_id=event.get("channel_id"),
        text=comment.get("comment"),
        **{"file_id": event.get("file_id")},
    )
    _enqueue("file_comment_added", item)


@app.event("file_comment_deleted")
def handle_file_comment_deleted(event: dict, ack):
    ack()
    item = build_message_event(
        event_type="file_comment_deleted",
        channel_id=event.get("channel_id"),
        **{"file_id": event.get("file_id"), "comment_id": event.get("comment")},
    )
    _enqueue("file_comment_deleted", item)


@app.event("file_comment_edited")
def handle_file_comment_edited(event: dict, ack):
    ack()
    comment = event.get("comment") or {}
    item = build_message_event(
        event_type="file_comment_edited",
        user_id=comment.get("user") or event.get("user_id"),
        channel_id=event.get("channel_id"),
        text=comment.get("comment"),
        **{"file_id": event.get("file_id")},
    )
    _enqueue("file_comment_edited", item)


# -----------------------------------------------------------------------------
# Start & stop (yaşam döngüsü main tarafından yönetilir)
# -----------------------------------------------------------------------------


def start() -> None:
    """Queue ve Slack Socket Mode dinleyicisini başlatır (bloklayıcı)."""
    global _socket_handler
    queue_server.start()
    _socket_handler = SocketModeHandler(app, settings.slack_app_token)
    logger.info("Slack dinleyici başladı.")
    _socket_handler.start()


def stop() -> None:
    """Socket Mode bağlantısını kapatır (graceful shutdown için)."""
    global _socket_handler
    if _socket_handler is not None:
        try:
            _socket_handler.close()
        except Exception as e:
            logger.warning("SocketModeHandler kapatılırken hata: %s", e)
        _socket_handler = None