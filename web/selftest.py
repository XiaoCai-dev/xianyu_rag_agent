"""配置自检：在网页上一键验证「模型 / 向量模型 / 闲鱼 Cookie」是否真正可用。

设计原则:
    - 只读取当前 .env 配置，不修改任何文件；
    - 所有网络调用都带超时，异常全部转成结构化结果返回，绝不 sys.exit / input；
    - Cookie 检测使用独立的一次性请求，不写回 .env、不触发主流程副作用。
"""

import os
import time
from typing import Dict, List

import requests
from loguru import logger

from utils.xianyu_utils import generate_device_id, generate_sign, trans_cookies

_TOKEN_URL = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/"
_APP_KEY = "444e9908a51d1cb236a27862abc769c9"
# Cookie 中缺一不可的字段
_REQUIRED_COOKIE_KEYS = ["unb", "_m_h5_tk", "cookie2", "cna"]


def test_llm() -> Dict:
    """测试 LLM 对话模型连通性。"""
    from openai import OpenAI

    api_key = os.getenv("API_KEY") or ""
    base_url = os.getenv("MODEL_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = os.getenv("MODEL_NAME") or "qwen-max"

    if not api_key:
        return {"target": "llm", "ok": False, "detail": "API_KEY 未配置"}

    started = time.time()
    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=30)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "回复一个字：好"}],
            max_tokens=10,
        )
        return {
            "target": "llm",
            "ok": True,
            "detail": f"模型 {model} 响应正常",
            "model": model,
            "base_url": base_url,
            "sample": (resp.choices[0].message.content or "").strip()[:50],
            "latency_ms": int((time.time() - started) * 1000),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "target": "llm",
            "ok": False,
            "detail": f"{type(e).__name__}: {e}",
            "model": model,
            "base_url": base_url,
            "latency_ms": int((time.time() - started) * 1000),
        }


def test_embedding() -> Dict:
    """测试向量模型连通性（含本地 ONNX 兜底）。"""
    started = time.time()
    try:
        from xianyu_rag_agent.rag.embedder import build_embedder, resolve_provider

        provider = resolve_provider()
        embedder = build_embedder()
        vecs = embedder.embed(["这是一条用于自检的向量化文本"])
        return {
            "target": "embedding",
            "ok": True,
            "detail": f"向量化成功，维度 {len(vecs[0])}",
            "provider": provider,
            "info": embedder.describe(),
            "dim": len(vecs[0]),
            "latency_ms": int((time.time() - started) * 1000),
        }
    except Exception as e:  # noqa: BLE001
        return {
            "target": "embedding",
            "ok": False,
            "detail": f"{type(e).__name__}: {e}",
            "latency_ms": int((time.time() - started) * 1000),
        }


def _fetch_token(session: requests.Session, cookies: Dict[str, str]) -> str:
    """请求一次 IM Token，返回 ret 原始字符串。"""
    device_id = generate_device_id(cookies["unb"])
    token = (session.cookies.get("_m_h5_tk") or cookies.get("_m_h5_tk", "")).split("_")[0]

    ts = str(int(time.time()) * 1000)
    data_val = '{"appKey":"' + _APP_KEY + '","deviceId":"' + device_id + '"}'
    params = {
        "jsv": "2.7.2",
        "appKey": "34839810",
        "t": ts,
        "sign": generate_sign(ts, token, data_val),
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": "mtop.taobao.idlemessage.pc.login.token",
        "sessionOption": "AutoLoginOnly",
        "spm_cnt": "a21ybx.im.0.0",
    }
    headers = {
        "Host": "h5api.m.goofish.com",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        ),
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.goofish.com",
        "referer": "https://www.goofish.com/",
    }
    resp = session.post(
        _TOKEN_URL,
        params=params,
        data={"data": data_val},
        headers=headers,
        timeout=20,
    )
    return str(resp.json().get("ret", []))


