from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Input(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, allow_inf_nan=False
    )


class WatchInput(Input):
    symbol: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9.:-]+$")
    notes: str = Field(default="", max_length=10000)
    conviction: int = Field(default=3, ge=1, le=5)
    target_price: Decimal | None = Field(default=None, ge=0, le=1e12)
    alert_below: Decimal | None = Field(default=None, ge=0, le=1e12)
    alert_above: Decimal | None = Field(default=None, ge=0, le=1e12)


class Named(Input):
    name: str = Field(min_length=1, max_length=80)


class ThesisInput(Input):
    thesis: str = Field(default="", max_length=20000)
    risks: str = Field(default="", max_length=10000)
    catalysts: str = Field(default="", max_length=10000)
    conviction: int = Field(default=3, ge=1, le=5)
    target_price: Decimal | None = Field(default=None, ge=0, le=1e12)


class JournalInput(Input):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    date: date
    symbol: str | None = Field(default=None, max_length=100)
    category: str = Field(default="Portfolio review", max_length=50)
    transaction_id: int | None = None


class EventInput(Input):
    title: str = Field(min_length=1, max_length=200)
    date: date
    symbol: str | None = Field(default=None, max_length=100)
    kind: Literal["earnings", "dividend_ex", "dividend_payment", "macro", "other"] = (
        "other"
    )


class TransactionInput(Input):
    kind: Literal["buy", "sell", "dividend", "deposit", "withdrawal", "fee", "transfer"]
    date: date
    symbol: str | None = Field(default=None, max_length=100)
    amount: Decimal = Field(ge=0, le=1e12)
    quantity: Decimal | None = Field(default=None, ge=0, le=1e12)
    realized_gain: Decimal | None = Field(default=None, ge=-1e12, le=1e12)
    notes: str = Field(default="", max_length=10000)


class ScenarioInput(Input):
    name: str = Field(default="Custom scenario", min_length=1, max_length=120)
    shocks: dict[str, float] = Field(max_length=100)

    @field_validator("shocks")
    @classmethod
    def validate_shocks(cls, value):
        import math

        for k, v in value.items():
            if (
                len(k) > 140
                or not (k == "market" or k.startswith(("symbol:", "sector:", "type:")))
                or not math.isfinite(v)
                or not -1 <= v <= 5
            ):
                raise ValueError(
                    "Use market, symbol:, sector: or type: with shocks from -1 to 5"
                )
        return value


class SimulatorInput(Input):
    starting: float = Field(ge=0, le=1e12)
    monthly: float = Field(ge=0, le=1e9)
    annual_return: float = Field(default=0.07, ge=-0.95, le=1)
    years: int = Field(default=20, ge=1, le=80)
    inflation: float = Field(default=0.025, ge=0, le=0.3)
    contribution_growth: float = Field(default=0, ge=-0.5, le=0.5)


class AIInput(Input):
    question: str = Field(min_length=3, max_length=1000)


class FlowInput(Input):
    external_flow: Decimal = Field(ge=-1e12, le=1e12)
    contributions: Decimal | None = Field(default=None, ge=-1e12, le=1e12)
