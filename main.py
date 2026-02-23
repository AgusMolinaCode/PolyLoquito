"""
Polymarket FastLoop Trader - Bot de Trading Automatizado
=========================================================
Opera mercados rápidos de BTC (5min y 15min) en Polymarket
usando momentum de precio de Binance como señal.

Variables de entorno (Railway):
  POLYMARKET_PRIVATE_KEY   → Tu clave privada (0x...)
  MAX_POSITION             → Máximo por trade (default: 3.0)
  MAX_TOTAL_SPEND          → Límite total de gasto (default: 20.0)
  LIVE                     → "true" para trades reales
  RUN_INTERVAL             → Segundos entre ciclos (default: 60)
  ASSETS                   → Assets a tradear, separados por coma (default: BTC)
  LOG_LEVEL                → DEBUG, INFO, WARNING, ERROR (default: INFO)

Uso:
  python main.py              # Modo servidor (loop continuo)
  python main.py --once       # Un solo ciclo
  python main.py --status     # Ver presupuesto y estado
  python main.py --reset      # Resetear presupuesto
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "assets": os.environ.get("ASSETS", "BTC").upper().split(","),
    "windows": ["5m", "15m"],
    "entry_threshold": 0.05,
    "min_momentum_pct": 0.5,
    "max_position": float(os.environ.get("MAX_POSITION", 3.0)),
    "min_position": 1.0,
    "max_total_spend": float(os.environ.get("MAX_TOTAL_SPEND", 20.0)),
    "lookback_minutes": 5,
    "min_time_remaining": 60,
    "volume_confidence": True,
    "polymarket_fee": 0.10,
    "run_interval": int(os.environ.get("RUN_INTERVAL", 60)),
}

# Endpoints
POLYMARKET_CLOB = "https://clob.polymarket.com"
POLYMARKET_GAMMA = "https://gamma-api.polymarket.com"
BINANCE_API = os.environ.get("BINANCE_API_URL", "https://data-api.binance.vision")

# Archivos de datos
DATA_DIR = "/app/data"
SPEND_FILE = f"{DATA_DIR}/total_spent.json"
LOG_FILE = f"{DATA_DIR}/bot.log"
STATE_FILE = f"{DATA_DIR}/state.json"

# ─── SETUP LOGGING ────────────────────────────────────────────────────────────


def setup_logging():
    """Configura logging a archivo y consola."""
    os.makedirs(DATA_DIR, exist_ok=True)

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger(__name__)


logger = setup_logging()

# ─── PERSISTENCIA ─────────────────────────────────────────────────────────────


def load_json(filepath: str, default: dict = None) -> dict:
    """Carga un archivo JSON o retorna default."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error cargando {filepath}: {e}")
    return default or {}


