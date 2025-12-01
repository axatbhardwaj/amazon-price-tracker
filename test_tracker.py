import pytest
from unittest.mock import patch, MagicMock
import json
import os
import logging
import requests

from tracker import (
    check_price_drop,
    update_price_history,
    load_items,
    load_history,
    save_history,
    send_notification,
    process_item,
)
from scrapers import (
    parse_price_text,
    get_price,
    fetch_amazon_price,
    fetch_myntra_price,
    fetch_flipkart_price,
)
import subprocess
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

    def test_price_dropped(self, caplog):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        with caplog.at_level(logging.INFO):
            check_price_drop("Test Item", 800.0, history, 500.0)

        assert "PRICE DROP" in caplog.text
        assert "1000.0" in caplog.text
        assert "800.0" in caplog.text

    def test_price_increased(self, caplog):
        history = {
            "Test Item": [{"price": 800.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        caplog.clear()
        check_price_drop("Test Item", 1000.0, history, 500.0)

        assert "PRICE DROP" not in caplog.text

    def test_price_unchanged(self, caplog):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        caplog.clear()
        check_price_drop("Test Item", 1000.0, history, 500.0)

        assert "PRICE DROP" not in caplog.text

    def test_threshold_reached(self, caplog):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        with caplog.at_level(logging.INFO):
            check_price_drop("Test Item", 450.0, history, 500.0)

        assert "TARGET REACHED" in caplog.text

    def test_threshold_not_reached(self, caplog):
        history = {
            "Test Item": [{"price": 1000.0, "timestamp": "2024-01-01T10:00:00"}]
        }
        caplog.clear()
        check_price_drop("Test Item", 600.0, history, 500.0)

        assert "TARGET REACHED" not in caplog.text

    def test_no_history(self, caplog):
        history = {}
        caplog.clear()
        check_price_drop("Test Item", 800.0, history, 500.0)

        assert caplog.text == ""

    def test_empty_item_history(self, caplog):
        history = {"Test Item": []}
        caplog.clear()
        check_price_drop("Test Item", 800.0, history, 500.0)

        assert caplog.text == ""


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

    def test_file_not_found(self, caplog):
        with patch('tracker.ITEMS_FILE', 'nonexistent.json'):
            result = load_items()

        assert result == []
        assert "not found" in caplog.text

        assert result == []
        assert "not found" in caplog.text


class TestDeleteItem:
    def test_delete_valid_item(self, tmp_path):
        items_file = tmp_path / "items.json"
        items_data = [{"name": "Item 1"}, {"name": "Item 2"}]
        items_file.write_text(json.dumps(items_data))

        with patch('tracker.ITEMS_FILE', str(items_file)):
            from tracker import delete_item
            removed = delete_item(0)
            
        assert removed == {"name": "Item 1"}
        
        saved_items = json.loads(items_file.read_text())
        assert len(saved_items) == 1
        assert saved_items[0]["name"] == "Item 2"

    def test_delete_invalid_index(self, tmp_path):
        items_file = tmp_path / "items.json"
        items_data = [{"name": "Item 1"}]
        items_file.write_text(json.dumps(items_data))

        with patch('tracker.ITEMS_FILE', str(items_file)):
            from tracker import delete_item
            removed = delete_item(5)
            
        assert removed is None
        
        saved_items = json.loads(items_file.read_text())
        assert len(saved_items) == 1
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


class TestFetchAmazonPrice:
    def test_successful_fetch(self):
        mock_html = '<div class="a-price-whole">1,299</div>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_amazon_price("http://example.com")

        assert price == 1299.0

    def test_failed_fetch_status(self, caplog):
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch('tracker.requests.get', return_value=mock_response):
            # Patch sleep to avoid waiting
            with patch("time.sleep"):
                price = fetch_amazon_price("http://example.com", max_retries=1)

        assert price is None
        assert "503" in caplog.text

    def test_network_error(self, caplog):
        with patch(
            "tracker.requests.get",
            side_effect=requests.RequestException("Network error"),
        ):
            with patch("time.sleep"):
                price = fetch_amazon_price("http://example.com", max_retries=1)

        assert price is None
        assert "Network error" in caplog.text


class TestFetchMyntraPrice:
    def test_successful_myntra_fetch(self):
        mock_html = '''
        <html>
        <script>
        window.__myx = {"pdpData": {"price": {"discounted": 1895, "mrp": 2495}, "name": "Test Product"}};
        </script>
        </html>
        '''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_myntra_price("http://myntra.com/test")

        assert price == 1895.0

    def test_myntra_mrp_fallback(self):
        """Test that MRP is used when discounted price is 0."""
        mock_html = '''
        <script>
        window.__myx = {"pdpData": {"price": {"discounted": 0, "mrp": 2495}}};
        </script>
        '''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_myntra_price("http://myntra.com/test")

        assert price == 2495.0

    def test_myntra_no_price_found(self, caplog):
        mock_html = '<html><body>No price data</body></html>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            with patch("time.sleep"):
                price = fetch_myntra_price("http://myntra.com/test", max_retries=1)

        assert price is None
        assert "Price not found in Myntra page" in caplog.text
        
        
class TestFetchFlipkartPrice:
    def test_successful_flipkart_json_ld(self):
        mock_html = '''
        <html>
        <script type="application/ld+json">
        [
            {
                "@type": "Product",
                "offers": {
                    "price": "12999"
                }
            }
        ]
        </script>
        </html>
        '''
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_flipkart_price("http://flipkart.com/test")

        assert price == 12999.0

    def test_successful_flipkart_selector(self):
        mock_html = '<div class="Nx9bqj CxhGGd">₹12,999</div>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            price = fetch_flipkart_price("http://flipkart.com/test")

        assert price == 12999.0

    def test_flipkart_no_price_found(self, caplog):
        mock_html = '<html><body>No price data</body></html>'
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_html.encode()

        with patch('tracker.requests.get', return_value=mock_response):
            with patch("time.sleep"):
                price = fetch_flipkart_price("http://flipkart.com/test", max_retries=1)

        assert price is None
        assert "Price not found in Flipkart page" in caplog.text


class TestProcessItem:
    @patch('tracker.fetch_amazon_price', return_value=1000.0)
    @patch('tracker.fetch_myntra_price')
    @patch('tracker.fetch_flipkart_price')
    def test_process_amazon_item(self, mock_flipkart, mock_myntra, mock_amazon):
        item = {
            "name": "Test Amazon Item",
            "url": "http://amazon.in/test",
            "threshold": 500,
            "Source": "amazon"
        }
        history = {}
        
        process_item(item, history)
        
        mock_amazon.assert_called_once()
        mock_myntra.assert_not_called()
        mock_flipkart.assert_not_called()

    @patch('tracker.fetch_amazon_price')
    @patch('tracker.fetch_myntra_price', return_value=1895.0)
    @patch('tracker.fetch_flipkart_price')
    def test_process_myntra_item(self, mock_flipkart, mock_myntra, mock_amazon):
        item = {
            "name": "Test Myntra Item",
            "url": "http://myntra.com/test",
            "threshold": 2000,
            "Source": "myntra"
        }
        history = {}
        
        process_item(item, history)
        
        mock_myntra.assert_called_once()
        mock_amazon.assert_not_called()
        mock_flipkart.assert_not_called()

    @patch('tracker.fetch_amazon_price')
    @patch('tracker.fetch_myntra_price')
    @patch('tracker.fetch_flipkart_price', return_value=12999.0)
    def test_process_flipkart_item(self, mock_flipkart, mock_myntra, mock_amazon):
        item = {
            "name": "Test Flipkart Item",
            "url": "http://flipkart.com/test",
            "threshold": 10000,
            "Source": "flipkart"
        }
        history = {}
        
        process_item(item, history)
        
        mock_flipkart.assert_called_once()
        mock_amazon.assert_not_called()
        mock_myntra.assert_not_called()

    @patch('tracker.fetch_amazon_price', return_value=1000.0)
    @patch('tracker.fetch_myntra_price')
    @patch('tracker.fetch_flipkart_price')
    def test_process_default_source(self, mock_flipkart, mock_myntra, mock_amazon):
        """Test that missing Source defaults to Amazon."""
        item = {
            "name": "Test Item",
            "url": "http://amazon.in/test",
            "threshold": 500
        }
        history = {}
        
        process_item(item, history)
        
        mock_amazon.assert_called_once()
        mock_myntra.assert_not_called()
        mock_flipkart.assert_not_called()


class TestSendNotification:
    @patch("tracker.platform.system", return_value="Windows")
    @patch("tracker.subprocess.Popen")
    def test_notification_windows(self, mock_popen, mock_system):
        send_notification("Title", "Message")
        
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        
        # Check command structure
        cmd = args[0]
        assert cmd[0] == "powershell"
        assert 'MessageBox' in cmd[2]
        assert "Title" in cmd[2]
        assert "Message" in cmd[2]
        
        # Check non-blocking flags
        assert kwargs.get("stdout") == subprocess.DEVNULL
        assert kwargs.get("stderr") == subprocess.DEVNULL

    @patch("tracker.platform.system", return_value="Linux")
    @patch("tracker.subprocess.run")
    def test_notification_linux(self, mock_run, mock_system):
        send_notification("Title", "Message")
        
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        cmd = args[0]
        
        assert cmd[0] == "notify-send"
        assert cmd[1] == "Title"
        assert cmd[2] == "Message"
