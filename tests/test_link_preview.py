"""
Test link preview functionality for YouTube, Instagram, and TikTok
"""
import unittest
from unittest.mock import patch, Mock
from app.social.link_preview import (
    extract_url_from_content,
    detect_platform,
    fetch_link_preview,
    get_youtube_oembed,
    fetch_open_graph_metadata,
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
    
    @patch('app.social.link_preview.requests.get')
    def test_get_youtube_oembed_success(self, mock_get):
        """Test successful YouTube oEmbed fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            'title': 'Test Video',
            'author_name': 'Test Author',
            'thumbnail_url': 'https://example.com/thumb.jpg'
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = get_youtube_oembed('https://www.youtube.com/watch?v=test')
        
        self.assertEqual(result['title'], 'Test Video')
        self.assertEqual(result['description'], 'By Test Author')
        self.assertEqual(result['image'], 'https://example.com/thumb.jpg')
        self.assertEqual(result['provider'], 'YouTube')
    
    @patch('app.social.link_preview.requests.get')
    def test_get_youtube_oembed_error(self, mock_get):
        """Test YouTube oEmbed fetch with error handling"""
        mock_get.side_effect = Exception('Network error')
        
        result = get_youtube_oembed('https://www.youtube.com/watch?v=test')
        
        # Should return metadata with None values on error
        self.assertIsNone(result['title'])
        self.assertIsNone(result['description'])
        self.assertIsNone(result['image'])
        self.assertEqual(result['provider'], 'YouTube')
    
    @patch('app.social.link_preview.fetch_open_graph_metadata')
    @patch('app.social.link_preview.get_youtube_oembed')
    def test_fetch_link_preview_youtube(self, mock_oembed, mock_og):
        """Test fetch_link_preview for YouTube URLs"""
        mock_oembed.return_value = {
            'title': 'Video Title',
            'description': 'By Author',
            'image': 'thumb.jpg',
            'provider': 'YouTube'
        }
        
        result = fetch_link_preview('https://www.youtube.com/watch?v=test')
        
        # Should use oEmbed for YouTube
        mock_oembed.assert_called_once()
        self.assertEqual(result['title'], 'Video Title')
        self.assertEqual(result['provider'], 'YouTube')
    
    @patch('app.social.link_preview.fetch_open_graph_metadata')
    def test_fetch_link_preview_instagram(self, mock_og):
        """Test fetch_link_preview for Instagram URLs"""
        mock_og.return_value = {
            'title': 'Instagram Post',
            'description': 'Test description',
            'image': 'image.jpg',
            'provider': 'instagram'
        }
        
        result = fetch_link_preview('https://www.instagram.com/p/test/')
        
        # Should use Open Graph for Instagram
        mock_og.assert_called_once()
        self.assertEqual(result['title'], 'Instagram Post')
    
    @patch('app.social.link_preview.fetch_open_graph_metadata')
    def test_fetch_link_preview_tiktok(self, mock_og):
        """Test fetch_link_preview for TikTok URLs"""
        mock_og.return_value = {
            'title': 'TikTok Video',
            'description': 'Test description',
            'image': 'image.jpg',
            'provider': 'tiktok'
        }
        
        result = fetch_link_preview('https://www.tiktok.com/@user/video/123')
        
        # Should use Open Graph for TikTok
        mock_og.assert_called_once()
        self.assertEqual(result['title'], 'TikTok Video')


if __name__ == '__main__':
    unittest.main()
