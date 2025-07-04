#!/usr/bin/env python3
"""
Simple tests for the Web Scraper and Summarizer

Run with: python test_scraper.py
"""

import os
import unittest
from unittest.mock import Mock, patch
from summarizer import (
    Website, 
    WebsiteScraper, 
    OpenAISummarizer, 
    WebSummarizer,
    ScrapingConfig, 
    OpenAIConfig
)

class TestWebsite(unittest.TestCase):
    """Test the Website class."""
    
    def test_website_creation(self):
        """Test creating a Website object."""
        website = Website(
            url="https://example.com",
            title="Test Title",
            text="Test content",
            metadata={"test": "data"}
        )
        
        self.assertEqual(website.url, "https://example.com")
        self.assertEqual(website.title, "Test Title")
        self.assertEqual(website.text, "Test content")
        self.assertEqual(website.metadata["test"], "data")
    
    def test_get_summary_prompt(self):
        """Test summary prompt generation."""
        website = Website(
            url="https://example.com",
            title="Test Title",
            text="Test content",
            metadata={}
        )
        
        prompt = website.get_summary_prompt()
        self.assertIn("Test Title", prompt)
        self.assertIn("Test content", prompt)

class TestScrapingConfig(unittest.TestCase):
    """Test the ScrapingConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ScrapingConfig()
        
        self.assertIsNotNone(config.user_agent)
        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay, 1.0)
        self.assertIsNotNone(config.remove_elements)
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScrapingConfig(
            timeout=60,
            max_retries=5,
            retry_delay=2.0
        )
        
        self.assertEqual(config.timeout, 60)
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.retry_delay, 2.0)

class TestOpenAIConfig(unittest.TestCase):
    """Test the OpenAIConfig class."""
    
    def test_config_creation(self):
        """Test creating OpenAI configuration."""
        config = OpenAIConfig(api_key="test_key")
        
        self.assertEqual(config.api_key, "test_key")
        self.assertEqual(config.model, "gpt-4o-mini")
        self.assertEqual(config.max_tokens, 1000)
        self.assertEqual(config.temperature, 0.7)
    
    def test_custom_openai_config(self):
        """Test custom OpenAI configuration."""
        config = OpenAIConfig(
            api_key="test_key",
            model="gpt-4",
            max_tokens=2000,
            temperature=0.5
        )
        
        self.assertEqual(config.model, "gpt-4")
        self.assertEqual(config.max_tokens, 2000)
        self.assertEqual(config.temperature, 0.5)


class TestWebsiteScraper(unittest.TestCase):
    """Test the WebsiteScraper class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = ScrapingConfig()
        self.scraper = WebsiteScraper(self.config)
    
    def test_scraper_creation(self):
        """Test creating a WebsiteScraper instance."""
        self.assertIsNotNone(self.scraper.session)
        self.assertEqual(self.scraper.config, self.config)
    
    def test_scraper_with_custom_config(self):
        """Test creating a scraper with custom configuration."""
        custom_config = ScrapingConfig(
            timeout=60,
            max_retries=5,
            retry_delay=2.0
        )
        scraper = WebsiteScraper(custom_config)
        self.assertEqual(scraper.config, custom_config)

class TestWebSummarizer(unittest.TestCase):
    """Test the WebSummarizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.openai_config = OpenAIConfig(api_key="test_key")
        self.summarizer = WebSummarizer(self.openai_config)
    
    def test_invalid_url(self):
        """Test handling of invalid URLs."""
        result = self.summarizer.summarize_url("not-a-valid-url")
        self.assertIsNone(result)
    
    def test_missing_scheme_url(self):
        """Test handling of URLs without scheme."""
        result = self.summarizer.summarize_url("example.com")
        self.assertIsNone(result)
    
    def test_valid_url_format(self):
        """Test that valid URL format is accepted."""
        # This should not raise an exception
        try:
            # We're not actually making the request, just testing URL validation
            with patch.object(self.summarizer.scraper, 'scrape', return_value=None):
                result = self.summarizer.summarize_url("https://example.com")
                self.assertIsNone(result)  # Because scrape returns None in our mock
        except Exception as e:
            self.fail(f"Valid URL should not raise exception: {e}")
    
    def test_scraping_failure_handling(self):
        """Test handling when scraping fails."""
        with patch.object(self.summarizer.scraper, 'scrape', return_value=None):
            result = self.summarizer.summarize_url("https://example.com")
            self.assertIsNone(result)
    
    def test_summarization_failure_handling(self):
        """Test handling when summarization fails."""
        # Create a mock website
        mock_website = Website(
            url="https://example.com",
            title="Test Site",
            text="Test content",
            metadata={}
        )
        
        with patch.object(self.summarizer.scraper, 'scrape', return_value=mock_website):
            with patch.object(self.summarizer.summarizer, 'summarize', return_value=None):
                result = self.summarizer.summarize_url("https://example.com")
                self.assertIsNone(result)

class TestIntegration(unittest.TestCase):
    """Integration tests with mocked dependencies."""
    
    @patch('requests.Session')
    def test_full_workflow_mock(self, mock_session):
        """Test the full workflow with mocked dependencies."""
        # Mock the session response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'<html><head><title>Test Site</title></head><body><p>Test content</p></body></html>'
        mock_response.headers = {'content-type': 'text/html'}
        
        mock_session_instance = Mock()
        mock_session_instance.get.return_value = mock_response
        mock_session.return_value = mock_session_instance
        
        # Mock OpenAI response
        mock_openai_response = Mock()
        mock_openai_response.choices = [Mock()]
        mock_openai_response.choices[0].message.content = "This is a test summary."
        
        # Mock the OpenAI client that gets created inside OpenAISummarizer
        with patch('summarizer.OpenAI') as mock_openai:
            mock_openai_instance = Mock()
            mock_openai_instance.chat.completions.create.return_value = mock_openai_response
            mock_openai.return_value = mock_openai_instance
            
            # Test the full workflow
            openai_config = OpenAIConfig(api_key="test_key")
            summarizer = WebSummarizer(openai_config)
            
            result = summarizer.summarize_url("https://example.com")
            
            # Verify the result
            self.assertEqual(result, "This is a test summary.")

def run_tests():
    """Run all tests."""
    print("Running Web Scraper and Summarizer Tests")
    print("=" * 50)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestWebsite,
        TestScrapingConfig,
        TestOpenAIConfig,
        TestWebsiteScraper,
        TestWebSummarizer,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✓ All tests passed!")
    else:
        print("✗ Some tests failed!")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    run_tests() 