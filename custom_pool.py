"""
自定义股票池 API 接口
POST /custom_pool — 接收用户自定义股票代码列表，复用现有因子引擎打分排序

依赖: fastapi, pydantic, httpx, asyncio
安装: pip install fastapi uvicorn httpx pydantic

启动: uvicorn server.custom_pool:app --reload --port 8000

=== 需要替换的接口标记 ===
搜索 [REPLACE] 找到所有需要对接现有系统的位置
"""

import asyncio
import time
import re
import os
from typing import Optional
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

app = FastAPI(title="自定义股票池API", version="1.0")

API_KEY = os.getenv("CUSTOM_POOL_API_KEY", "your-secret-key-here")
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
MAX_POOL_SIZE = 200
REQUEST_TIMEOUT = 5.0
BATCH_SIZE = 30
BATCH_DELAY = 0.15


# ============================================================
# 1. 请求/响应模型
# ============================================================

class CustomPoolRequest(BaseModel):
    codes: list[str] = Field(..., description="股票代码列表", min_length=1, max_length=MAX_POOL_SIZE)
    top_n: int = Field(20, description="返回前N只", ge=1, le=200)
    strategy: str = Field("default", description="策略名称，传给现有因子引擎")

    @field_validator("codes")
    @classmethod
    def dedup_codes(cls, v: list[str]) -> list[str]:
        seen = set()
        result = []
        for code in v:
            normalized = normalize_stock_code(code)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        if not result:
            raise ValueError("没有有效的股票代码")
        return result


class StockResult(BaseModel):
    code: str
    name: str
    price: float
    change: float
    score: float
    rank: int
    factors: dict


class CustomPoolResponse(BaseModel):
    success: bool
    processed: int
    skipped: int
    elapsed_ms: float
    timeout: bool
    results: list[StockResult]
    errors: list[str] = Field(default_factory=list)


# ============================================================
# 2. 股票代码格式归一化
#    支持 "000001" / "000001.SZ" / "sz000001" / "SZ000001"
# ============================================================

SZ_PREFIXES = {"0", "1", "2", "3"}
SH_PREFIXES = {"5", "6", "9"}
BJ_PREFIXES = {"4", "8"}

def normalize_stock_code(raw: str) -> Optional[str]:
    raw = raw.strip().upper()
    if not raw:
        return None

    # 格式1: "000001.SZ" -> "sz000001"
    m = re.match(r"^(\d{6})\.([SZ]{2})$", raw)
    if m:
        return f"{m.group(2).lower()}{m.group(1)}"

    # 格式2: "sz000001" 或 "SZ000001"
    m = re.match(r"^([SZ]{2})(\d{6})$", raw)
    if m:
        return f"{m.group(1).lower()}{m.group(2)}"

    # 格式3: 纯数字 "000001" -> 根据前缀推断交易所
    m = re.match(r"^(\d{6})$", raw)
    if m:
        digits = m.group(1)
        first = digits[0]
        if first in SZ_PREFIXES:
            return f"sz{digits}"
        elif first in SH_PREFIXES:
            return f"sh{digits}"
        elif first in BJ_PREFIXES:
            return f"bj{digits}"
        return f"sz{digits}"

    return None


def to_display_code(normalized: str) -> str:
    exchange = normalized[:2].upper()
    digits = normalized[2:]
    return f"{digits}.{exchange}"


# ============================================================
# 3. 腾讯行情API调用 + 股票校验
# ============================================================

@dataclass
class QuoteData:
    code: str
    name: str
    price: float
    prev_close: float
    change: float
    volume: float
    amount: float
    high: float
    low: float
    pe: float
    pb: float
    total_market_cap: float
    turnover_rate: float


async def fetch_tencent_quotes(
    client: httpx.AsyncClient,
    codes: list[str],
) -> dict[str, QuoteData]:
    result: dict[str, QuoteData] = {}

    for i in range(0, len(codes), BATCH_SIZE):
        batch = codes[i : i + BATCH_SIZE]
        query = ",".join(batch)
        try:
            resp = await client.get(TENCENT_QUOTE_URL + query, timeout=3.0)
            text = resp.text
            for line in text.split(";"):
                line = line.strip()
                if not line:
                    continue
                parsed = parse_tencent_line(line)
                if parsed:
                    result[parsed.code] = parsed
        except (httpx.TimeoutException, httpx.HTTPError):
            pass

        if i + BATCH_SIZE < len(codes):
            await asyncio.sleep(BATCH_DELAY)

    return result


