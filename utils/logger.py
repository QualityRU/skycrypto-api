from system.settings import APP_NAME
import logging


class NoRunningFilter(logging.Filter):
    def filter(self, record):
        m = record.msg
        return m != '%r'


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(APP_NAME)
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger('sqlalchemy.engine.base.Engine').addFilter(NoRunningFilter())

logging.getLogger('apscheduler.scheduler').setLevel(logging.WARN)
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)
logging.getLogger('werkzeug').setLevel(logging.WARN)

