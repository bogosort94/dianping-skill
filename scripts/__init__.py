"""
dianping-skill

基于 xiaohongshu-skill 架构的大众点评自动化查询工具
"""

from .client import DianpingClient, create_client, DEFAULT_COOKIE_PATH
from . import login
from . import search
from . import shop

__version__ = "0.1.0"
__all__ = [
    "DianpingClient",
    "create_client",
    "DEFAULT_COOKIE_PATH",
    "login",
    "search",
    "shop",
]
