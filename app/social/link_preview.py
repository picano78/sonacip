"""
Link Preview Utilities
Extract and fetch metadata for external links (YouTube, Instagram, TikTok)
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict
from urllib.parse import urlparse


# Supported platforms with their URL patterns
SUPPORTED_PLATFORMS = {
    'youtube': [
        r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)',
        r'(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)'
    ],
    'instagram': [
        r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)',
    ],
    'tiktok': [
        r'(?:https?://)?(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)',
        r'(?:https?://)?(?:vm\.)?tiktok\.com/([a-zA-Z0-9]+)',
    ]
}


def extract_url_from_content(content: str) -> Optional[str]:
    """
    Extract the first URL from post content that matches supported platforms.
    
    Args:
        content: The post content text
        
    Returns:
        The first matching URL or None
    """
    # Generic URL pattern
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, content)
    
    for url in urls:
        # Check if URL matches any supported platform
        for platform, patterns in SUPPORTED_PLATFORMS.items():
            for pattern in patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return url
    
    return None


def detect_platform(url: str) -> Optional[str]:
    """
    Detect which platform a URL belongs to.
    
    Args:
        url: The URL to check
        
    Returns:
        Platform name (youtube, instagram, tiktok) or None
    """
    for platform, patterns in SUPPORTED_PLATFORMS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    
    return None


def fetch_open_graph_metadata(url: str, timeout: int = 5) -> Dict[str, Optional[str]]:
    """
    Fetch Open Graph metadata from a URL.
    
    Args:
        url: The URL to fetch metadata from
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with title, description, image, and provider
    """
    metadata = {
        'title': None,
        'description': None,
        'image': None,
        'provider': None
    }
    
    try:
        # Set a user agent to avoid blocking
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Fetch the page
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract Open Graph metadata
        og_title = soup.find('meta', property='og:title')
        if og_title:
            metadata['title'] = og_title.get('content', '')
        
        og_description = soup.find('meta', property='og:description')
        if og_description:
            metadata['description'] = og_description.get('content', '')
        
        og_image = soup.find('meta', property='og:image')
        if og_image:
            metadata['image'] = og_image.get('content', '')
        
        og_site_name = soup.find('meta', property='og:site_name')
        if og_site_name:
            metadata['provider'] = og_site_name.get('content', '')
        
        # Fallback to standard meta tags if OG tags not found
        if not metadata['title']:
            title_tag = soup.find('title')
            if title_tag:
                metadata['title'] = title_tag.string
        
        if not metadata['description']:
            desc_tag = soup.find('meta', attrs={'name': 'description'})
            if desc_tag:
                metadata['description'] = desc_tag.get('content', '')
        
        # Detect provider from URL if not found in metadata
        if not metadata['provider']:
            metadata['provider'] = detect_platform(url)
        
    except Exception as e:
        # Log error but don't crash - we'll return empty metadata
        print(f"Error fetching metadata for {url}: {str(e)}")
    
    return metadata


def get_youtube_oembed(url: str) -> Dict[str, Optional[str]]:
    """
    Get YouTube video metadata using oEmbed API.
    
    Args:
        url: YouTube video URL
        
    Returns:
        Dictionary with title, description (author_name), image (thumbnail_url), and provider
    """
    metadata = {
        'title': None,
        'description': None,
        'image': None,
        'provider': 'YouTube'
    }
    
    try:
        oembed_url = f'https://www.youtube.com/oembed?url={url}&format=json'
        response = requests.get(oembed_url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        metadata['title'] = data.get('title')
        metadata['description'] = f"By {data.get('author_name', 'Unknown')}"
        metadata['image'] = data.get('thumbnail_url')
        
    except Exception as e:
        print(f"Error fetching YouTube oEmbed for {url}: {str(e)}")
    
    return metadata


def fetch_link_preview(url: str) -> Dict[str, Optional[str]]:
    """
    Fetch link preview metadata for a URL.
    Uses platform-specific APIs when available, falls back to Open Graph.
    
    Args:
        url: The URL to fetch preview for
        
    Returns:
        Dictionary with title, description, image, and provider
    """
    platform = detect_platform(url)
    
    # Use YouTube oEmbed API for better results
    if platform == 'youtube':
        metadata = get_youtube_oembed(url)
        # If oEmbed fails, fall back to Open Graph
        if not metadata['title']:
            metadata = fetch_open_graph_metadata(url)
    else:
        # For Instagram and TikTok, use Open Graph
        metadata = fetch_open_graph_metadata(url)
    
    return metadata
