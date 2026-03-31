from __future__ import annotations

import json
import os
import re
from typing import Any

from evolutionary_sde.models import CostBenefitRequest, FounderScore

_SYSTEM_PROMPT = """You are a staff engineer + founder advisor scoring infrastructure choices.
Return ONLY valid JSON with keys:
score_1_to_10 (integer 1-10),
summary (string, 2-4 sentences),
cheaper_alternative (string or null),
deployment_speed_note (string or null),
justify_prompt (string: a sharp challenge to the user, e.g. SQS cheaper / faster deploy),
risks (array of short strings).

Be concrete about Kafka vs SQS vs Redis streams vs RabbitMQ: ordering, ops burden, cost drivers, replay."""

_USER_TEMPLATE = """Design summary:
{summary}

Primary choice: {primary}
Alternatives to contrast: {alts}
Workload hints (JSON): {hints}

Challenge the user like a founder: if another option is materially cheaper or faster to ship, say so."""


def analyze_cost_benefit(req: CostBenefitRequest) -> FounderScore:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        try:
            return _analyze_openai(req)
        except Exception:
            pass
    return _analyze_heuristic(req)


def _analyze_openai(req: CostBenefitRequest) -> FounderScore:
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            "openai package not installed. Run: pip install 'evolutionary-sde[openai]'"
        ) from e

    client = OpenAI()
    user = _USER_TEMPLATE.format(
        summary=req.design_summary.strip(),
        primary=req.primary_choice.strip(),
        alts=", ".join(req.alternatives) or "(none)",
        hints=json.dumps(req.workload_hints, default=str),
    )
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    data: dict[str, Any] = json.loads(raw)
    return FounderScore(
        score_1_to_10=_clamp_int(data.get("score_1_to_10"), 7),
        summary=str(data.get("summary") or "").strip() or "See raw_model.",
        cheaper_alternative=_none_if_empty(data.get("cheaper_alternative")),
        deployment_speed_note=_none_if_empty(data.get("deployment_speed_note")),
        justify_prompt=str(
            data.get("justify_prompt")
            or "Justify your primary choice vs the cheapest viable alternative."
        ).strip(),
        risks=[str(x) for x in (data.get("risks") or []) if str(x).strip()][:8],
        raw_model=raw[:8000],
    )


def _analyze_heuristic(req: CostBenefitRequest) -> FounderScore:
    primary = req.primary_choice.strip().lower()
    alts = {a.strip().lower() for a in req.alternatives if a.strip()}
    cheaper = None
    deploy = None
    score = 6
    risks: list[str] = []

    if "kafka" in primary:
        cheaper = "Amazon SQS or SNS+SQS often cheaper at moderate volume; fewer moving parts."
        deploy = "SQS is typically faster to deploy than operating Kafka (MSK / self-managed)."
        score = 6
        risks.extend(
            [
                "Kafka ops: partition sizing, consumer lag, replay discipline",
                "Overkill cost if you only need a work queue without ordering / replay",
            ]
        )
    elif "sqs" in primary:
        cheaper = "Redis Streams or RabbitMQ on small footprint can reduce per-message cost at high churn."
        deploy = "SQS is already among the fastest paths on AWS for a managed queue."
        score = 7
        risks.extend(["FIFO throughput limits", "Visibility timeout tuning for long jobs"])
    elif "redis" in primary:
        cheaper = "Memcached for pure cache; SQS/Kafka for durable workflows — Redis is not always cheapest."
        deploy = "Redis is quick to adopt but persistence / HA add operational surface."
        score = 6
        risks.extend(["Memory-bound failures", "Hot key pressure", "Durability vs latency trade-offs"])
    else:
        cheaper = "Compare managed queue (SQS) vs log (Kafka) vs broker (RabbitMQ) for your ordering needs."
        deploy = "Favor the option your cloud already standardizes on to reduce toil."
        score = 6

    if "sqs" in alts and "kafka" in primary:
        justify = (
            f"You chose **{req.primary_choice}**. **SQS** is often cheaper per million requests at moderate "
            "scale and faster to wire up — justify Kafka if you need partition ordering, replay, or "
            "multi-subscriber log semantics."
        )
    elif "kafka" in alts and "sqs" in primary:
        justify = (
            f"You chose **{req.primary_choice}**. **Kafka** gives ordering + replay + fan-out — "
            "if you only enqueue jobs, you may be paying complexity without benefit."
        )
    else:
        justify = (
            f"You chose **{req.primary_choice}**. Pick the cheapest option that still meets your "
            "**ordering**, **durability**, and **replay** requirements — then defend the gap you accepted."
        )

    summary = (
        "Heuristic pass (set OPENAI_API_KEY for LLM nuance). "
        f"Primary=`{req.primary_choice}`. Stress-test: cost of egress, broker hours, consumer fleet, "
        "and engineer time to operate."
    )
    return FounderScore(
        score_1_to_10=score,
        summary=summary,
        cheaper_alternative=cheaper,
        deployment_speed_note=deploy,
        justify_prompt=justify,
        risks=risks[:8],
        raw_model=None,
    )


def _clamp_int(v: Any, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(1, min(10, n))


def _none_if_empty(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def parse_founder_score_from_text(text: str) -> FounderScore | None:
    """Best-effort parse if a model returns markdown-wrapped JSON."""
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return None
    return FounderScore(
        score_1_to_10=_clamp_int(data.get("score_1_to_10"), 5),
        summary=str(data.get("summary") or ""),
        cheaper_alternative=_none_if_empty(data.get("cheaper_alternative")),
        deployment_speed_note=_none_if_empty(data.get("deployment_speed_note")),
        justify_prompt=str(data.get("justify_prompt") or ""),
        risks=[str(x) for x in (data.get("risks") or [])][:8],
        raw_model=text[:8000],
    )
