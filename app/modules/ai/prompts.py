"""Prompt engineering and structured templates for Gemma 2 (2B) inference."""

import json
from typing import Any, Dict


SYSTEM_PROMPT_JSON = (
    "You are an expert autonomous logistics Control Tower AI specialized in supply chain risk, "
    "incident diagnosis, and tactical recovery operations. "
    "You MUST respond ONLY with a single valid, parseable JSON object matching the requested schema. "
    "Do NOT include markdown formatting, backticks, preamble, or explanations outside the JSON."
)


def build_root_cause_prompt(context: Dict[str, Any]) -> str:
    """Constructs prompt for root cause synthesis tailored for gemma2:2b."""
    return f"""Analyze the following shipment exception and synthesize the root cause.

Shipment Details:
- Reference: {context.get('shipment_reference')}
- Carrier: {context.get('carrier_code')}
- Origin: {context.get('origin')} -> Destination: {context.get('destination')}
- Commodity / Cargo: {context.get('cargo_type')}
- Temperature Sensitive: {context.get('is_temp_sensitive')} (Range: {context.get('temp_min')}C to {context.get('temp_max')}C)
- Exception Type: {context.get('exception_type')}
- Severity: {context.get('severity')}
- Description: {context.get('description')}
- Latest Telemetry / Events: {json.dumps(context.get('recent_events', []))}
- Estimated Financial Exposure: ${context.get('estimated_financial_impact', 0):,.2f}

Produce a JSON response with EXACTLY this structure:
{{
  "synthesized_cause": "<concise 2-3 sentence diagnostic root cause analysis>",
  "contributing_factors": ["<factor 1>", "<factor 2>", "<factor 3>"],
  "severity_assessment": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "confidence_score": <float between 0.0 and 1.0>
}}
"""


def build_recovery_recommendation_prompt(context: Dict[str, Any]) -> str:
    """Constructs prompt for tactical recovery strategy selection."""
    valid_strategies = [
        "VEHICLE_REPLACEMENT",
        "CROSS_DOCK",
        "ROUTE_REDIRECT",
        "AIR_EXPEDITE",
        "WAREHOUSE_HOLD",
        "RETURN_TO_ORIGIN",
    ]
    return f"""Recommend the optimal recovery strategy for this logistics disruption.

Available Strategies: {', '.join(valid_strategies)}

Context:
- Exception: {context.get('exception_type')} (Severity: {context.get('severity')})
- Cargo: {context.get('cargo_type')}, Temp Sensitive: {context.get('is_temp_sensitive')}
- Customer Tier: {context.get('customer_tier')}
- Transit Route: {context.get('origin')} -> {context.get('destination')}
- Root Cause: {context.get('root_cause_summary')}
- Delay: {context.get('delay_hours', 0)} hours
- Priority Score: {context.get('priority_score', 50)}/100

Produce a JSON response with EXACTLY this structure:
{{
  "recommended_strategy": "<One of: VEHICLE_REPLACEMENT, CROSS_DOCK, ROUTE_REDIRECT, AIR_EXPEDITE, WAREHOUSE_HOLD, RETURN_TO_ORIGIN>",
  "suggested_action_type": "<tactical action category>",
  "rationale": "<compelling operational justification>",
  "estimated_cost_usd": <numeric estimated cost, e.g. 850.0>,
  "estimated_turnaround_hours": <numeric turnaround hours, e.g. 4.0>,
  "risk_tradeoffs": ["<tradeoff 1>", "<tradeoff 2>"],
  "confidence_score": <float between 0.0 and 1.0>
}}
"""


def build_customer_communication_prompt(context: Dict[str, Any]) -> str:
    """Constructs prompt for proactive customer email notification."""
    ref = context.get('shipment_reference', 'SHP-001')
    cust = context.get('customer_name', 'Valued Customer')
    return f"""Draft an empathetic, transparent customer email update for this shipment delay/exception.

Context:
- Customer Name: {cust}
- Recipient Email: {context.get('customer_email')}
- Shipment Reference: {ref}
- Route: {context.get('origin')} to {context.get('destination')}
- Exception Type: {context.get('exception_type')}
- Current Status: {context.get('exception_status')}
- Mitigation Action: {context.get('recovery_action', 'Dispatched response team to expedite delivery')}
- Estimated Delay: {context.get('delay_hours', 0)} hours

Write a complete, professional email body of at least 2-3 sentences explaining the situation and reassurance.

Produce a JSON response with EXACTLY this structure:
{{
  "email_subject": "Shipment Advisory: Transit Update for Order {ref}",
  "email_body": "Dear {cust},\\n\\nWe are writing to provide a transparent update regarding shipment {ref}. Our control tower identified an operational delay and has initiated mitigation procedures to expedite delivery. Your projected delivery window is adjusted by approximately {context.get('delay_hours', 4)} hours.\\n\\nSincerely,\\nControl Tower Operations Team",
  "tone": "Empathetic & Professional"
}}
"""
