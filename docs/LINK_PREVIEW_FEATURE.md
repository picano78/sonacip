# Link Preview Feature for Social Posts

## Overview

The link preview feature automatically detects and displays rich previews for external links from YouTube, Instagram, and TikTok when shared in social posts.

## Supported Platforms

- **YouTube** - Video links, shorts, and youtu.be short URLs
- **Instagram** - Posts and Reels
- **TikTok** - Videos and short URLs

## How It Works

### 1. URL Detection

When a user creates a post with content containing a URL from one of the supported platforms, the system:

1. Scans the post content for URLs using regex patterns
2. Identifies if the URL matches a supported platform
3. Extracts the first matching URL from the content

### 2. Metadata Fetching

For each detected URL, the system fetches preview metadata:

- **YouTube**: Uses YouTube's oEmbed API for reliable metadata
  - Endpoint: `https://www.youtube.com/oembed?url={url}&format=json`
  - Returns: title, author, thumbnail

- **Instagram & TikTok**: Uses Open Graph metadata extraction
  - Fetches the HTML page
  - Parses Open Graph meta tags (`og:title`, `og:description`, `og:image`)
  - Falls back to standard HTML meta tags if OG tags are not available

### 3. Storage

Link preview metadata is stored in the `post` table with these fields:

- `link_url` (VARCHAR(500)) - The extracted URL
- `link_title` (VARCHAR(255)) - Title from metadata
- `link_description` (TEXT) - Description from metadata
- `link_image` (VARCHAR(500)) - Preview image URL
- `link_provider` (VARCHAR(50)) - Provider name (youtube, instagram, tiktok)

### 4. Display

Link previews are displayed in post cards with:

- Thumbnail image (if available)
- Title (clickable link to original content)
- Description (truncated to 150 characters)
- Provider badge

## Implementation Details

### Backend Components

**`app/social/link_preview.py`**
- `extract_url_from_content()` - Extracts URLs from post content
- `detect_platform()` - Identifies the platform from a URL
- `fetch_link_preview()` - Main entry point for fetching metadata
- `get_youtube_oembed()` - YouTube-specific oEmbed fetching
- `fetch_open_graph_metadata()` - Generic Open Graph parser

**`app/social/routes.py`**
- Modified `create_post()` to call link preview extraction
- Error handling ensures post creation continues even if preview fetch fails

### Frontend Components

**`app/templates/components/post_card.html`**
- Displays link preview card below post content
- Responsive layout with image on left (desktop) or top (mobile)
- Opens links in new tab with security attributes

### Database Migration

**`migrations/versions/m6n7o8p9q0r1_add_link_preview_fields.py`**
- Adds five new columns to the `post` table
- Reversible migration for easy rollback

### Dependencies

- `requests==2.32.3` - HTTP client for fetching URLs
- `beautifulsoup4==4.12.3` - HTML parsing for Open Graph tags

## Security Considerations

### 1. Request Timeout
All external requests have a 5-second timeout to prevent hanging

### 2. Error Handling
Link preview failures do not prevent post creation - errors are logged but gracefully handled

### 3. User Agent
Uses a modern Chrome user agent to avoid being blocked by social platforms

### 4. Link Security
External links open with `target="_blank"` and `rel="noopener noreferrer"` to prevent:
- Tabnapping attacks
- Window.opener exploits

### 5. No SSRF Protection Needed
The system only fetches from verified platform URLs (YouTube, Instagram, TikTok), reducing SSRF risk

## Testing

### Unit Tests

**`tests/test_link_preview.py`** includes tests for:

1. URL extraction from various platform formats
2. Platform detection accuracy
3. Multiple URL handling
4. Unsupported URL filtering
5. Metadata fetching with mocked responses
6. Error handling scenarios

Run tests with:
```bash
python -m unittest tests.test_link_preview
```

### Manual Testing

To test the feature:

1. Create a new post with a YouTube URL:
   ```
   Check out this video! https://www.youtube.com/watch?v=dQw4w9WgXcQ
   ```

2. Create a post with an Instagram URL:
   ```
   Amazing post https://www.instagram.com/p/ABC123xyz/
   ```

3. Create a post with a TikTok URL:
   ```
   Funny video https://www.tiktok.com/@user/video/1234567890
   ```

## URL Pattern Examples

### YouTube
- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/SHORT_ID`

### Instagram
- `https://www.instagram.com/p/POST_ID/`
- `https://www.instagram.com/reel/REEL_ID/`

### TikTok
- `https://www.tiktok.com/@username/video/VIDEO_ID`
- `https://vm.tiktok.com/SHORT_CODE/`

## Future Enhancements

Potential improvements for future releases:

1. **More Platforms** - Add support for Twitter, Facebook, LinkedIn
2. **Link Caching** - Cache metadata to reduce repeated API calls
3. **Custom Thumbnails** - Allow users to override auto-generated previews
4. **Analytics** - Track click-through rates on link previews
5. **Admin Controls** - Settings to enable/disable specific platforms
6. **Rate Limiting** - Implement rate limiting for metadata fetching
7. **Background Processing** - Move metadata fetching to async tasks

## Troubleshooting

### Preview Not Appearing

If a link preview doesn't appear:

1. Verify the URL matches one of the supported platform patterns
2. Check server logs for fetch errors
3. Ensure the platform's servers are accessible from your server
4. Verify the URL is publicly accessible (not private/restricted)

### Slow Post Creation

If post creation is slow:

1. Check network latency to social platform APIs
2. Consider implementing background task processing
3. Monitor timeout settings (currently 5 seconds)

### Missing Metadata

If preview appears but is incomplete:

1. Some platforms may block scraping attempts
2. Private or deleted content won't return metadata
3. Some URLs may not have Open Graph tags

## Migration Guide

To apply the database changes:

```bash
# Backup your database first
flask db upgrade

# Or using Alembic directly
alembic upgrade head
```

To rollback:

```bash
flask db downgrade
# Or
alembic downgrade -1
```
