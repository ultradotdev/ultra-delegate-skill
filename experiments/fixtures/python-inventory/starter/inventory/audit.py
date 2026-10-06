class AuditLog:
    def __init__(self):
        self._entries = []

    def record(self, event, **fields):
        entry = {'seq': len(self._entries) + 1, 'event': event, **fields}
        self._entries.append(entry)
        return entry

    def entries(self):
        return [dict(entry) for entry in self._entries]
