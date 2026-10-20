class NotificationRejected(Exception):
    def __init__(self, code, status=412):
        self.code = code
        self.status = status
        super().__init__(code)
