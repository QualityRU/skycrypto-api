from typing import Optional, Tuple

from flask_apscheduler import APScheduler
from werkzeug.exceptions import InternalServerError, BadRequest, Forbidden
from jobs.config import Config
from apis.internal import *
from utils.logger import logger
import traceback


def exception_handler(exception: BaseException, status: int, detail: Optional[str] = None) -> Tuple[dict, int]:
    detail = detail or str(exception)
    return jsonify({'type': exception.__class__.__name__, 'detail': detail, 'status': status}), status


@app.errorhandler(InternalServerError)
def handle_error(e):
    logger.error(traceback.format_exc())
    return exception_handler(e, 500, "Internal server error")


@app.errorhandler(BadRequest)
def handle_error(e):
    return exception_handler(e, 400)


@app.errorhandler(Forbidden)
def handle_error(e):
    return exception_handler(e, 403)


if __name__ == '__main__':
    app.config.from_object(Config())
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()
    app.run(host='0.0.0.0', port=5555)
