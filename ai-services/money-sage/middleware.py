import logging
import sys

# Basic structured logging setup
LOG_LEVEL = logging.INFO
if logging.root.handlers:
    logging.root.handlers.clear()

logging.basicConfig(
    level=LOG_LEVEL,
    format='{"ts": "%(asctime)s", "level": "%(levelname)s", "service": "money-sage", "correlation_id": "%(correlation_id)s", "message": "%(message)s"}',
    stream=sys.stdout,
)

class CorrelationIdLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        kwargs['extra']['correlation_id'] = self.extra.get('correlation_id', 'N/A')
        return msg, kwargs

def get_logger(correlation_id: str = None):
    logger = logging.getLogger(__name__)
    return CorrelationIdLoggerAdapter(logger, {'correlation_id': correlation_id})
