#!/usr/bin/env python3
"""
Web Scraper and Summarizer

A production-ready tool for scraping websites and generating AI-powered summaries.
"""

import os
import logging
import requests
import argparse
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from openai import OpenAI
from openai import APIError as OpenAIAPIError
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(override=True)


@dataclass
class ScrapingConfig:
    """Configuration for web scraping."""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    remove_elements: list = None

    def __post_init__(self):
        if self.remove_elements is None:
            self.remove_elements = ["script", "style", "img", "input", "nav", "header", "footer", "aside"]


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI API."""
    api_key: str
    model: str = "gpt-4o-mini"
    max_tokens: int = 1000
    temperature: float = 0.7


class WebsiteScraper:
    """Handles web scraping with error handling and retries."""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
    
    def scrape(self, url: str) -> Optional['Website']:
        """
        Scrape a website with retry logic and error handling.
        
        Args:
            url: The URL to scrape
            
        Returns:
            Website object or None if scraping failed
        """
        for attempt in range(self.config.max_retries):
            try:
                logger.info(f"Scraping {url} (attempt {attempt + 1}/{self.config.max_retries})")
                
                response = self.session.get(
                    url, 
                    timeout=self.config.timeout,
                    allow_redirects=True
                )
                response.raise_for_status()
                
                return Website.from_response(url, response, self.config)
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"Failed to scrape {url} after {self.config.max_retries} attempts")
                    return None
            except Exception as e:
                logger.error(f"Unexpected error scraping {url}: {e}")
                return None


class Website:
    """Represents a scraped website with cleaned content."""
    
    def __init__(self, url: str, title: str, text: str, metadata: Dict[str, Any]):
        self.url = url
        self.title = title
        self.text = text
        self.metadata = metadata
    
    @classmethod
    def from_response(cls, url: str, response: requests.Response, config: ScrapingConfig) -> 'Website':
        """Create a Website object from a requests response."""
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract title
        title = soup.title.string if soup.title else "No title found"
        title = title.strip() if title else "No title found"
        
        # Clean the content
        if soup.body:
            # Remove unwanted elements
            for element in soup.body.find_all(config.remove_elements):
                element.decompose()
            
            # Extract text
            text = soup.body.get_text(separator="\n", strip=True)
            
            # Clean up whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
        else:
            text = "No content found"
        
        # Extract metadata
        metadata = {
            'status_code': response.status_code,
            'content_type': response.headers.get('content-type', ''),
            'content_length': len(response.content),
            'scraped_at': time.time()
        }
        
        return cls(url, title, text, metadata)
    
    def get_summary_prompt(self) -> str:
        """Generate a prompt for summarization."""
        return f"""You are looking at a website titled "{self.title}"

The contents of this website is as follows; please provide a short summary of this website in markdown. 
If it includes news or announcements, then summarize these too.

{self.text}"""


class OpenAISummarizer:
    """Handles AI-powered summarization using OpenAI."""
    
    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.client = OpenAI(api_key=config.api_key)
    
    def summarize(self, website: Website, system_prompt: str = None) -> Optional[str]:
        """
        Generate a summary of the website content.
        
        Args:
            website: The Website object to summarize
            system_prompt: Optional custom system prompt
            
        Returns:
            Summary text or None if summarization failed
        """
        if system_prompt is None:
            system_prompt = """You are an assistant that analyzes the contents of a website 
and provides a short summary, ignoring text that might be navigation related. 
Respond in markdown."""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": website.get_summary_prompt()}
            ]
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except OpenAIAPIError as e:
            logger.error(f"OpenAI API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during summarization: {e}")
            return None


class WebSummarizer:
    """Main class that orchestrates scraping and summarization."""
    
    def __init__(self, openai_config: OpenAIConfig, scraping_config: ScrapingConfig = None):
        self.openai_config = openai_config
        self.scraping_config = scraping_config or ScrapingConfig()
        
        self.scraper = WebsiteScraper(self.scraping_config)
        self.summarizer = OpenAISummarizer(self.openai_config)
    
    def summarize_url(self, url: str, system_prompt: str = None) -> Optional[str]:
        """
        Scrape a URL and generate a summary.
        
        Args:
            url: The URL to scrape and summarize
            system_prompt: Optional custom system prompt for summarization
            
        Returns:
            Summary text or None if the process failed
        """
        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.error(f"Invalid URL: {url}")
                return None
        except Exception as e:
            logger.error(f"URL parsing error: {e}")
            return None
        
        # Scrape the website
        website = self.scraper.scrape(url)
        if not website:
            return None
        
        logger.info(f"Successfully scraped {url} (title: {website.title})")
        
        # Generate summary
        summary = self.summarizer.summarize(website, system_prompt)
        if summary:
            logger.info(f"Successfully generated summary for {url}")
        
        return summary


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Web Scraper and Summarizer - Generate AI-powered summaries of websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python summarizer.py -u "https://example.com"
  python summarizer.py --url "https://news.ycombinator.com" --model "gpt-4o-mini"
  python summarizer.py -u "https://blog.example.com" --max-tokens 1500 --temperature 0.3
  python summarizer.py -u "https://docs.example.com" --timeout 60 --retries 5
        """
    )
    
    # Required arguments
    parser.add_argument(
        '-u', '--url',
        required=True,
        help='URL to scrape and summarize'
    )
    
    # OpenAI configuration
    parser.add_argument(
        '--model',
        default='gpt-4o-mini',
        help='OpenAI model to use (default: gpt-4o-mini)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=1000,
        help='Maximum tokens for the summary (default: 1000)'
    )
    
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.7,
        help='Temperature for AI response (0.0-1.0, default: 0.7)'
    )
    
    # Scraping configuration
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Maximum retry attempts (default: 3)'
    )
    
    parser.add_argument(
        '--retry-delay',
        type=float,
        default=1.0,
        help='Base delay between retries in seconds (default: 1.0)'
    )
    
    # Output options
    parser.add_argument(
        '--output',
        '-o',
        help='Output file to save summary (default: print to console)'
    )
    
    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Suppress logging output'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def setup_logging(quiet: bool, verbose: bool):
    """Setup logging configuration."""
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)


def main():
    """Main function for command-line usage."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.quiet, args.verbose)
    
    # Get API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        logger.error("OPENAI_API_KEY environment variable not found!")
        logger.error("Please set your OpenAI API key in the .env file or as an environment variable.")
        sys.exit(1)
    
    # Create configurations
    openai_config = OpenAIConfig(
        api_key=api_key,
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature
    )
    
    scraping_config = ScrapingConfig(
        timeout=args.timeout,
        max_retries=args.retries,
        retry_delay=args.retry_delay
    )
    
    # Initialize the summarizer
    summarizer = WebSummarizer(openai_config, scraping_config)
    
    # Process the URL
    logger.info(f"Starting to scrape and summarize: {args.url}")
    print(f"🌐 Scraping and summarizing: {args.url}")
    print("=" * 60)
    
    summary = summarizer.summarize_url(args.url)
    
    if summary:
        print("📝 SUMMARY:")
        print("-" * 40)
        print(summary)
        print("-" * 40)
        
        # Save to file if requested
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(f"# Summary of {args.url}\n\n")
                    f.write(summary)
                print(f"💾 Summary saved to: {args.output}")
            except Exception as e:
                logger.error(f"Failed to save summary to {args.output}: {e}")
                print(f"❌ Failed to save summary to {args.output}")
        
        print("✅ Summary generated successfully!")
    else:
        print("❌ Failed to generate summary")
        sys.exit(1)


if __name__ == "__main__":
    main()








