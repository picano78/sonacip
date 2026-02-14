"""
Test link preview functionality for YouTube, Instagram, and TikTok
"""
import unittest
from app.social.link_preview import (
    extract_url_from_content,
    detect_platform,
    fetch_link_preview,
    SUPPORTED_PLATFORMS
)


class TestLinkPreview(unittest.TestCase):
    
    def test_extract_youtube_url(self):
        """Test extracting YouTube URLs from content"""
        content = "Check out this video https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('youtube.com', url)
    
    def test_extract_youtube_short_url(self):
        """Test extracting YouTube short URLs"""
        content = "Amazing! https://youtu.be/dQw4w9WgXcQ"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('youtu.be', url)
    
    def test_extract_youtube_shorts(self):
        """Test extracting YouTube Shorts URLs"""
        content = "Check this short https://www.youtube.com/shorts/abc123"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('youtube.com/shorts', url)
    
    def test_extract_instagram_url(self):
        """Test extracting Instagram URLs"""
        content = "Love this post https://www.instagram.com/p/ABC123xyz/"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('instagram.com', url)
    
    def test_extract_instagram_reel(self):
        """Test extracting Instagram Reel URLs"""
        content = "Great reel https://www.instagram.com/reel/XYZ123abc/"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('instagram.com', url)
    
    def test_extract_tiktok_url(self):
        """Test extracting TikTok URLs"""
        content = "Funny video https://www.tiktok.com/@username/video/1234567890"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('tiktok.com', url)
    
    def test_extract_tiktok_short_url(self):
        """Test extracting TikTok short URLs"""
        content = "Watch https://vm.tiktok.com/ZMabcdefg/"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('tiktok.com', url)
    
    def test_no_url_extraction(self):
        """Test that non-supported URLs are not extracted"""
        content = "Check out my website https://example.com"
        url = extract_url_from_content(content)
        self.assertIsNone(url)
    
    def test_multiple_urls_first_supported(self):
        """Test that first supported URL is extracted when multiple URLs present"""
        content = "https://example.com and https://www.youtube.com/watch?v=test123"
        url = extract_url_from_content(content)
        self.assertIsNotNone(url)
        self.assertIn('youtube.com', url)
    
    def test_detect_youtube_platform(self):
        """Test detecting YouTube platform"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        platform = detect_platform(url)
        self.assertEqual(platform, 'youtube')
    
    def test_detect_instagram_platform(self):
        """Test detecting Instagram platform"""
        url = "https://www.instagram.com/p/ABC123xyz/"
        platform = detect_platform(url)
        self.assertEqual(platform, 'instagram')
    
    def test_detect_tiktok_platform(self):
        """Test detecting TikTok platform"""
        url = "https://www.tiktok.com/@username/video/1234567890"
        platform = detect_platform(url)
        self.assertEqual(platform, 'tiktok')
    
    def test_detect_unsupported_platform(self):
        """Test that unsupported platforms return None"""
        url = "https://example.com"
        platform = detect_platform(url)
        self.assertIsNone(platform)
    
    def test_url_patterns_comprehensive(self):
        """Test that all URL patterns are comprehensive"""
        test_urls = {
            'youtube': [
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'https://youtu.be/dQw4w9WgXcQ',
                'https://www.youtube.com/shorts/abc123',
                'http://youtube.com/watch?v=test',
            ],
            'instagram': [
                'https://www.instagram.com/p/ABC123/',
                'https://instagram.com/reel/XYZ456/',
                'http://www.instagram.com/p/test123/',
            ],
            'tiktok': [
                'https://www.tiktok.com/@user/video/1234567890',
                'https://vm.tiktok.com/ZMabcdefg/',
                'http://tiktok.com/@username/video/9876543210',
            ]
        }
        
        for expected_platform, urls in test_urls.items():
            for url in urls:
                platform = detect_platform(url)
                self.assertEqual(
                    platform, 
                    expected_platform,
                    f"URL {url} should be detected as {expected_platform}, got {platform}"
                )


if __name__ == '__main__':
    unittest.main()
