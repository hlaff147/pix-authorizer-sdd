class DailyLimitExceededException(Exception):
    """Lançada quando a transação excede o limite diário configurado."""

    def __init__(self, message: str = "Limite diário excedido"):
        self.message = message
        self.error_code = "DAILY_LIMIT_EXCEEDED"
        super().__init__(self.message)
