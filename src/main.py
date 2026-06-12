import asyncio
import signal as os_signal
import sys
import logging
from decimal import Decimal

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
    Manages the event loop, state dependencies, and graceful shutdowns.
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
        self.position_sizer = PositionSizer()
        self.signal_generator = SignalGenerator()
        
        self.active_trades = []

    async def initialize(self):
        """Prepares asynchronous connections before starting the loop."""
        trading_logger.info("Initializing EXOFORGE Bot infrastructure...")
        await self.db.initialize_schema()
        trading_logger.info("Database schema validated.")
        
        # Validate Gate.io API connection by fetching a test ticker
        test_ticker = await self.exchange.get_ticker("BTC_USDT")
        if not test_ticker:
            raise ConnectionError("Failed to connect to Gate.io API. Check credentials and network.")
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
        """Catches OS-level termination signals for Docker/Render deployments."""
        loop = asyncio.get_running_loop()
        for sig in (os_signal.SIGINT, os_signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

    async def run_market_cycle(self):
        """
        The core logic loop executed periodically (e.g., every 15 minutes).
        Fetches data, evaluates confluence, manages risk, and executes trades.
        """
        # In a full deployment, you would fetch actual OHLCV DataFrames from the exchange here
        # df_4h, df_1h, df_15m = await fetch_market_data(self.exchange, symbol)
        
        trading_logger.info("Market cycle tick executed. Awaiting live data feed integration...")
        
        # Pseudo-code for live cycle execution:
        # 1. Fetch OHLCV data
        # 2. Check open trades & update PnL / Trailing Stops
        # 3. Generate Signals via self.signal_generator.analyze_confluence()
        # 4. Filter Signals via self.risk_manager.validate_trade_proposal()
        # 5. Size Positions via self.position_sizer.determine_trade_size()
        # 6. Execute via self.order_manager.execute_signal()
        # 7. Save to self.db & Notify via self.alerter

    async def run(self):
        """Main execution loop."""
        await self.initialize()
        self.register_signal_handlers()
        
        self.is_running = True
        trading_logger.info("EXOFORGE main loop active.")
        
        try:
            while self.is_running:
                await self.run_market_cycle()
                # Poll interval: Standard wait time between market evaluations
                await asyncio.sleep(60) 
                
        except Exception as e:
            error_logger.critical(f"Fatal error in main loop: {str(e)}")
            await self.alerter.notify_system_error("Main Loop", str(e))
            await self.shutdown()

async def main():
    orchestrator = BotOrchestrator()
    await orchestrator.run()

if __name__ == "__main__":
    asyncio.run(main())
