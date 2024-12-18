import ccxt
from dotenv import load_dotenv
import os
import time
import logging
import pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp
from functools import partial
from typing import Set, List, Tuple
from itertools import permutations

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configure your exchange
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_SECRET')
})
exchange.set_sandbox_mode(True)
# Configuration
TRADE_AMOUNT = 100  # Amount to trade per transaction (in USDT)
PROFIT_MARGIN = 0.003  # Minimum profit margin (e.g., 1%)
CHECK_INTERVAL = 3  # Check prices every 10 seconds
DEBUG_MODE = True  # Debug mode flag
PATHS_FILE = "triangular_paths.pkl"  # File to save/load triangular paths
MAX_PARALLEL_REQUESTS = 5  # Limit the number of parallel API requests

# Precomputed triangular arbitrage paths
triangular_paths = []


def save_paths_to_disk(paths):
    try:
        with open(PATHS_FILE, 'wb') as f:
            pickle.dump(paths, f)
        logging.info(f"Triangular paths saved to {PATHS_FILE}.")
    except Exception as e:
        logging.error(f"Error saving triangular paths: {e}")


def load_paths_from_disk():
    global triangular_paths
    try:
        with open(PATHS_FILE, 'rb') as f:
            triangular_paths = pickle.load(f)
        logging.info(f"Triangular paths loaded from {PATHS_FILE}.")
    except FileNotFoundError:
        logging.warning(f"{PATHS_FILE} not found. Generating new paths...")
    except Exception as e:
        logging.error(f"Error loading triangular paths: {e}")


def check_triangle_bidirectional(triangle: Tuple[str, str, str], active_pairs: Set[str]):
    """
    Check if a triangle combination exists in active pairs, ensuring a valid trading cycle that starts and ends with USDT.
    Returns the path of trades that completes the cycle, or None if no valid cycle exists.
    """
    try:
        # Define stable coins we want to use as base currency
        stable_coins = {'USDT', 'USDC', 'BUSD', 'FDUSD'}

        # Ensure first currency is a stablecoin
        if triangle[0] not in stable_coins:
            return None

        pairs = []
        start_currency = triangle[0]  # Must be USDT or another stablecoin
        current_currency = None

        # First trade: Stablecoin -> Crypto1
        # We need to BUY the second currency using our stablecoin
        a, b = triangle[0], triangle[1]
        pair = f"{b}/{a}"  # Format: CRYPTO/STABLECOIN

        if pair in active_pairs:
            pairs.append(pair)
            current_currency = b
        else:
            return None

        # Second trade: Crypto1 -> Crypto2
        b, c = triangle[1], triangle[2]
        forward = f"{current_currency}/{c}"
        reverse = f"{c}/{current_currency}"

        if forward in active_pairs:
            pairs.append(forward)
            current_currency = c
        elif reverse in active_pairs:
            pairs.append(reverse)
            current_currency = c
        else:
            return None

        # Final trade: Crypto2 -> Starting Stablecoin
        # We need to SELL our final crypto for our original stablecoin
        pair = f"{current_currency}/{start_currency}"

        if pair in active_pairs:
            pairs.append(pair)
        else:
            return None

        # Verify we have a complete cycle back to starting stablecoin
        if len(pairs) == 3:
            # Log the cycle for verification
            logging.debug(f"Found cycle: {start_currency} -> {' -> '.join(pairs)} -> {start_currency}")
            # Validate the cycle
            try:
                # Split first pair
                first_base, first_quote = pairs[0].split('/')
                if first_quote != start_currency:  # First trade should use our stablecoin
                    return None

                # Split last pair
                last_base, last_quote = pairs[2].split('/')
                if last_quote != start_currency:  # Last trade should give us back our stablecoin
                    return None

                # Validate currency flow
                currencies = [first_base]  # Start with what we buy
                for pair in pairs[1:]:  # Check subsequent trades
                    base, quote = pair.split('/')
                    if base != currencies[-1]:  # Must use what we have
                        return None
                    currencies.append(quote)

                # Final currency should be our stablecoin
                if currencies[-1] != start_currency:
                    return None

                return tuple(pairs)
            except:
                return None

        return None

    except Exception as e:
        logging.error(f"Error in check_triangle_bidirectional: {e}")
        return None


def process_chunk(chunk: List[Tuple[str, str, str]], active_pairs: Set[str]) -> List[Tuple[str, str, str]]:
    """Process a chunk of triangle combinations, checking both directions."""
    valid_paths = []
    for triangle in chunk:
        result = check_triangle_bidirectional(triangle, active_pairs)
        if result:
            valid_paths.append(result)
    return valid_paths


