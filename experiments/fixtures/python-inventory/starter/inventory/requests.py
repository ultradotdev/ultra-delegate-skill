"""Request-id bookkeeping for idempotent operations (SPEC R17-R19)."""
from .errors import IdempotencyConflict

MISSING = object()


class RequestLog:
    def __init__(self):
        self._seen = {}

    def replay(self, request_id, operation, args):
        """Return the remembered result for `request_id`, or MISSING if it is new.

        Raises IdempotencyConflict if the id was used for another call.
        """
        if request_id not in self._seen:
            return MISSING
        seen_operation, seen_args, result = self._seen[request_id]
        if (seen_operation, seen_args) != (operation, args):
            raise IdempotencyConflict(
                f'request {request_id!r} was already used for {seen_operation}{seen_args!r}')
        return result

    def remember(self, request_id, operation, args, result):
        self._seen[request_id] = (operation, args, result)
