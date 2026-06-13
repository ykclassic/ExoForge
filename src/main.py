import os
import asyncio
import signal as os_signal
import sys
import logging
from decimal import Decimal
import pandas as pd
from aiohttp import web

from src.config import get_settings
from src.logger import trading_logger, error_logger
from src.data.database import DatabaseClient
from src.execution.exchange_client import GateIOClient
from src.execution.order_manager import OrderManager
from src.monitoring.alerts import DiscordAlerter
from src.risk.risk_manager import PortfolioRiskManager
from src.risk.position_sizing import PositionSizer
from src.strategy.signal_generator import SignalGenerator

class BotOrchestrator:
    """
    Master orchestrator that ties all modules together.
    Manages the event loop, state dependencies, live data fetching, and execution.
    """
    
    def __init__(self):
        self.is_running = False
        self.env_settings, self.yaml_settings = get_settings()
        
        # Initialize Core Modules
        self.db = DatabaseClient(self.env_settings)
        self.exchange = GateIOClient(self.env_settings)
        self.alerter = DiscordAlerter(self.env_settings)
        
        self.order_manager = OrderManager(self.exchange)
        self.risk_manager = PortfolioRiskManager(self.yaml_settings)
        self.position_sizer = PositionSizer(fractional_multiplier=Decimal('0.25'))
        self.signal_generator = SignalGenerator()
        
        self.active_trades = []

    async def initialize(self):
        """Prepares asynchronous connections before starting the loop."""
        trading_logger.info("Initializing MarketForge-Apex Bot infrastructure...")
        await self.db.initialize_schema()
        trading_logger.info("Database schema validated.")
        
        test_ticker = await self.exchange.get_ticker("BTC_USDT")
        if not test_ticker:
            raise ConnectionError("Failed to connect to Gate.io API. Check credentials.")
        trading_logger.info("Exchange API connectivity verified.")

    async def shutdown(self):
        """Ensures all connections and resources are closed gracefully."""
        trading_logger.info("Initiating graceful shutdown sequence...")
        self.is_running = False
        await self.exchange.close()
        await self.db.close()
        await self.alerter.notify_system_error("Orchestrator", "Bot has been gracefully shut down.")
        trading_logger.info("Shutdown complete.")
        sys.exit(0)

    def register_signal_handlers(self):
        """Catches OS-level termination signals for Docker deployments."""
        loop = asyncio.get_running_loop()
        for sig in (os_signal.SIGINT, os_signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

    async def fetch_dataframe(self, symbol: str, interval: str) -> pd.DataFrame:
        """Fetches live OHLCV data from Gate.io and parses it into a DataFrame."""
        try:
            # Gate.io V4 candlestick format: 
            # [timestamp, quote_volume, close, high, low, open, base_volume, is_closed]
            response = await self.exchange._request(
                "GET", 
                "/spot/candlesticks", 
                {"currency_pair": symbol, "interval": interval, "limit": 200}
            )
            
            if not response or not isinstance(response, list):
                return pd.DataFrame()
                
            # Properly mapping all 8 elements returned by the exchange
            df = pd.DataFrame(response, columns=["timestamp", "quote_volume", "close", "high", "low", "open", "volume", "is_closed"])
            
            # Convert numeric columns to float, ensuring TA tools receive standard data types
            for col in ["quote_volume", "close", "high", "low", "open", "volume"]:
                df[col] = df[col].astype(float)
                
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
            df.set_index("timestamp", inplace=True)
            return df.sort_index()
            
        except Exception as e:
            error_logger.error(f"Error fetching data for {symbol} at {interval}: {str(e)}")
            return pd.DataFrame()

    async def run_market_cycle(self):
        """
        The core logic loop executed periodically.
        Fetches live data, evaluates confluence, manages risk, and executes trades.
        """
        trading_logger.info("Initiating live market cycle analysis...")
        
        # In a complete implementation, balance would be fetched via exchange API. 
        # Simulated here safely for the scope of the risk engine context.
        current_account_balance = Decimal('10000.00') 
        realized_pnl_today = Decimal('0.00')
        peak_equity = Decimal('10000.00')
        
        for symbol in self.yaml_settings.symbols:
            # 1. Fetch live market data
            df_4h = await self.fetch_dataframe(symbol, "4h")
            df_1h = await self.fetch_dataframe(symbol, "1h")
            df_15m = await self.fetch_dataframe(symbol, "15m")
            
            if df_4h.empty or df_1h.empty or df_15m.empty:
                trading_logger.warning(f"Incomplete dataset for {symbol}. Skipping analysis.")
                continue

            # 2. Generate Signals
            signal = self.signal_generator.analyze_confluence(symbol, df_4h, df_1h, df_15m)
            
            if signal:
                # 3. Validate Trade Proposal (Risk Management)
                is_approved, reason = self.risk_manager.validate_trade_proposal(
                    signal=signal,
                    active_trades=self.active_trades,
                    realized_pnl_today=realized_pnl_today,
                    peak_equity=peak_equity,
                    current_equity=current_account_balance
                )
                
                if not is_approved:
                    trading_logger.info(f"Signal rejected by Risk Manager: {reason}")
                    continue
                    
                # 4. Calculate Position Size
                # Using hardcoded historical win rate for the calculation model
                historical_win_rate = Decimal('0.45') 
                current_atr = Decimal(str(df_15m.iloc[-1]['ATR_14'])) if 'ATR_14' in df_15m else Decimal('1.0')
                avg_atr = Decimal(str(df_15m['ATR_14'].mean())) if 'ATR_14' in df_15m else Decimal('1.0')

                risk_amount = self.position_sizer.determine_trade_size(
                    account_balance=current_account_balance,
                    signal=signal,
                    historical_win_rate=historical_win_rate,
                    current_atr=current_atr,
                    average_atr=avg_atr
                )
                
                # Update signal with calculated sizes
                # Ensure entry price is non-zero to avoid division errors
                if risk_amount > 0 and signal.entry_price > 0:
                    position_qty = risk_amount / signal.entry_price
                    # Use object.__setattr__ since Signal dataclass is frozen
                    object.__setattr__(signal, 'risk_amount', risk_amount)
                    object.__setattr__(signal, 'position_size', position_qty.quantize(Decimal('0.00000001')))
                    
                    # 5. Execute Signal
                    trade, order = await self.order_manager.execute_signal(signal)
                    
                    # 6. Save State and Alert
                    if trade and order:
                        await self.db.save_signal(signal)
                        await self.db.save_trade(trade)
                        await self.db.save_order(order)
                        self.active_trades.append(trade)
                        await self.alerter.notify_trade_entry(trade, signal)

    async def run(self):
        """Main execution loop."""
        await self.initialize()
        self.register_signal_handlers()
        
        self.is_running = True
        trading_logger.info("MarketForge-Apex main loop active. Listening to market data.")
        
        try:
            while self.is_running:
                await self.run_market_cycle()
                await asyncio.sleep(60 * 15) # Standard 15-minute intervals
                
        except Exception as e:
            error_logger.critical(f"Fatal error in main loop: {str(e)}")
            await self.alerter.notify_system_error("Main Loop", str(e))
            await self.shutdown()

# ---------------------------------------------------------
# Web Server Layer (Render Health Checks)
# ---------------------------------------------------------

async def health_check(request):
    """Minimal endpoint to satisfy Render's web service requirements."""
    return web.Response(text="MarketForge-Apex Trading Bot is currently active and healthy.", status=200)

async def run_web_server():
    """Initializes the background web server."""
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    trading_logger.info(f"Health check web server listening on port {port}.")

async def main():
    """Entry point combining the web server and the trading orchestrator."""
    orchestrator = BotOrchestrator()
    await asyncio.gather(
        run_web_server(),
        orchestrator.run()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
