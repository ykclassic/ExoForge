import logging
import json
import aiohttp
from typing import Dict, Any, Optional
from decimal import Decimal

from src.config import EnvironmentConfig
from src.models.trade import Trade
from src.models.signal import Signal

logger = logging.getLogger("trading.monitoring.alerts")

class DiscordAlerter:
    """
    Asynchronous notification engine for Discord.
    Broadcasts trade lifecycle events, risk triggers, and critical errors.
    """

    def __init__(self, config: EnvironmentConfig):
        self.webhook_url = config.DISCORD_WEBHOOK_URL
        self.environment = config.ENVIRONMENT
        self.enabled = bool(self.webhook_url and self.webhook_url.strip())
        
        if not self.enabled:
            logger.warning("Discord webhook URL not provided. Alerts are disabled.")

    async def _send_payload(self, embed: Dict[str, Any]) -> bool:
        """Fires the HTTP POST request to the Discord Webhook."""
        if not self.enabled:
            return False

        payload = {
            "username": f"EXOFORGE Bot ({self.environment.upper()})",
            "avatar_url": "https://i.imgur.com/x4WvQ9M.png",
            "embeds": [embed]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status not in (200, 204):
                        logger.error(f"Discord API Error [{response.status}]: Failed to send alert.")
                        return False
            return True
        except Exception as e:
            logger.error(f"Network error while sending Discord alert: {str(e)}")
            return False

    async def notify_trade_entry(self, trade: Trade, signal: Signal):
        """Sends an alert when a new position is successfully opened."""
        color = 0x00FF00 if trade.direction.name == "LONG" else 0xFF0000
        
        embed = {
            "title": f"🚨 NEW POSITION OPENED: {trade.pair}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": trade.direction.name, "inline": True},
                {"name": "Entry Price", "value": f"${trade.entry_price:,.4f}", "inline": True},
                {"name": "Position Size", "value": f"{trade.position_size}", "inline": True},
                {"name": "Stop Loss", "value": f"${trade.stop_loss:,.4f}", "inline": True},
                {"name": "Take Profit 1", "value": f"${trade.take_profit_1:,.4f}", "inline": True},
                {"name": "Risk Amount", "value": f"${signal.risk_amount:,.2f}", "inline": True},
            ],
            "footer": {"text": f"Trade ID: {trade.trade_id[:8]}... | Market Regime: {signal.market_regime.name}"}
        }
        await self._send_payload(embed)

    async def notify_trade_exit(self, trade: Trade, exit_reason: str):
        """Sends an alert when a position is closed, summarizing the PnL."""
        if trade.pnl is None:
            trade.pnl = Decimal('0.0')
            
        is_profit = trade.pnl > Decimal('0.0')
        color = 0x00FF00 if is_profit else 0xFF0000
        pnl_symbol = "+" if is_profit else ""

        embed = {
            "title": f"🔒 POSITION CLOSED: {trade.pair}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": trade.direction.name, "inline": True},
                {"name": "Exit Reason", "value": exit_reason, "inline": True},
                {"name": "Exit Price", "value": f"${trade.exit_price:,.4f}", "inline": True},
                {"name": "Realized PnL", "value": f"{pnl_symbol}${trade.pnl:,.2f}", "inline": True},
                {"name": "PnL %", "value": f"{pnl_symbol}{trade.pnl_percent:,.2f}%", "inline": True},
                {"name": "Duration (m)", "value": str(trade.hold_time_minutes or "N/A"), "inline": True},
            ],
            "footer": {"text": f"Trade ID: {trade.trade_id[:8]}..."}
        }
        await self._send_payload(embed)

    async def notify_risk_limit(self, reason: str, details: str):
        """Alerts administrators when a portfolio circuit breaker is tripped."""
        embed = {
            "title": "⚠️ RISK CIRCUIT BREAKER TRIPPED",
            "color": 0xFFA500,
            "description": "The bot has halted new trade execution due to a risk threshold breach.",
            "fields": [
                {"name": "Breach Reason", "value": reason, "inline": False},
                {"name": "Current Status", "value": details, "inline": False},
            ],
            "footer": {"text": "Manual intervention may be required."}
        }
        await self._send_payload(embed)

    async def notify_system_error(self, component: str, error_msg: str):
        """Alerts administrators of critical system failures."""
        
        # Safely format the error block using triple quotes to prevent literal newline syntax errors
        formatted_error = f"""```text
{error_msg[:1000]}
```"""
        
        embed = {
            "title": "❌ CRITICAL SYSTEM ERROR",
            "color": 0x000000,
            "description": f"Failure detected in **{component}**.",
            "fields": [
                {"name": "Error Details", "value": formatted_error, "inline": False},
            ]
        }
        await self._send_payload(embed)
