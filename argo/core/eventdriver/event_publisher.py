import asyncio
import inspect
from typing import Callable, Dict, List, Any

from argo.utils.logger import logger


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Any], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Any], None]):
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def publish(self, event_type: str, event: Any):
        for subscriber in self._subscribers.get(event_type, []):
            if inspect.iscoroutinefunction(subscriber):
                try:
                    logger.info(f"[Event] publishing event {event_type}")
                    asyncio.create_task(subscriber(event))
                except RuntimeError as e:
                    print(f"Error: can not handle event {event_type}. {e}")
            else:
                subscriber(event)

event_bus = EventBus()
