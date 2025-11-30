import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
import json
import os

from tracker import (
    parse_price_text,
    get_price,
    check_price_drop,
    update_price_history,
    load_items,
    load_history,
    save_history,
    fetch_price,
)
from bs4 import BeautifulSoup


class TestParsePriceText:
    def test_simple_price(self):
        assert parse_price_text("100.00") == 100.00

    def test_price_with_currency_symbol(self):
        assert parse_price_text("₹15,999") == 15999.0

    def test_price_with_dollar(self):
        assert parse_price_text("$49.99") == 49.99

    def test_empty_string(self):
        assert parse_price_text("") is None

    def test_no_digits(self):
        assert parse_price_text("Price unavailable") is None


class TestGetPrice:
    def test_price_whole_selector(self):
        html = '<div class="a-price-whole">15,999</div>'
        soup = BeautifulSoup(html, 'lxml')
        assert get_price(soup) == 15999.0

    def test_offscreen_selector(self):
        html = '<span class="a-price"><span class="a-offscreen">₹12,499</span></span>'
        soup = BeautifulSoup(html, 'lxml')
        assert get_price(soup) == 12499.0

    def test_no_price_found(self):
        html = '<div>No price here</div>'
        soup = BeautifulSoup(html, 'lxml')
        assert get_price(soup) is None


class TestCheckPriceDrop:
    def test_price_dropped(self, capsys):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        check_price_drop("Test Item", 800.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert "PRICE DROP ALERT" in captured.out
        assert "1000.0" in captured.out
        assert "800.0" in captured.out

    def test_price_increased(self, capsys):
        history = {
            "Test Item": [{"price": 800.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        check_price_drop("Test Item", 1000.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert "PRICE DROP ALERT" not in captured.out

    def test_price_unchanged(self, capsys):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        check_price_drop("Test Item", 1000.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert "PRICE DROP ALERT" not in captured.out

    def test_threshold_reached(self, capsys):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        check_price_drop("Test Item", 450.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert "TARGET REACHED" in captured.out

    def test_threshold_not_reached(self, capsys):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        check_price_drop("Test Item", 600.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert "TARGET REACHED" not in captured.out

    def test_no_history(self, capsys):
        history = {}
        check_price_drop("Test Item", 800.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_empty_item_history(self, capsys):
        history = {"Test Item": []}
        check_price_drop("Test Item", 800.0, history, 500.0)
        
        captured = capsys.readouterr()
        assert captured.out == ""


class TestUpdatePriceHistory:
    def test_new_item(self):
        history = {}
        update_price_history("New Item", 999.0, history)
        
        assert "New Item" in history
        assert len(history["New Item"]) == 1
        assert history["New Item"][0]["price"] == 999.0
        assert "timestamp" in history["New Item"][0]

    def test_existing_item(self):
        history = {
            "Existing Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        update_price_history("Existing Item", 900.0, history)
        
        assert len(history["Existing Item"]) == 2
        assert history["Existing Item"][1]["price"] == 900.0


class TestLoadItems:
    def test_load_valid_items(self, tmp_path):
        items_file = tmp_path / "items.json"
        items_data = [{"name": "Test", "url": "http://test.com", "threshold": 100}]
        items_file.write_text(json.dumps(items_data))
        
        with patch('tracker.ITEMS_FILE', str(items_file)):
            result = load_items()
        
        assert result == items_data

    def test_file_not_found(self, capsys):
        with patch('tracker.ITEMS_FILE', 'nonexistent.json'):
            result = load_items()
        
        assert result == []
        captured = capsys.readouterr()
        assert "not found" in captured.out


class TestLoadHistory:
    def test_load_existing_history(self, tmp_path):
        history_file = tmp_path / "history.json"
        history_data = {"Item": [{"price": 100, "timestamp": "2024-01-01"}]}
        history_file.write_text(json.dumps(history_data))
        
        with patch('tracker.HISTORY_FILE', str(history_file)):
            result = load_history()
        
        assert result == history_data

    def test_no_history_file(self, tmp_path):
        with patch('tracker.HISTORY_FILE', str(tmp_path / "nonexistent.json")):
            result = load_history()
        
        assert result == {}


class TestSaveHistory:
    def test_save_history(self, tmp_path):
        history_file = tmp_path / "history.json"
        history_data = {"Item": [{"price": 100, "timestamp": "2024-01-01"}]}
        
        with patch('tracker.HISTORY_FILE', str(history_file)):
            save_history(history_data)
        
        saved = json.loads(history_file.read_text())
        assert saved == history_data


class TestFetchPrice:
    def test_successful_fetch(self):
        mock_html = '<div class="a-price-whole">1,299</div>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()
        
        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_price("http://example.com")
        
        assert price == 1299.0

    def test_failed_fetch_status(self, capsys):
        mock_response = MagicMock()
        mock_response.status_code = 503
        
        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_price("http://example.com")
        
        assert price is None
        captured = capsys.readouterr()
        assert "503" in captured.out

    def test_network_error(self, capsys):
        with patch('tracker.requests.get', side_effect=Exception("Network error")):
            price = fetch_price("http://example.com")
        
        assert price is None
        captured = capsys.readouterr()
        assert "Error" in captured.out