def save_json(filepath: str, data: dict):
    """Guarda datos en un archivo JSON."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        logger.error(f"Error guardando {filepath}: {e}")


def load_total_spent() -> float:
    """Carga el total gastado desde archivo."""
    data = load_json(SPEND_FILE, {"total_spent": 0.0})
    return float(data.get("total_spent", 0.0))


def save_total_spent(amount_to_add: float) -> float:
    """Agrega al total gastado y guarda."""
    current = load_total_spent()
    new_total = current + amount_to_add
    save_json(
        SPEND_FILE,
        {
            "total_spent": new_total,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(f"Presupuesto actualizado: ${new_total:.2f} gastado")
    return new_total


def load_state() -> dict:
    """Carga el estado del bot."""
    return load_json(STATE_FILE, {"trades": [], "last_run": None, "status": "stopped"})


def save_state(state: dict):
    """Guarda el estado del bot."""
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_json(STATE_FILE, state)


def add_trade(
    market_id: str, outcome: str, amount: float, ev: float, tx_hash: str = None
):
    """Registra un trade en el estado."""
    state = load_state()
    state["trades"].append(
        {
            "market_id": market_id,
            "outcome": outcome,
            "amount": amount,
            "ev": ev,
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    save_state(state)


# ─── CÁLCULO DE EV ────────────────────────────────────────────────────────────


def calculate_ev(
    yes_price: float, direction: str, momentum_pct: float
) -> Tuple[float, float, str, str]:
    """
    Calcula el Expected Value real después del fee del 10%.

    Returns:
        (ev, prob_acierto, outcome_token, razon)
    """
    fee = DEFAULT_CONFIG["polymarket_fee"]

    # Estimar probabilidad de acierto según momentum
    raw_extra = min(abs(momentum_pct) * 0.05, 0.20)
    prob_up = 0.50 + raw_extra

    if direction == "up":
        prob_acierto = prob_up
        token_price = yes_price
        outcome = "YES"
    else:
        prob_acierto = 1 - prob_up
        token_price = 1 - yes_price
        outcome = "NO"

    prob_falla = 1 - prob_acierto

    # Si el token ya está muy caro, no vale
    if token_price >= 0.95:
        return (
            -1,
            prob_acierto,
            outcome,
            f"Precio demasiado alto ({token_price:.3f}>0.95), sin valor",
        )

    ganancia_neta = (1 - token_price) * (1 - fee)
    ev = (prob_acierto * ganancia_neta) - (prob_falla * token_price)

    breakeven = token_price / (ganancia_neta + token_price)

    razon = (
        f"EV={ev:+.4f} | Prob={prob_acierto:.1%} (BE={breakeven:.1%}) | "
        f"{outcome}@{token_price:.3f} | Fee={fee:.0%}"
    )

    return ev, prob_acierto, outcome, razon


# ─── SEÑALES DE PRECIO ────────────────────────────────────────────────────────


def get_crypto_momentum(
    symbol: str = "BTCUSDT", lookback_minutes: int = 5
) -> Optional[Dict]:
    """
    Obtiene el momentum de precio desde Binance.

    Args:
        symbol: Par de trading (ej: BTCUSDT, ETHUSDT)
        lookback_minutes: Minutos de historial a analizar

    Returns:
        Dict con price_now, price_then, momentum_pct, direction, volume_ratio
    """
    try:
        r = requests.get(
            f"{BINANCE_API}/api/v3/klines",
            params={"symbol": symbol, "interval": "1m", "limit": lookback_minutes + 1},
            timeout=10,
        )
        r.raise_for_status()
        klines = r.json()

        if len(klines) < 2:
            logger.warning(f"Datos insuficientes de Binance para {symbol}")
            return None

        price_now = float(klines[-1][4])
        price_then = float(klines[0][4])
        momentum_pct = (price_now - price_then) / price_then * 100

        volumes = [float(k[5]) for k in klines[:-1]]
        avg_volume = sum(volumes) / len(volumes) if volumes else 1
        volume_ratio = float(klines[-1][5]) / avg_volume if avg_volume > 0 else 1.0

        return {
            "symbol": symbol,
            "price_now": price_now,
            "price_then": price_then,
            "momentum_pct": momentum_pct,
            "direction": "up" if momentum_pct > 0 else "down",
            "volume_ratio": volume_ratio,
        }
    except Exception as e:
        logger.error(f"Error obteniendo momentum de {symbol}: {e}")
        return None


def get_multi_asset_signals(assets: List[str]) -> Dict[str, Optional[Dict]]:
    """Obtiene señales para múltiples assets."""
    signals = {}
    for asset in assets:
        symbol = f"{asset}USDT"
        signals[asset] = get_crypto_momentum(symbol, DEFAULT_CONFIG["lookback_minutes"])
    return signals


# ─── POLYMARKET: MERCADOS ─────────────────────────────────────────────────────


def get_fast_markets(asset: str = "BTC") -> List[Dict]:
    """
    Busca mercados rápidos activos para un asset específico.

    Returns:
        Lista de mercados ordenados por tiempo restante
    """
    try:
        r = requests.get(
            f"{POLYMARKET_GAMMA}/markets",
            params={"active": "true", "closed": "false", "limit": 100},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        markets = data if isinstance(data, list) else data.get("markets", [])

        now = datetime.now(timezone.utc).timestamp()
        fast = []

        for m in markets:
            q = m.get("question", "")

            # Filtrar por asset y tipo de mercado
            if asset not in q.upper() or "UP OR DOWN" not in q.upper():
                continue

            # Detectar ventana temporal (5m o 15m)
            window = "5m"
            if "15 MINUTE" in q.upper() or "15-MINUTE" in q.upper():
                window = "15m"

            end_iso = m.get("endDateIso") or m.get("end_date_iso", "")
            time_remaining = None
            if end_iso:
                try:
                    end_ts = datetime.fromisoformat(
                        end_iso.replace("Z", "+00:00")
                    ).timestamp()
                    time_remaining = end_ts - now
                except:
                    pass

            if (
                time_remaining is not None
                and time_remaining < DEFAULT_CONFIG["min_time_remaining"]
            ):
                continue

            fast.append(
                {
                    "id": m.get("id"),
                    "question": q,
                    "slug": m.get("slug"),
                    "time_remaining": time_remaining,
                    "window": window,
                    "tokens": m.get("tokens", []),
                    "volume": m.get("volume", 0),
                    "liquidity": m.get("liquidity", 0),
                }
            )

        fast.sort(key=lambda x: x["time_remaining"] or 0, reverse=True)
        return fast
    except Exception as e:
        logger.error(f"Error buscando mercados para {asset}: {e}")
        return []


def get_token_price(token_id: str, side: str = "BUY") -> Optional[float]:
    """Obtiene el precio de un token en Polymarket."""
    try:
        r = requests.get(
            f"{POLYMARKET_CLOB}/price",
            params={"token_id": token_id, "side": side},
            timeout=10,
        )
        if r.status_code == 200:
            return float(r.json().get("price", 0.5))
    except Exception as e:
        logger.debug(f"Error obteniendo precio de token {token_id}: {e}")
    return None


def get_order_book(token_id: str) -> Optional[Dict]:
    """Obtiene el libro de órdenes para un token."""
    try:
        r = requests.get(
            f"{POLYMARKET_CLOB}/book", params={"token_id": token_id}, timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"Error obteniendo order book: {e}")
    return None


# ─── EJECUCIÓN DE TRADE ───────────────────────────────────────────────────────


def execute_trade(
    market: Dict, outcome: str, amount: float, live: bool = False
) -> Tuple[bool, str]:
    """
    Ejecuta un trade en Polymarket.

    Args:
        market: Dict con información del mercado
        outcome: "YES" o "NO"
        amount: Monto en USD
        live: Si es True, ejecuta el trade real

    Returns:
        (success, tx_hash_or_error)
    """
    private_key = os.environ.get("POLYMARKET_PRIVATE_KEY")

    if not private_key:
        logger.error("POLYMARKET_PRIVATE_KEY no configurada")
        return False, "Missing private key"

    if not live:
        logger.info(f"[DRY RUN] Compraría {outcome} por ${amount:.2f}")
        return True, "dry_run"

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import MarketOrderArgs
        from py_clob_client.constants import POLYGON

        client = ClobClient(host=POLYMARKET_CLOB, key=private_key, chain_id=POLYGON)

        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
        except Exception as e:
            logger.warning(f"Error derivando credenciales L2: {e}")

        # Encontrar token_id
        token_id = None
        for t in market.get("tokens", []):
            if t.get("outcome", "").upper() == outcome.upper():
                token_id = t.get("token_id")
                break

        if not token_id:
            logger.error(f"Token {outcome} no encontrado en el mercado")
            return False, "Token not found"

        # Crear y enviar orden
        signed_order = client.create_market_order(
            MarketOrderArgs(token_id=token_id, amount=amount)
        )
        resp = client.post_order(signed_order)

        tx_hash = resp.get("transaction_hash") or resp.get("order_id", "unknown")
        logger.info(f"Trade ejecutado: {tx_hash}")

        return True, tx_hash

    except Exception as e:
        logger.error(f"Error ejecutando trade: {e}")
        return False, str(e)


# ─── ANÁLISIS Y DECISIÓN ──────────────────────────────────────────────────────


def analyze_market(market: Dict, signal: Dict, config: Dict) -> Optional[Dict]:
    """
    Analiza un mercado y determina si hay oportunidad de trade.

    Returns:
        Dict con trade info si hay oportunidad, None si no
    """
    # Obtener precio YES
    yes_price = 0.50
    for t in market.get("tokens", []):
        if t.get("outcome", "").upper() == "YES":
            p = get_token_price(t.get("token_id", ""))
            if p:
                yes_price = p
            break

    mom_pct = abs(signal["momentum_pct"])

    # Filtros
    if config["volume_confidence"] and signal["volume_ratio"] < 0.5:
        return None

    if mom_pct < config["min_momentum_pct"]:
        return None

    # Calcular EV
    ev, prob, outcome, razon = calculate_ev(yes_price, signal["direction"], mom_pct)

    if ev <= 0:
        return None

    return {
        "market": market,
        "outcome": outcome,
        "ev": ev,
        "prob": prob,
        "yes_price": yes_price,
        "razon": razon,
        "signal": signal,
    }


# ─── CICLO PRINCIPAL ───────────────────────────────────────────────────────────


def run_cycle(live: bool = False) -> Dict:
    """
    Ejecuta un ciclo completo de trading.

    Returns:
        Dict con resultados del ciclo
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "live": live,
        "trades": [],
        "signals": {},
        "errors": [],
    }

    logger.info("=" * 60)
    logger.info(f"🚀 Iniciando ciclo | Modo: {'LIVE' if live else 'DRY RUN'}")

    # Verificar presupuesto
    total_spent = load_total_spent()
    max_total = DEFAULT_CONFIG["max_total_spend"]
    disponible = max_total - total_spent

    logger.info(
        f"💰 Presupuesto: ${total_spent:.2f}/${max_total:.2f} | Disponible: ${disponible:.2f}"
    )

    if total_spent >= max_total:
        logger.warning(f"🛑 LÍMITE ALCANZADO (${total_spent:.2f}/${max_total:.2f})")
        results["stopped"] = True
        return results

    trade_amount = min(DEFAULT_CONFIG["max_position"], disponible)
    if trade_amount < DEFAULT_CONFIG["min_position"]:
        logger.warning(f"⚠️ Presupuesto insuficiente (${disponible:.2f})")
        results["stopped"] = True
        return results

    # Obtener señales para todos los assets
    logger.info(f"📈 Obteniendo señales para: {', '.join(DEFAULT_CONFIG['assets'])}")
    signals = get_multi_asset_signals(DEFAULT_CONFIG["assets"])
    results["signals"] = {k: v for k, v in signals.items() if v}

    for asset, signal in signals.items():
        if not signal:
            continue

        logger.info(
            f"  {asset}: {signal['momentum_pct']:+.3f}% | {signal['direction'].upper()} | Vol: {signal['volume_ratio']:.2f}x"
        )

        # Buscar mercados para este asset
        markets = get_fast_markets(asset)

        if not markets:
            logger.info(f"  ⚠️ Sin mercados activos para {asset}")
            continue

        logger.info(f"  📊 {len(markets)} mercados encontrados")

        # Analizar cada mercado
        for market in markets[:3]:  # Top 3 mercados
            time_left = market["time_remaining"] or 0
            mins, secs = int(time_left // 60), int(time_left % 60)

            logger.info(f"  🎯 {market['question'][:60]}...")
            logger.info(f"     ⏱ {mins}m {secs}s | Ventana: {market['window']}")

            opportunity = analyze_market(market, signal, DEFAULT_CONFIG)

            if not opportunity:
                logger.info(f"     ⏸ Sin oportunidad EV+")
                continue

            # Hay oportunidad - ejecutar
            logger.info(f"     ✅ EV={opportunity['ev']:+.4f} | {opportunity['razon']}")
            logger.info(
                f"     💵 Trade: ${trade_amount:.2f} en {opportunity['outcome']}"
            )

            success, tx = execute_trade(
                market, opportunity["outcome"], trade_amount, live
            )

            if success:
                if live:
                    nuevo_total = save_total_spent(trade_amount)
                    add_trade(
                        market["id"],
                        opportunity["outcome"],
                        trade_amount,
                        opportunity["ev"],
                        tx,
                    )
                    logger.info(
                        f"     💰 Acumulado: ${nuevo_total:.2f}/${max_total:.2f}"
                    )

                results["trades"].append(
                    {
                        "asset": asset,
                        "market": market["question"],
                        "outcome": opportunity["outcome"],
                        "amount": trade_amount,
                        "ev": opportunity["ev"],
                        "tx": tx,
                    }
                )
                break  # Solo un trade por ciclo
            else:
                results["errors"].append(f"Trade fallido: {tx}")

    # Guardar estado
    state = load_state()
    state["last_run"] = results["timestamp"]
    state["status"] = "running"
    save_state(state)

    logger.info(f"✅ Ciclo completado | Trades: {len(results['trades'])}")
    logger.info("=" * 60)

    return results


# ─── MODO SERVIDOR ────────────────────────────────────────────────────────────


def run_server(live: bool = False):
    """Ejecuta el bot en modo servidor (loop continuo)."""
    interval = DEFAULT_CONFIG["run_interval"]

    logger.info("🤖 Polymarket FastLoop Trader - Modo Servidor")
    logger.info(f"   Intervalo: {interval}s | Assets: {DEFAULT_CONFIG['assets']}")
    logger.info(f"   Live trading: {live}")

    # Guardar estado inicial
    state = load_state()
    state["status"] = "running"
    state["started_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    try:
        while True:
            try:
                run_cycle(live)
            except Exception as e:
                logger.error(f"Error en ciclo: {e}")

            logger.info(f"⏳ Esperando {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("🛑 Bot detenido por usuario")
        state = load_state()
        state["status"] = "stopped"
        save_state(state)


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────


def health_check() -> Dict:
    """Retorna el estado actual del bot para health checks."""
    state = load_state()
    total_spent = load_total_spent()

    return {
        "status": state.get("status", "unknown"),
        "last_run": state.get("last_run"),
        "started_at": state.get("started_at"),
        "total_spent": total_spent,
        "max_spend": DEFAULT_CONFIG["max_total_spend"],
        "trades_count": len(state.get("trades", [])),
        "assets": DEFAULT_CONFIG["assets"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Polymarket FastLoop Trader")
    parser.add_argument("--once", action="store_true", help="Ejecutar un solo ciclo")
    parser.add_argument("--live", action="store_true", help="Activar trading real")
    parser.add_argument(
        "--status", action="store_true", help="Ver estado y presupuesto"
    )
    parser.add_argument("--reset", action="store_true", help="Resetear presupuesto")
    parser.add_argument("--health", action="store_true", help="Mostrar health check")
    args = parser.parse_args()

    live = args.live or os.environ.get("LIVE", "").lower() == "true"

    if args.reset:
        save_json(
            SPEND_FILE,
            {"total_spent": 0.0, "updated_at": datetime.now(timezone.utc).isoformat()},
        )
        print("✅ Presupuesto reseteado a $0.00")
        return

    if args.status:
        total = load_total_spent()
        max_total = DEFAULT_CONFIG["max_total_spend"]
        state = load_state()

        print(f"\n💰 PRESUPUESTO")
        print(f"   Gastado:    ${total:.2f}")
        print(f"   Límite:     ${max_total:.2f}")
        print(f"   Disponible: ${max_total - total:.2f}")
        print(f"\n📊 ESTADO")
        print(f"   Status:     {state.get('status', 'unknown')}")
        print(f"   Iniciado:   {state.get('started_at', 'N/A')}")
        print(f"   Última run: {state.get('last_run', 'N/A')}")
        print(f"   Trades:     {len(state.get('trades', []))}")
        print(f"   Assets:     {', '.join(DEFAULT_CONFIG['assets'])}")
        return

    if args.health:
        import json as json_lib

        print(json_lib.dumps(health_check(), indent=2))
        return

    if args.once:
        run_cycle(live)
    else:
        run_server(live)


if __name__ == "__main__":
    main()
