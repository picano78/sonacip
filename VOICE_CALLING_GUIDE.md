# Voice Calling Feature - User Guide

## 📞 Overview

The SONACIP messaging system now supports voice calling functionality for both direct messages and group chats. Users can make audio-only calls with appropriate buttons in the messaging interface.

## ✨ Features

### Direct Voice Calls
- **One-on-one audio calls** between users
- **Real-time voice communication** using WebRTC
- **Call controls**: Mute/unmute microphone, toggle speaker, end call
- **Visual audio indicators** with animated bars
- **Call duration tracking**

### Group Voice Calls
- **Multi-participant audio calls** in group chats
- **Participant list** showing active members
- **Same call controls** as direct calls
- **Group membership validation**

## �� How to Use

### Starting a Direct Voice Call

1. Navigate to a direct message conversation
2. Look for the **green phone icon** (🎤) in the chat header
3. Click the icon to start the voice call
4. Allow microphone access when prompted
5. Wait for the other user to join

### Starting a Group Voice Call

1. Navigate to a group chat
2. Look for the **green phone icon** (🎤) next to the video call button
3. Click the icon to start the group voice call
4. Allow microphone access when prompted
5. Other group members can join the call

### During a Call

**Microphone Control**
- Click the microphone icon to mute/unmute
- Icon changes to show muted state
- Audio visualizer hides when muted

**Speaker Control**
- Click the speaker icon to toggle speaker on/off
- Icon changes to show muted state

**End Call**
- Click the red phone icon to end the call
- You'll be returned to the chat

## 🔧 Technical Requirements

### Browser Requirements
- Modern browser with WebRTC support (Chrome, Firefox, Safari, Edge)
- Microphone access permission
- WebSocket support
- JavaScript enabled

### Permissions
- **Microphone**: Required for voice calls
- The browser will prompt for permission on first use
- You can manage permissions in browser settings

## 🎨 UI Elements

### Button Styling
- **Voice Call Button**: Green outline circle with phone icon
- **Video Call Button**: Blue outline circle with camera icon
- Consistent styling across direct and group messaging

### Voice Call Interface
- **Caller/Group Avatar**: Displayed at the top
- **Call Status**: Shows "Connecting", "Connected", or "Call ended"
- **Call Duration**: Real-time timer (MM:SS format)
- **Audio Visualizer**: Animated bars showing audio activity
- **Call Controls**: Three circular buttons at the bottom

## 🔒 Security & Privacy

### Authentication
- All voice call routes require user authentication
- Cannot call yourself
- Group calls validate membership

### Permissions
- Microphone access is requested only when starting a call
- No recording or storage of audio
- Clean disconnect when leaving the page

## 🐛 Troubleshooting

### Common Issues

**"Permission denied" error**
- Solution: Enable microphone permission in browser settings
- Chrome: Settings → Privacy and Security → Site Settings → Microphone
- Firefox: Preferences → Privacy & Security → Permissions → Microphone

**"No microphone found" error**
- Solution: Connect a microphone device and refresh the page
- Check system settings to ensure microphone is enabled

**Call won't connect**
- Check your internet connection
- Ensure WebSocket support is enabled
- Try refreshing the page and starting again

**No audio from other participant**
- Check speaker settings
- Toggle speaker button off and on
- Ensure other participant's microphone is not muted

## 📱 Mobile Support

The voice calling interface is fully responsive and works on mobile devices:
- Touch-friendly buttons
- Optimized layout for small screens
- Supports device microphone and speaker

## 🔄 Future Enhancements

Potential improvements for future versions:
- Call recording capability
- Call history and logs
- Missed call notifications
- Call quality indicators
- Screen sharing during voice calls
- Voice messages/voicemail

## 📚 Developer Notes

### Routes
- Direct voice call: `/messages/chat/<user_id>/voice-call`
- Group voice call: `/messages/groups/<group_id>/voice-call`

### Templates
- `voice_call.html`: Voice call interface
- `conversations.html`: Direct messaging with voice call button
- `group_chat.html`: Group chat with voice call button

### WebSocket Events
- `join_call`: User joins a call
- `call_offer`: Send call offer
- `call_answer`: Receive call answer
- `leave_call`: User leaves the call
- `call_user_joined`: Notification when user joins
- `call_user_left`: Notification when user leaves

### Media Constraints
```javascript
{
    video: false,
    audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
    }
}
```

## 🆘 Support

For issues or questions:
1. Check this guide for common solutions
2. Review browser console for error messages
3. Ensure all technical requirements are met
4. Contact system administrator for persistent issues

---

**SONACIP Voice Calling** - Making communication easier!
