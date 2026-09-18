"""可视化平台后端（FastAPI）。

启动: uvicorn web.app:app --host 0.0.0.0 --port 8000

注意：包的 ``__init__`` 会在导入任何 ``web.*`` 子模块之前执行，
因此在这里完成三件事：
    1. 把项目根加入 sys.path 并 chdir 过去，保证 data/、prompts/、utils/ 都能按相对路径定位；
    2. 修好 .env（Docker 挂载不存在的文件会生成同名目录）；
    3. 加载 .env —— 此前 web 进程从不加载 .env，导致 RAG 因缺少 API_KEY 而始终 503。
"""

import os
import sys

from dotenv import load_dotenv

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_PROJECT_ROOT)

from utils.env_file import ensure_env_file  # noqa: E402  (必须在 chdir 之后导入)

_ENV_PATH = ensure_env_file()
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH, override=False)
