# Triangular Arbitrage Bot

A Python-based cryptocurrency trading bot that identifies and executes triangular arbitrage opportunities across multiple trading pairs on Binance.

## Overview

This bot continuously monitors cryptocurrency trading pairs to find profitable triangular arbitrage opportunities. It specifically looks for price discrepancies between three trading pairs that form a cycle, starting and ending with a stablecoin (USDT, USDC, BUSD, or FDUSD).

## Features

- Multi-threaded price monitoring and trade execution
- Supports multiple stablecoins as base currencies
- Configurable profit margins and trade amounts
- Automatic order book analysis
- Debug mode for testing without actual trades
- Efficient path caching system
- Rate limit handling
- Comprehensive logging

## Prerequisites

- Python 3.7+
- Binance API key and secret
- Active Binance account

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd triangular-arbitrage-bot
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with your Binance credentials:
```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET=your_secret_here
```

## Configuration

Key parameters can be adjusted in the main script:

- `TRADE_AMOUNT`: Base trade amount in USDT
- `PROFIT_MARGIN`: Minimum profit margin to execute trades
- `CHECK_INTERVAL`: Time between price checks (seconds)
- `DEBUG_MODE`: Enable/disable test mode without actual trading
- `MAX_PARALLEL_REQUESTS`: Limit concurrent API requests

## Usage

1. Start the bot:
```bash
python main.py
```

2. The bot will:
   - Initialize by finding valid triangular paths
   - Cache paths to disk for future use
   - Continuously monitor for profitable opportunities
   - Execute trades when opportunities are found (if not in debug mode)

## How It Works

1. **Path Generation**:
   - Identifies all possible triangular paths starting with stablecoins
   - Validates paths against available trading pairs
   - Caches valid paths to disk

2. **Arbitrage Detection**:
   - Monitors order books for all valid paths
   - Calculates potential profits including fees
   - Checks liquidity at each step

3. **Trade Execution**:
   - Executes trades when profit exceeds threshold
   - Handles all three trades in sequence
   - Includes safety checks and error handling

## Safety Features

- Sandbox mode support for testing
- Rate limit handling
- Liquidity checks before trade execution
- Comprehensive error handling
- Debug mode for risk-free testing

## Logging

The bot maintains detailed logs including:
- Initialization progress
- Path discovery
- Price checks
- Trade execution
- Errors and warnings

## Warning

Cryptocurrency trading involves significant risk. This bot is provided for educational purposes only. Always test thoroughly with small amounts before running with significant funds.

## License

[Your chosen license]

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.
