# -*- coding: utf-8 -*-
"""Logical TaskScheduler -> QWeb executor adapter for the application runtime."""

from __future__ import annotations

from bot_ia.core.task_engine import Task
from services.web_queue import WebChatQueueManager


class WebChatTaskExecutor:
    """Translate a logical Task into the existing QWeb ticket queue.

    This class owns no physical state. Physical ownership and lifecycle remain
    inside QWebPhysicalResourceAdapter and PhysicalWebChatResourceAuthority.
    """

    def __init__(self, web_queue: WebChatQueueManager) -> None:
        if not isinstance(web_queue, WebChatQueueManager):
            raise TypeError("web_queue must be WebChatQueueManager")
        self.web_queue = web_queue

    def submit(self, task: Task) -> None:
        if not isinstance(task, Task):
            raise TypeError("task must be Task")
        context = task.context
        self.web_queue.enqueue_bot_message(
            bot_name=str(
                context.get("bot_name")
                or context.get("waitress_id")
                or "BOT-IA"
            ),
            ticket_id=task.task_id,
            action=str(context.get("action") or "chat"),
            message=str(context.get("message") or ""),
            user=str(context.get("user") or task.requester),
            channel=str(context.get("channel") or "/cafe"),
        )

    def cancel(self, task_id: str) -> None:
        self.web_queue.cancel_ticket(task_id)


__all__ = ["WebChatTaskExecutor"]
