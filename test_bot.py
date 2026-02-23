"""
Tests para Polymarket FastLoop Trader
=====================================
Ejecutar: python test_bot.py
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Asegurar que podemos importar main
sys.path.insert(0, os.path.dirname(__file__))

from main import (
    calculate_ev,
    load_total_spent,
    save_total_spent,
    health_check,
    DEFAULT_CONFIG
)


class TestEVCalculation(unittest.TestCase):
    """Tests para el cálculo de Expected Value."""
    
    def test_ev_positive_scenario(self):
        """EV positivo cuando hay momentum fuerte y precio favorable."""
        yes_price = 0.48
        direction = "up"
        momentum_pct = 1.0  # 1% de momentum
        
        ev, prob, outcome, razon = calculate_ev(yes_price, direction, momentum_pct)
        
        self.assertGreater(ev, 0, "EV debería ser positivo con buenas condiciones")
        self.assertEqual(outcome, "YES")
        self.assertGreater(prob, 0.5)
    
    def test_ev_negative_scenario(self):
        """EV negativo cuando el precio es muy alto."""
        yes_price = 0.96
        direction = "up"
        momentum_pct = 0.5
        
        ev, prob, outcome, razon = calculate_ev(yes_price, direction, momentum_pct)
        
        self.assertLess(ev, 0, "EV debería ser negativo con precio > 0.95")
    
    def test_ev_down_direction(self):
        """EV con dirección DOWN."""
        yes_price = 0.52
        direction = "down"
        momentum_pct = 1.0
        
        ev, prob, outcome, razon = calculate_ev(yes_price, direction, momentum_pct)
        
        self.assertEqual(outcome, "NO")
        self.assertLess(prob, 0.5)


class TestBudgetManagement(unittest.TestCase):
    """Tests para gestión de presupuesto."""
    
    def setUp(self):
        """Setup para tests."""
        self.test_file = "/tmp/test_spent.json"
        # Patch el archivo de gastos
        self.spend_patcher = patch('main.SPEND_FILE', self.test_file)
        self.spend_patcher.start()
    
    def tearDown(self):
        """Cleanup después de tests."""
        self.spend_patcher.stop()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
    
    def test_load_empty_spent(self):
        """Cargar gasto cuando no hay archivo."""
        spent = load_total_spent()
        self.assertEqual(spent, 0.0)
    
    def test_save_and_load_spent(self):
        """Guardar y cargar gasto."""
        save_total_spent(5.0)
        spent = load_total_spent()
        self.assertEqual(spent, 5.0)
        
        save_total_spent(3.0)
        spent = load_total_spent()
        self.assertEqual(spent, 8.0)


class TestHealthCheck(unittest.TestCase):
    """Tests para health check."""
    
    def test_health_check_structure(self):
        """Verificar estructura del health check."""
        health = health_check()
        
        required_keys = ["status", "total_spent", "max_spend", "trades_count", "assets"]
        for key in required_keys:
            self.assertIn(key, health, f"Falta clave: {key}")
        
        self.assertIsInstance(health["total_spent"], float)
        self.assertIsInstance(health["max_spend"], float)
        self.assertIsInstance(health["trades_count"], int)


class TestConfig(unittest.TestCase):
    """Tests para configuración."""
    
    def test_default_config(self):
        """Verificar configuración por defecto."""
        self.assertIn("BTC", DEFAULT_CONFIG["assets"])
        self.assertEqual(DEFAULT_CONFIG["polymarket_fee"], 0.10)
        self.assertGreater(DEFAULT_CONFIG["min_momentum_pct"], 0)
        self.assertGreater(DEFAULT_CONFIG["entry_threshold"], 0)


class TestBinanceSignal(unittest.TestCase):
    """Tests para señales de Binance."""
    
    @patch('main.requests.get')
    def test_get_btc_momentum_success(self, mock_get):
        """Obtener momentum exitosamente."""
        # Mock respuesta de Binance
        mock_response = MagicMock()
        mock_response.json.return_value = [
            [0, 0, 0, 0, "50000.0", "10.0"],  # hace 5 min
            [0, 0, 0, 0, "50100.0", "12.0"],
            [0, 0, 0, 0, "50200.0", "11.0"],
            [0, 0, 0, 0, "50300.0", "13.0"],
            [0, 0, 0, 0, "50400.0", "15.0"],  # ahora
            [0, 0, 0, 0, "50500.0", "14.0"],
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from main import get_crypto_momentum
        result = get_crypto_momentum("BTCUSDT", 5)
        
        self.assertIsNotNone(result)
        self.assertIn("momentum_pct", result)
        self.assertIn("direction", result)
        self.assertEqual(result["direction"], "up")
    
    @patch('main.requests.get')
    def test_get_btc_momentum_failure(self, mock_get):
        """Manejar error de API."""
        mock_get.side_effect = Exception("API Error")
        
        from main import get_crypto_momentum
        result = get_crypto_momentum("BTCUSDT", 5)
        
        self.assertIsNone(result)


def run_tests():
    """Ejecutar todos los tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Agregar tests
    suite.addTests(loader.loadTestsFromTestCase(TestEVCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestBudgetManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestHealthCheck))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestBinanceSignal))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
