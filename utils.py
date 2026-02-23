"""
Utilidades para Polymarket FastLoop Trader
==========================================
Funciones auxiliares para análisis, reportes y gestión.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List

DATA_DIR = "/app/data"


def load_trades() -> List[Dict]:
    """Carga el historial de trades."""
    state_file = os.path.join(DATA_DIR, "state.json")
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                data = json.load(f)
                return data.get("trades", [])
    except:
        pass
    return []


def generate_report(days: int = 7) -> Dict:
    """
    Genera un reporte de rendimiento.
    
    Args:
        days: Días hacia atrás para analizar
    
    Returns:
        Dict con estadísticas del período
    """
    trades = load_trades()
    
    if not trades:
        return {"error": "No hay trades registrados"}
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent_trades = [
        t for t in trades 
        if datetime.fromisoformat(t["timestamp"]) > cutoff
    ]
    
    total_trades = len(recent_trades)
    total_volume = sum(t["amount"] for t in recent_trades)
    avg_ev = sum(t["ev"] for t in recent_trades) / total_trades if total_trades > 0 else 0
    
    # Agrupar por asset
    by_asset = {}
    for t in recent_trades:
        asset = t.get("asset", "UNKNOWN")
        if asset not in by_asset:
            by_asset[asset] = {"trades": 0, "volume": 0}
        by_asset[asset]["trades"] += 1
        by_asset[asset]["volume"] += t["amount"]
    
    return {
        "period_days": days,
        "total_trades": total_trades,
        "total_volume": total_volume,
        "avg_ev": avg_ev,
        "by_asset": by_asset,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


def export_trades_csv(filepath: str = None) -> str:
    """
    Exporta trades a formato CSV.
    
    Returns:
        Ruta del archivo CSV generado
    """
    trades = load_trades()
    
    if not filepath:
        filepath = os.path.join(DATA_DIR, f"trades_{datetime.now().strftime('%Y%m%d')}.csv")
    
    with open(filepath, 'w') as f:
        f.write("timestamp,asset,market,outcome,amount,ev,tx_hash\n")
        for t in trades:
            f.write(f"{t['timestamp']},{t.get('asset','')},{t.get('market','')},"
                   f"{t['outcome']},{t['amount']},{t['ev']},{t.get('tx_hash','')}\n")
    
    return filepath


def get_daily_stats() -> Dict:
    """Obtiene estadísticas del día actual."""
    trades = load_trades()
    
    today = datetime.now(timezone.utc).date()
    today_trades = [
        t for t in trades
        if datetime.fromisoformat(t["timestamp"]).date() == today
    ]
    
    return {
        "date": today.isoformat(),
        "trades_count": len(today_trades),
        "total_volume": sum(t["amount"] for t in today_trades),
        "avg_ev": sum(t["ev"] for t in today_trades) / len(today_trades) if today_trades else 0
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Utilidades del bot")
    parser.add_argument("--report", type=int, metavar="DAYS", help="Generar reporte de N días")
    parser.add_argument("--export-csv", action="store_true", help="Exportar trades a CSV")
    parser.add_argument("--daily", action="store_true", help="Estadísticas del día")
    args = parser.parse_args()
    
    if args.report:
        report = generate_report(args.report)
        print(json.dumps(report, indent=2))
    
    elif args.export_csv:
        path = export_trades_csv()
        print(f"Exportado a: {path}")
    
    elif args.daily:
        stats = get_daily_stats()
        print(json.dumps(stats, indent=2))
    
    else:
        parser.print_help()
