import logging
import asyncio
import os
import sys
from typing import Any 
import aiohttp
from discord.utils import MISSING, _ColourFormatter

from utils.json_loader import read_json

info_file = read_json('info')
logger_webhook = info_file['webhooks']['logger_webhook']
if not logger_webhook:
    wb = False
else:
    wb = True

class Discord_Handler(logging.Handler):

    def __init__(self, url):
        logging.Handler.__init__(self)
        self.url = url

    def mapLogRecord(self, record):
        return record.__dict__

    def emit(self, record):
        asyncio.create_task(self.emitting(record))

    async def emitting(self, record):
        try:
            msg = self.format(record)
            url = self.url
            headers = {}
            data = self.mapLogRecord(record)
            headers["Content-type"] = "application/x-www-form-urlencoded"
            #can't do anything with the result
            if len(msg) > 1900:
                msg_list = [msg[i: i+1900] for i in range(0, len(msg), 1900)]
                for i in msg_list:
              	    async with aiohttp.request("POST", url, data={'content':f"```{i}```"}, headers=headers):
                        pass
            else:
                if 'aiohttp.http_exceptions.BadStatusLine' in msg or 'UNKNOWN / HTTP/1.0' in msg:
                    pass

                async with aiohttp.request("POST", url, data={'content':f"```{msg}```"}, headers=headers):
                    pass
        except Exception:
            self.handleError(record)


def stream_supports_colour(stream: Any) -> bool:
    # Pycharm and Vscode support colour in their inbuilt editors
    if 'PYCHARM_HOSTED' in os.environ or os.environ.get('TERM_PROGRAM') == 'vscode':
        return True

    is_a_tty = hasattr(stream, 'isatty') and stream.isatty()
    if sys.platform != 'win32':
        return is_a_tty

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return is_a_tty and ('ANSICON' in os.environ or 'WT_SESSION' in os.environ)
    
def setup_logging(
    *,
    handler: logging.Handler = MISSING,
    formatter: logging.Formatter = MISSING,
    level: int = MISSING,
    root: bool = True,
) -> None:
    """A helper function to setup logging.

    This is superficially similar to :func:`logging.basicConfig` but
    uses different defaults and a colour formatter if the stream can
    display colour.

    This is used by the :class:`~discord.Client` to set up logging
    if ``log_handler`` is not ``None``.

    .. versionadded:: 2.0

    Parameters
    -----------
    handler: :class:`logging.Handler`
        The log handler to use for the library's logger.

        The default log handler if not provided is :class:`logging.StreamHandler`.
    formatter: :class:`logging.Formatter`
        The formatter to use with the given log handler. If not provided then it
        defaults to a colour based logging formatter (if available). If colour
        is not available then a simple logging formatter is provided.
    level: :class:`int`
        The default log level for the library's logger. Defaults to ``logging.INFO``.
    root: :class:`bool`
        Whether to set up the root logger rather than the library logger.
        Unlike the default for :class:`~discord.Client`, this defaults to ``True``.
    """

    if level is MISSING:
        level = logging.INFO

    if handler is MISSING:
        handler = logging.StreamHandler()

    if formatter is MISSING:
        if isinstance(handler, logging.StreamHandler) and stream_supports_colour(handler.stream):
            formatter = _ColourFormatter()
        else:
            dt_fmt = '%Y-%m-%d %H:%M:%S'
            formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')

    if root:
        logger = logging.getLogger()
    else:
        library, _, _ = __name__.partition('.')
        logger = logging.getLogger(library)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)
    if wb:
        logger.addHandler(Discord_Handler(logger_webhook))

    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)
