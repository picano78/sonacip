# Live Streaming Feature

## Overview

The live streaming feature allows users to broadcast live video to their followers without storing any video data on the server. This implementation follows the key requirements:

1. **No Server Storage**: Video streams are NOT saved on the server
2. **Client-Side Recording**: Users can optionally save streams to their own devices
3. **Full-Screen Support**: Mobile-optimized with full-screen viewing capability

## Architecture

### Database Models

- **LiveStream**: Stores only metadata about active streams (title, duration, viewer count)
- **LiveStreamViewer**: Tracks viewer analytics (join/leave times)

**Important**: NO video data is stored in the database. Only stream metadata and analytics.

### Key Features

#### For Broadcasters
- Start/stop live streams with title and description
- Real-time viewer count
- Camera controls (toggle, switch front/back)
- Microphone controls
- Full-screen broadcasting
- Stream duration tracking

#### For Viewers
- Browse active live streams
- Watch streams in real-time
- Full-screen viewing (mobile-optimized)
- Optional client-side recording (saves to device)
- Viewer count and stream duration display
- Audio mute/unmute controls

## Technical Implementation

### WebRTC P2P Streaming

The implementation uses WebRTC (Web Real-Time Communication) for peer-to-peer video streaming:

- **getUserMedia API**: Captures camera and microphone
- **Peer-to-peer**: Direct browser-to-browser communication (in production with STUN/TURN servers)
- **No Server Video Storage**: Video streams directly between browsers
- **Signaling**: Minimal server involvement only for connection setup

### Client-Side Recording

Viewers can optionally save streams to their devices using:

- **MediaRecorder API**: Records the video stream locally
- **Browser Download**: Automatically downloads the recorded file
- **Format**: WebM format with VP8/Opus codecs
- **Storage**: Saved to user's device (Downloads folder)

### Full-Screen Support

- **Fullscreen API**: Native browser full-screen mode
- **Mobile-Optimized**: Touch-friendly controls
- **Orientation Lock**: Landscape mode on mobile (when supported)

## Usage

### Starting a Live Stream

1. Navigate to Live Streaming section
2. Click "Inizia una Diretta"
3. Enter title and optional description
4. Grant camera/microphone permissions
5. Stream goes live immediately

### Watching a Live Stream

1. Browse active streams on the main page
2. Click on a stream to watch
3. Grant audio playback permissions if needed
4. Use controls to:
   - Toggle full-screen
   - Mute/unmute audio
   - Record to your device (optional)

### Ending a Stream

Broadcasters can end their stream at any time by clicking the stop button. This will:
- Close all viewer connections
- Mark the stream as inactive
- Record final statistics (duration, peak viewers)
- Clean up resources

## Security & Privacy

- ✅ No server-side video storage
- ✅ Metadata-only database records
- ✅ Permission-based camera/microphone access
- ✅ User-controlled recording (opt-in)
- ✅ Stream visibility controls (future: private/public streams)

## Performance

- **Minimal Server Load**: No video processing or storage
- **Scalable**: Peer-to-peer architecture scales naturally
- **Low Latency**: Direct browser connections (with proper STUN/TURN setup)
- **Bandwidth**: Managed by WebRTC (adaptive bitrate)

## Future Enhancements

1. **WebSocket Signaling**: Replace polling with WebSocket for better real-time performance
2. **TURN Server**: Add TURN server for NAT traversal (firewall/router compatibility)
3. **Stream Quality Options**: Allow broadcasters to set quality (720p, 480p, etc.)
4. **Chat Feature**: Real-time chat during live streams
5. **Notifications**: Push notifications when followed users go live
6. **Stream Scheduling**: Schedule future live streams
7. **Multi-streaming**: Broadcast to multiple platforms simultaneously
8. **Analytics Dashboard**: Detailed analytics for streamers

## Browser Compatibility

- ✅ Chrome/Edge (recommended)
- ✅ Firefox
- ✅ Safari (iOS 11+)
- ✅ Mobile browsers (Android/iOS)

**Note**: Full WebRTC support required. Internet Explorer not supported.

## Configuration

The livestream feature is controlled by the `livestream` feature flag in the platform settings. Administrators can enable/disable this feature system-wide.

## Development Notes

- Templates: `app/templates/livestream/`
- Routes: `app/livestream/routes.py`
- Models: `app/models.py` (LiveStream, LiveStreamViewer)
- Blueprint: Registered in `app/__init__.py`

## Production Deployment

For production use, consider:

1. **STUN/TURN Servers**: Configure ICE servers for reliable connections
2. **HTTPS Required**: WebRTC requires HTTPS in production
3. **Feature Flag**: Enable via admin panel
4. **Rate Limiting**: Already implemented for stream creation
5. **Resource Limits**: Monitor database for stream metadata cleanup

## Support

For issues or questions:
- Check browser console for errors
- Verify camera/microphone permissions
- Ensure HTTPS is enabled (required for getUserMedia)
- Check browser compatibility