def _try_has_login(session: requests.Session, cookies: Dict[str, str]) -> bool:
    """复刻 XianyuApis.hasLogin 的刷新流程（不弹输入、不退出进程）。"""
    try:
        resp = session.post(
            "https://passport.goofish.com/newlogin/hasLogin.do",
            params={"appName": "xianyu", "fromSite": "77"},
            data={
                "hid": cookies.get("unb", ""),
                "ltl": "true",
                "appName": "xianyu",
                "appEntrance": "web",
                "_csrf_token": cookies.get("XSRF-TOKEN", ""),
                "umidToken": "",
                "hsiz": cookies.get("cookie2", ""),
                "bizParams": "taobaoBizLoginFrom=web",
                "mainPage": "false",
                "isMobile": "false",
                "lang": "zh_CN",
                "returnUrl": "",
                "fromSite": "77",
                "isIframe": "true",
                "documentReferer": "https://www.goofish.com/",
                "defaultView": "hasLogin",
                "umidTag": "SERVER",
                "deviceId": cookies.get("cna", ""),
            },
            timeout=20,
        )
        return bool(resp.json().get("content", {}).get("success"))
    except Exception:  # noqa: BLE001
        return False


def test_cookie(do_network: bool = True) -> Dict:
    """校验闲鱼 Cookie：先检查必需字段，再发起真实取 token 请求。

    说明：Cookie 过期时闲鱼会先走 hasLogin 刷新再发 token，
    bot 主进程正是这么做的，因此自检也复刻这一步，避免把「可自愈」误报为失效。
    """
    cookie_str = os.getenv("COOKIES_STR") or ""
    if not cookie_str or cookie_str == "your_cookies_here":
        return {"target": "cookie", "ok": False, "detail": "COOKIES_STR 未配置"}

    try:
        cookies = trans_cookies(cookie_str)
    except Exception as e:  # noqa: BLE001
        return {"target": "cookie", "ok": False, "detail": f"Cookie 解析失败: {e}"}

    missing = [k for k in _REQUIRED_COOKIE_KEYS if not cookies.get(k)]
    if missing:
        return {
            "target": "cookie",
            "ok": False,
            "detail": f"缺少关键字段: {', '.join(missing)}（请从浏览器重新复制完整 Cookie）",
            "field_count": len(cookies),
        }

    result = {
        "target": "cookie",
        "ok": True,
        "detail": f"格式校验通过，共 {len(cookies)} 个字段",
        "unb": cookies.get("unb"),
        "field_count": len(cookies),
    }
    if not do_network:
        return result

    started = time.time()
    try:
        session = requests.Session()
        session.cookies.update(cookies)
        ret = _fetch_token(session, cookies)

        # token 接口常见「会话过期/令牌过期」，先按 bot 的方式刷新登录再试一次
        if "SUCCESS::调用成功" not in ret:
            result["detail"] = "首次取 token 未成功，正在尝试刷新登录..."
            if _try_has_login(session, cookies):
                cookies = {c.name: c.value for c in session.cookies}
                ret = _fetch_token(session, cookies)

        result["latency_ms"] = int((time.time() - started) * 1000)

        if "SUCCESS::调用成功" in ret:
            result["ok"] = True
            result["detail"] = "Cookie 有效，已成功获取 IM Token（可正常接入闲鱼消息）"
        elif "RGV587_ERROR" in ret or "被挤爆" in ret:
            result["ok"] = False
            result["detail"] = "触发风控：请到闲鱼网页版点开消息过一次滑块，再重新复制 Cookie"
        else:
            result["ok"] = False
            result["detail"] = f"取 token 失败（{ret[:160]}），Cookie 可能已失效"
        return result
    except Exception as e:  # noqa: BLE001
        result["ok"] = False
        result["detail"] = f"网络请求异常: {type(e).__name__}: {e}"
        return result


_TESTS = {
    "llm": test_llm,
    "embedding": test_embedding,
    "cookie": test_cookie,
}


def run_selftest(targets: List[str]) -> Dict:
    """按需执行自检，返回各项结果。"""
    results = []
    for name in targets:
        fn = _TESTS.get(name)
        if not fn:
            results.append({"target": name, "ok": False, "detail": f"未知检测项: {name}"})
            continue
        logger.info(f"配置自检开始: {name}")
        try:
            r = fn()
        except Exception as e:  # noqa: BLE001
            r = {"target": name, "ok": False, "detail": f"{type(e).__name__}: {e}"}
        logger.info(f"配置自检结果: {name} -> {'OK' if r.get('ok') else 'FAIL'} | {r.get('detail')}")
        results.append(r)
    return {"results": results, "all_ok": all(r.get("ok") for r in results)}
