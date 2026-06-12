import asyncio
import sys
from config import get_settings
from logger import trading_logger, error_logger

async def main():
    """Main application entry point for the EXOFORGE Bot."""
    try:
        # 1. Load Configurations securely
        env_settings, yaml_settings = get_settings()
        trading_logger.info(f"Starting EXOFORGE Bot in {env_settings.ENVIRONMENT} mode.")
        trading_logger.info(f"Loaded {len(yaml_settings.symbols)} symbols for tracking.")

        # Phase 2-8 Modules will be initialized here
        # e.g., db_pool = await setup_database(env_settings.SUPABASE_DB_URL)
        # e.g., gateio_client = GateIOClient(api_key, api_secret)

        trading_logger.info("Initialization complete. Awaiting signal engine execution...")
        
        # Keep process alive for async scheduling
        while True:
            await asyncio.sleep(60)

    except Exception as e:
        error_logger.critical(f"Critical system failure on startup: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        trading_logger.info("Bot execution manually terminated. Initiating graceful shutdown.")