def init_triangular_paths():
    try:
        logging.info("Initializing triangular paths...")
        time.sleep(1)

        markets = exchange.load_markets()

        # Filter for only active pairs
        active_pairs = {
            pair['symbol']: pair
            for pair in markets.values()
            if pair['active']
        }

        active_pairs_strings = set()
        currencies = set()

        # Extract unique currencies and trading pairs
        for data in active_pairs.values():
            currencies.add(data['base'])
            currencies.add(data['quote'])
            active_pairs_strings.add(f"{data['base']}/{data['quote']}")

        # Define stablecoins we want to use as starting point
        stable_coins = {'USDT', 'USDC', 'BUSD', 'FDUSD'}

        # Remove stablecoins from general currency set to avoid duplicate combinations
        tradeable_currencies = currencies - stable_coins

        # Generate triangles ONLY starting with stablecoins
        all_triangles = []
        for stable in stable_coins:
            if stable in currencies:  # Only if the stablecoin exists in our pairs
                # Generate combinations of two other currencies
                for pair in permutations(tradeable_currencies, 2):
                    # Always put stablecoin first in the triangle
                    all_triangles.append((stable,) + pair)

        total_triangles = len(all_triangles)
        logging.info(f"Generated {total_triangles} potential triangles starting with stablecoins")

        # Process in chunks
        batch_size = 100000
        paths = []

        for i in range(0, total_triangles, batch_size):
            batch = all_triangles[i:i + batch_size]
            num_cpus = min(mp.cpu_count(), 6)
            chunk_size = len(batch) // num_cpus + 1
            chunks = [batch[j:j + chunk_size] for j in range(0, len(batch), chunk_size)]

            with mp.Pool(num_cpus) as pool:
                worker_func = partial(process_chunk, active_pairs=active_pairs_strings)
                results = pool.map(worker_func, chunks)

                for chunk_result in results:
                    paths.extend(chunk_result)

            logging.info(f"Processed {i + len(batch)}/{total_triangles} combinations...")

        # Save paths
        global triangular_paths
        triangular_paths = paths
        save_paths_to_disk(paths)

        # Log some example paths for verification
        logging.info(f"Initialized {len(paths)} triangular paths.")
        if paths:
            logging.info("Example paths found:")
            for path in paths[:5]:
                logging.info(f"Path: {' -> '.join(path)}")

    except Exception as e:
        logging.error(f"Error initializing triangular paths: {e}")
        raise


def get_order_book(pair):
    try:
        time.sleep(0.1)  # Add small delay between requests
        return exchange.fetch_order_book(pair, limit=5)  # Limit depth to reduce data
    except ccxt.BaseError as e:
        if "rate limit" in str(e).lower() or "banned" in str(e).lower():
            logging.error("Rate limit hit in order book fetch. Waiting...")
            time.sleep(10)  # Wait 10 seconds
            return None
        logging.error(f"Error fetching order book for {pair}: {e}")
        return None


def calculate_arbitrage_for_path(pair1, pair2, pair3):
    try:
        # Fetch order books
        order_book1 = get_order_book(pair1)
        order_book2 = get_order_book(pair2)
        order_book3 = get_order_book(pair3)

        if not order_book1 or not order_book2 or not order_book3:
            return None  # Skip if order books are invalid

        # Extract best prices and liquidity
        best_ask1, ask_volume1 = order_book1['asks'][0] if order_book1['asks'] else (None, None)
        best_bid1, bid_volume1 = order_book1['bids'][0] if order_book1['bids'] else (None, None)

        best_ask2, ask_volume2 = order_book2['asks'][0] if order_book2['asks'] else (None, None)
        best_bid2, bid_volume2 = order_book2['bids'][0] if order_book2['bids'] else (None, None)

        best_ask3, ask_volume3 = order_book3['asks'][0] if order_book3['asks'] else (None, None)
        best_bid3, bid_volume3 = order_book3['bids'][0] if order_book3['bids'] else (None, None)

        if not best_ask1 or not best_bid2 or not best_bid3:
            return None  # Skip if there are no valid prices

        # Adjust trade amount to available liquidity
        amount1 = min(TRADE_AMOUNT / best_ask1, ask_volume1)
        amount2 = min(amount1 * best_bid2, bid_volume2)
        amount3 = min(amount2 * best_bid3, bid_volume3)

        # Simulate triangular arbitrage
        final_amount = amount3  # After completing the triangular trade
        profit = final_amount - TRADE_AMOUNT
        profit_percentage = profit / TRADE_AMOUNT

        if profit_percentage > PROFIT_MARGIN:
            logging.info(f"Profitable opportunity found! {profit_percentage*100}")
            logging.info(f"Path: {pair1} -> {pair2} -> {pair3}")
            logging.info(f"Adjusted trade amounts: {amount1:.4f}, {amount2:.4f}, {amount3:.4f}")

            if DEBUG_MODE:
                logging.info("DEBUG MODE: Trades not executed. Simulated trade sequence:")
                logging.info(f"Simulate buy: {pair1} with amount {amount1:.4f}")
                logging.info(f"Simulate sell: {pair2} with amount {amount1 * best_bid2:.4f}")
                logging.info(f"Simulate sell: {pair3} with amount {amount2 * best_bid3:.4f}")
            else:
                execute_trades(pair1, pair2, pair3, amount1)

            return True  # Return True when a profitable trade is found



    except Exception as e:
        logging.error(f"Error calculating arbitrage for {pair1} -> {pair2} -> {pair3}: {e}")
    return None


def execute_trades(pair1, pair2, pair3, amount):
    try:
        # Step 1: Buy base -> quote1
        order1 = exchange.create_market_buy_order(pair1, amount)
        logging.info(f"Executed: {order1}")

        # Step 2: Trade quote1 -> quote2
        order2 = exchange.create_market_sell_order(pair2, order1['filled'])
        logging.info(f"Executed: {order2}")

        # Step 3: Trade quote2 -> base
        order3 = exchange.create_market_sell_order(pair3, order2['filled'])
        logging.info(f"Executed: {order3}")

    except Exception as e:
        logging.error(f"Error executing trades: {e}")


def calculate_triangular_arbitrage():
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
        futures = {executor.submit(calculate_arbitrage_for_path, *path): path for path in triangular_paths}

        # Stop as soon as a profitable opportunity is found
        for future in as_completed(futures):
            result = future.result()
            if result:
                logging.info("Profitable arbitrage executed. Stopping further checks.")
                break


if __name__ == "__main__":
    load_paths_from_disk()
    if not triangular_paths:
        init_triangular_paths()

    while True:
        logging.info("Starting triangular arbitrage check...")
        calculate_triangular_arbitrage()
        logging.info("Waiting for next check...")
        time.sleep(CHECK_INTERVAL)

