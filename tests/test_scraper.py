import unittest
from src.nlu.models import ScrapeRequest
from src.nlu.local_nlu_fallback import LocalNLUParser
from src.core.polite_throttler import PoliteThrottler
from src.core.parser import TweetParser
from bs4 import BeautifulSoup


class TestTwitterScraper(unittest.TestCase):
    """Test suite for NLU parser, query builder, and DOM parsing logic."""

    def test_nlu_hashtag_and_dates_extraction(self):
        prompt = "Scrape 100 live tweets for #Python from 2025-05-01 to 2025-05-15"
        req = LocalNLUParser.parse_prompt(prompt)
        self.assertEqual(req.query, "#Python")
        self.assertEqual(req.since, "2025-05-01")
        self.assertEqual(req.until, "2025-05-15")
        self.assertEqual(req.limit, 100)
        self.assertTrue(req.f_live)

    def test_nlu_top_and_min_likes_extraction(self):
        prompt = "Scrape top 25 tweets for #PSL with min 100 likes and min 20 retweets"
        req = LocalNLUParser.parse_prompt(prompt)
        self.assertEqual(req.query, "#PSL")
        self.assertEqual(req.limit, 25)
        self.assertFalse(req.f_live)  # Targeted 'Top' tab
        self.assertEqual(req.min_likes, 100)
        self.assertEqual(req.min_retweets, 20)

        query_str = req.build_search_query()
        self.assertIn("min_faves:100", query_str)
        self.assertIn("min_retweets:20", query_str)

    def test_nlu_dotted_hashtag_and_combined_phrasing(self):
        prompt = "top 10 latest tweets for #web3.0 with min 70 likes"
        req = LocalNLUParser.parse_prompt(prompt)
        self.assertEqual(req.query, "#web3")
        self.assertEqual(req.limit, 10)
        self.assertEqual(req.min_likes, 70)
        self.assertFalse(req.f_live)  # Targeted 'Top' tab because min_likes was requested
        query_str = req.build_search_query()
        self.assertIn("#web3", query_str)
        self.assertIn("min_faves:70", query_str)

    def test_nlu_relative_date_extraction(self):
        prompt = "Collect 30 tweets about #AI in the last 7 days"
        req = LocalNLUParser.parse_prompt(prompt)
        self.assertEqual(req.query, "#AI")
        self.assertEqual(req.limit, 30)
        self.assertIsNotNone(req.since)
        self.assertIsNotNone(req.until)

    def test_search_url_generation(self):
        req = ScrapeRequest(
            query="#Bitcoin",
            since="2025-06-01",
            until="2025-06-15",
            limit=50,
            language="en",
            f_live=True
        )
        url = req.build_search_url()
        self.assertIn("x.com/search", url)
        self.assertIn("f=live", url)
        self.assertIn("%23Bitcoin", url)
        self.assertIn("since%3A2025-06-01", url)
        self.assertIn("until%3A2025-06-15", url)

    def test_metric_number_parser(self):
        self.assertEqual(TweetParser._parse_metric_number("1.2K"), 1200)
        self.assertEqual(TweetParser._parse_metric_number("3.5M"), 3500000)
        self.assertEqual(TweetParser._parse_metric_number("450"), 450)
        self.assertEqual(TweetParser._parse_metric_number("0"), 0)
        self.assertEqual(TweetParser._parse_metric_number(""), 0)

    def test_dom_tweet_parsing(self):
        sample_html = """
        <article data-testid="tweet">
            <a href="/elonmusk/status/1880000000000000000"></a>
            <div data-testid="User-Name">
                <span>Elon Musk</span>
                <span>@elonmusk</span>
            </div>
            <div data-testid="tweetText">
                <span>Exciting updates coming to AI and aerospace!</span>
            </div>
            <time datetime="2025-05-10T14:30:00.000Z"></time>
            <div data-testid="reply">1.5K</div>
            <div data-testid="retweet">5.2K</div>
            <div data-testid="like">45K</div>
        </article>
        """
        soup = BeautifulSoup(sample_html, "lxml")
        tweet_id, permalink = TweetParser._extract_tweet_id_and_url(soup)
        username, display_name = TweetParser._extract_user_info(soup)
        text = TweetParser._extract_tweet_text(soup)
        timestamp = TweetParser._extract_timestamp(soup)
        metrics = TweetParser._extract_metrics(soup)

        self.assertEqual(tweet_id, "1880000000000000000")
        self.assertEqual(permalink, "https://x.com/elonmusk/status/1880000000000000000")
        self.assertEqual(username, "@elonmusk")
        self.assertEqual(display_name, "Elon Musk")
        self.assertIn("Exciting updates", text)
        self.assertEqual(timestamp, "2025-05-10T14:30:00.000Z")
        self.assertEqual(metrics["replies"], 1500)
        self.assertEqual(metrics["retweets"], 5200)
        self.assertEqual(metrics["likes"], 45000)


if __name__ == "__main__":
    unittest.main()
