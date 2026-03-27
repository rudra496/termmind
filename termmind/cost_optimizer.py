"""Cost Optimizer — track and optimize API costs across providers."""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Cost per 1K tokens for each provider (approximate)
PRICING = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    },
    "anthropic": {
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-haiku-4-20250414": {"input": 0.0008, "output": 0.004},
        "claude-opus-4-20250514": {"input": 0.015, "output": 0.075},
    },
    "gemini": {
        "gemini-2.0-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    },
    "groq": {
        "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
        "mixtral-8x7b-32768": {"input": 0.00024, "output": 0.00024},
    },
    "together": {
        "meta-llama/Llama-3-70b-chat-hf": {"input": 0.00088, "output": 0.00088},
        "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": 0.00024, "output": 0.00024},
    },
    "openrouter": {
        "_default": {"input": 0.01, "output": 0.03},
    },
    "ollama": {
        "_default": {"input": 0.0, "output": 0.0},
    },
}

class CostOptimizer:
    """Track and optimize API costs across providers."""

    def __init__(self, config_dir: str = "~/.termmind"):
        self.config_dir = Path(config_dir).expanduser()
        self.history_file = self.config_dir / "cost_history.json"
        self.session_costs: List[Dict] = []
        self.budget: Optional[float] = None
        self.budget_warned = False
        self._load_history()

    def _load_history(self) -> None:
        """Load cost history from file."""
        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text())
                self.session_costs = data.get("sessions", [])
            except (json.JSONDecodeError, KeyError):
                self.session_costs = []

    def _save_history(self) -> None:
        """Save cost history to file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "sessions": self.session_costs[-1000],  # Keep last 1000
            "last_updated": datetime.now().isoformat(),
        }
        self.history_file.write_text(json.dumps(data, indent=2))

    def get_pricing(self, provider: str, model: str) -> Dict[str, float]:
        """Get pricing for a provider+model combo."""
        provider_prices = PRICING.get(provider, {})
        if model in provider_prices:
            return provider_prices[model]
        if "_default" in provider_prices:
            return provider_prices["_default"]
        return {"input": 0.01, "output": 0.03}  # Fallback estimate

    def estimate_cost(self, provider: str, model: str,
                      input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a single request."""
        prices = self.get_pricing(provider, model)
        return (input_tokens * prices["input"] / 1000 +
                output_tokens * prices["output"] / 1000)

    def record_request(self, provider: str, model: str,
                       input_tokens: int, output_tokens: int) -> Dict:
        """Record a request and return cost info."""
        cost = self.estimate_cost(provider, model, input_tokens, output_tokens)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6),
        }
        self.session_costs.append(entry)
        self._save_history()

        # Check budget
        budget_alert = None
        if self.budget is not None:
            total = self.get_session_total()
            pct = (total / self.budget) * 100 if self.budget > 0 else 0
            if pct >= 100 and not self.budget_warned:
                budget_alert = f"⚠️ Budget exceeded! ${total:.2f} / ${self.budget:.2f}"
                self.budget_warned = True
            elif pct >= 80 and not self.budget_warned:
                budget_alert = f"⚠️ Approaching budget: ${total:.2f} / ${self.budget:.2f} ({pct:.0f}%)"

        return {"cost": cost, "budget_alert": budget_alert}

    def get_session_total(self) -> float:
        """Get total cost for current session (today)."""
        today = datetime.now().strftime("%Y-%m-%d")
        return sum(
            e["cost"] for e in self.session_costs
            if e["timestamp"].startswith(today)
        )

    def get_total_all_time(self) -> float:
        """Get total cost across all sessions."""
        return sum(e["cost"] for e in self.session_costs)

    def set_budget(self, amount: float) -> None:
        """Set a session budget."""
        self.budget = amount
        self.budget_warned = False

    def get_budget_status(self) -> Optional[Dict]:
        """Get budget status."""
        if self.budget is None:
            return None
        total = self.get_session_total()
        return {
            "budget": self.budget,
            "spent": round(total, 4),
            "remaining": round(max(0, self.budget - total), 4),
            "percent": round((total / self.budget) * 100, 1) if self.budget > 0 else 0,
        }

    def get_breakdown_by_provider(self) -> Dict[str, float]:
        """Get cost breakdown by provider for current session."""
        today = datetime.now().strftime("%Y-%m-%d")
        breakdown = {}
        for entry in self.session_costs:
            if entry["timestamp"].startswith(today):
                p = entry["provider"]
                breakdown[p] = breakdown.get(p, 0) + entry["cost"]
        return {k: round(v, 4) for k, v in sorted(breakdown.items(), key=lambda x: -x[1])}

    def get_breakdown_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by model for current session."""
        today = datetime.now().strftime("%Y-%m-%d")
        breakdown = {}
        for entry in self.session_costs:
            if entry["timestamp"].startswith(today):
                m = f"{entry['provider']}/{entry['model']}"
                breakdown[m] = breakdown.get(m, 0) + entry["cost"]
        return {k: round(v, 4) for k, v in sorted(breakdown.items(), key=lambda x: -x[1])}

    def get_daily_history(self, days: int = 30) -> List[Dict]:
        """Get daily cost totals for the last N days."""
        daily = {}
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        for entry in self.session_costs:
            day = entry["timestamp"][:10]
            if day >= cutoff:
                daily[day] = daily.get(day, 0) + entry["cost"]
        return [{"date": k, "cost": round(v, 4)} for k, v in sorted(daily.items())]

    def get_token_stats(self) -> Dict[str, int]:
        """Get total tokens used in current session."""
        today = datetime.now().strftime("%Y-%m-%d")
        stats = {"input": 0, "output": 0, "total": 0, "requests": 0}
        for entry in self.session_costs:
            if entry["timestamp"].startswith(today):
                stats["input"] += entry["input_tokens"]
                stats["output"] += entry["output_tokens"]
                stats["requests"] += 1
        stats["total"] = stats["input"] + stats["output"]
        return stats

    def compare_providers(self, input_tokens: int, output_tokens: int) -> List[Dict]:
        """Compare estimated costs across all providers."""
        comparisons = []
        for provider, models in PRICING.items():
            for model, prices in models.items():
                if model.startswith("_"):
                    continue
                cost = (input_tokens * prices["input"] / 1000 +
                        output_tokens * prices["output"] / 1000)
                comparisons.append({
                    "provider": provider,
                    "model": model,
                    "cost": round(cost, 6),
                    "input_per_1k": prices["input"],
                    "output_per_1k": prices["output"],
                })
        return sorted(comparisons, key=lambda x: x["cost"])

    def suggest_savings(self, provider: str, model: str,
                        input_tokens: int, output_tokens: int) -> List[Dict]:
        """Suggest cheaper alternatives for current usage."""
        current_cost = self.estimate_cost(provider, model, input_tokens, output_tokens)
        alternatives = []
        comparisons = self.compare_providers(input_tokens, output_tokens)
        for comp in comparisons:
            if comp["cost"] < current_cost and comp["provider"] != provider:
                savings_pct = round((1 - comp["cost"] / current_cost) * 100, 1)
                savings_amt = round(current_cost - comp["cost"], 6)
                alternatives.append({
                    "provider": comp["provider"],
                    "model": comp["model"],
                    "cost": comp["cost"],
                    "savings_percent": savings_pct,
                    "savings_amount": savings_amt,
                })
        return sorted(alternatives, key=lambda x: -x["savings_percent"])[:5]

    def optimize_context(self, messages: List[Dict], provider: str, model: str) -> Dict:
        """Analyze context and suggest optimizations to save tokens."""
        total_tokens = sum(len(str(m.get("content", "")).split()) * 1.3
                         for m in messages)
        prices = self.get_pricing(provider, model)
        current_cost = (total_tokens * prices["input"] / 1000 +
                       (total_tokens * 0.3) * prices["output"] / 1000)

        suggestions = []
        # Check for long messages
        long_msgs = [(i, len(str(m.get("content", "")))) for i, m in enumerate(messages)
                     if len(str(m.get("content", ""))) > 5000]
        if long_msgs:
            savings = sum(len(content) for _, content in long_msgs) * 0.3 * 1.3
            suggestions.append({
                "type": "truncate_long_messages",
                "description": f"{len(long_msgs)} messages over 5000 chars can be truncated",
                "estimated_savings_tokens": int(savings),
            })

        # Check for repeated content
        content_hashes = {}
        for i, m in enumerate(messages):
            c = str(m.get("content", ""))[:200]
            if c in content_hashes:
                suggestions.append({
                    "type": "duplicate_content",
                    "description": f"Messages {content_hashes[c]} and {i} start similarly",
                    "estimated_savings_tokens": 500,
                })
            content_hashes[c] = i

        # Check old messages
        if len(messages) > 10:
            removable = len(messages) - 6
            savings = sum(len(str(m.get("content", "")).split()) for m in messages[:removable]) * 1.3
            suggestions.append({
                "type": "remove_old_messages",
                "description": f"Remove {removable} oldest messages, keep last 6",
                "estimated_savings_tokens": int(savings),
            })

        return {
            "current_context_tokens": int(total_tokens),
            "estimated_request_cost": round(current_cost, 6),
            "suggestions": suggestions,
            "total_potential_savings_tokens": sum(s["estimated_savings_tokens"] for s in suggestions),
        }

    def get_analysis_text(self) -> str:
        """Get a formatted text analysis of costs."""
        lines = ["💰 Cost Analysis — Current Session\n"]

        # Token stats
        tokens = self.get_token_stats()
        lines.append(f"  Tokens: {tokens['input']:,} in / {tokens['output']:,} out ({tokens['requests']} requests)")

        # Session total
        total = self.get_session_total()
        lines.append(f"  Session Cost: ${total:.4f}")

        # All-time
        all_time = self.get_total_all_time()
        lines.append(f"  All-time Cost: ${all_time:.4f}")

        # Budget
        budget = self.get_budget_status()
        if budget:
            bar_len = 20
            filled = int(bar_len * budget["percent"] / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"  Budget: [{bar}] {budget['percent']:.0f}% (${budget['spent']:.2f} / ${budget['budget']:.2f})")

        # Provider breakdown
        by_provider = self.get_breakdown_by_provider()
        if by_provider:
            lines.append("\n  By Provider:")
            for p, c in by_provider.items():
                pct = (c / total * 100) if total > 0 else 0
                lines.append(f"    {p}: ${c:.4f} ({pct:.0f}%)")

        # Daily history (last 7 days)
        daily = self.get_daily_history(7)
        if len(daily) > 1:
            lines.append("\n  Last 7 Days:")
            for d in daily:
                lines.append(f"    {d['date']}: ${d['cost']:.4f}")

        return "\n".join(lines)