def parse_tencent_line(line: str) -> Optional[QuoteData]:
    m = re.search(r'v_(\w+)="(.+?)"', line)
    if not m:
        return None

    code = m.group(1)
    fields = m.group(2).split("~")
    if len(fields) < 40:
        return None

    def safe_float(idx: int) -> float:
        if idx >= len(fields):
            return 0.0
        try:
            v = float(fields[idx])
            return v if v == v else 0.0  # NaN check
        except (ValueError, TypeError):
            return 0.0

    price = safe_float(3)
    if price <= 0:
        return None

    prev_close = safe_float(4)
    change = safe_float(32)
    if change == 0 and prev_close > 0:
        change = round((price - prev_close) / prev_close * 100, 2)

    return QuoteData(
        code=code,
        name=fields[1] if len(fields) > 1 else "",
        price=price,
        prev_close=prev_close,
        change=change,
        volume=safe_float(6),
        amount=safe_float(37),
        high=safe_float(33),
        low=safe_float(34),
        pe=safe_float(39),
        pb=safe_float(46),
        total_market_cap=safe_float(44),
        turnover_rate=safe_float(38),
    )


# ============================================================
# 4. 因子引擎对接  [REPLACE]
# ============================================================

async def run_factor_engine(
    quotes: dict[str, QuoteData],
    strategy: str,
    top_n: int,
) -> list[StockResult]:
    """
    [REPLACE] 把腾讯行情数据喂给你现有的因子引擎。

    当前实现: 用简单的动量+估值打分作为占位逻辑。
    你需要替换为:
        from your_module import your_factor_engine
        scores = your_factor_engine(stock_list, strategy_params)
    """
    # ---- ↓↓↓ 占位逻辑，替换为你的因子引擎调用 ↓↓↓ ----
    results: list[StockResult] = []
    for code, q in quotes.items():
        momentum = q.change
        valuation = 100 / (q.pe + 1) if q.pe > 0 else 0
        size = min(q.total_market_cap / 1000, 10) if q.total_market_cap > 0 else 0
        score = momentum * 0.4 + valuation * 0.3 + size * 0.3

        results.append(
            StockResult(
                code=to_display_code(code),
                name=q.name,
                price=q.price,
                change=q.change,
                score=round(score, 4),
                rank=0,
                factors={
                    "pe": q.pe,
                    "pb": q.pb,
                    "market_cap": q.total_market_cap,
                    "turnover": q.turnover_rate,
                    "momentum": momentum,
                },
            )
        )

    results.sort(key=lambda x: x.score, reverse=True)
    for i, r in enumerate(results):
        r.rank = i + 1
    # ---- ↑↑↑ 占位逻辑结束 ↑↑↑ ----

    return results[:top_n]


# ============================================================
# 5. 鉴权
# ============================================================

def verify_api_key(x_api_key: Optional[str]) -> None:
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="无效的API Key")


# ============================================================
# 6. 主接口
# ============================================================

@app.post("/custom_pool", response_model=CustomPoolResponse)
async def custom_pool(
    body: CustomPoolRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """
    自定义股票池打分接口

    请求头: X-API-Key: your-secret-key
    请求体: {"codes": ["000001.SZ", "600036.SH"], "top_n": 20, "strategy": "default"}
    """
    verify_api_key(x_api_key)

    start = time.monotonic()
    normalized_codes = body.codes
    errors: list[str] = []

    # 用 deadline 控制总超时，超时返回部分结果
    deadline = start + REQUEST_TIMEOUT

    async with httpx.AsyncClient() as client:
        # Step 1: 调腾讯API获取行情 + 隐式校验（API不返回 = 无效代码）
        remaining = max(deadline - time.monotonic(), 0.5)
        try:
            quotes = await asyncio.wait_for(
                fetch_tencent_quotes(client, normalized_codes),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
            quotes = {}

        # Step 2: 区分有效/无效代码
        valid_codes = [c for c in normalized_codes if c in quotes]
        invalid_codes = [c for c in normalized_codes if c not in quotes]

        for c in invalid_codes:
            errors.append(f"{to_display_code(c)}: 无法获取行情数据(代码无效或API超时)")

        if not valid_codes:
            return CustomPoolResponse(
                success=False,
                processed=0,
                skipped=len(invalid_codes),
                elapsed_ms=round((time.monotonic() - start) * 1000, 1),
                timeout=False,
                results=[],
                errors=errors,
            )

        # Step 3: 调用因子引擎
        timeout_flag = False
        remaining = max(deadline - time.monotonic(), 0.5)
        try:
            results = await asyncio.wait_for(
                run_factor_engine(quotes, body.strategy, body.top_n),
                timeout=remaining,
            )
        except asyncio.TimeoutError:
            timeout_flag = True
            # 超时则返回已有行情数据的简单排序
            results = [
                StockResult(
                    code=to_display_code(c),
                    name=q.name,
                    price=q.price,
                    change=q.change,
                    score=0,
                    rank=i + 1,
                    factors={"pe": q.pe, "pb": q.pb},
                )
                for i, (c, q) in enumerate(quotes.items())
            ][: body.top_n]
            errors.append("因子引擎计算超时，返回行情数据降级排序")

    elapsed = round((time.monotonic() - start) * 1000, 1)

    return CustomPoolResponse(
        success=True,
        processed=len(valid_codes),
        skipped=len(invalid_codes),
        elapsed_ms=elapsed,
        timeout=timeout_flag,
        results=results,
        errors=errors,
    )


# ============================================================
# 7. 健康检查
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ============================================================
# 本地开发运行
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server.custom_pool:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
