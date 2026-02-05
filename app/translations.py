"""
Translation system for Italian/English support
"""

TRANSLATIONS = {
    'it': {
        'nav_home': 'Home',
        'nav_feed': 'Feed',
        'nav_messages': 'Messaggi',
        'nav_events': 'Eventi',
        'nav_planner': 'Planner',
        'nav_profile': 'Profilo',
        'nav_settings': 'Impostazioni',
        'nav_logout': 'Esci',
        'nav_login': 'Accedi',
        'nav_register': 'Registrati',
        'nav_notifications': 'Notifiche',
        'nav_search': 'Cerca',
        
        'common_save': 'Salva',
        'common_cancel': 'Annulla',
        'common_delete': 'Elimina',
        'common_edit': 'Modifica',
        'common_create': 'Crea',
        'common_back': 'Indietro',
        'common_next': 'Avanti',
        'common_send': 'Invia',
        'common_search': 'Cerca',
        'common_loading': 'Caricamento...',
        'common_no_results': 'Nessun risultato',
        'common_success': 'Operazione completata',
        'common_error': 'Si è verificato un errore',
        
        'auth_login': 'Accedi',
        'auth_register': 'Registrati',
        'auth_logout': 'Esci',
        'auth_email': 'Email',
        'auth_password': 'Password',
        'auth_confirm_password': 'Conferma Password',
        'auth_username': 'Username',
        'auth_first_name': 'Nome',
        'auth_last_name': 'Cognome',
        'auth_phone': 'Telefono',
        'auth_remember_me': 'Ricordami',
        'auth_forgot_password': 'Password dimenticata?',
        'auth_no_account': 'Non hai un account?',
        'auth_have_account': 'Hai già un account?',
        
        'profile_edit': 'Modifica Profilo',
        'profile_bio': 'Biografia',
        'profile_followers': 'Follower',
        'profile_following': 'Seguiti',
        'profile_posts': 'Post',
        'profile_language': 'Lingua',
        
        'messages_inbox': 'Posta in arrivo',
        'messages_new': 'Nuovo messaggio',
        'messages_write': 'Scrivi un messaggio...',
        'messages_search': 'Cerca conversazione...',
        'messages_no_conversations': 'Nessuna conversazione',
        'messages_select_chat': 'Seleziona una chat',
        'messages_start_conversation': 'Inizia una conversazione',
        
        'events_upcoming': 'Prossimi eventi',
        'events_past': 'Eventi passati',
        'events_create': 'Crea evento',
        'events_date': 'Data',
        'events_time': 'Ora',
        'events_location': 'Luogo',
        'events_description': 'Descrizione',
        
        'feed_new_post': 'Nuovo post',
        'feed_write_something': 'Scrivi qualcosa...',
        'feed_like': 'Mi piace',
        'feed_comment': 'Commenta',
        'feed_share': 'Condividi',
        
        'privacy_cookie_title': 'Privacy e Cookie',
        'privacy_cookie_message': 'Questo sito utilizza cookie per migliorare la tua esperienza.',
        'privacy_accept': 'Accetta',
        'privacy_reject': 'Rifiuta',
        'privacy_settings': 'Impostazioni',
        
        'footer_about': 'Chi siamo',
        'footer_contact': 'Contatti',
        'footer_privacy': 'Privacy',
        'footer_terms': 'Termini',
    },
    'en': {
        'nav_home': 'Home',
        'nav_feed': 'Feed',
        'nav_messages': 'Messages',
        'nav_events': 'Events',
        'nav_planner': 'Planner',
        'nav_profile': 'Profile',
        'nav_settings': 'Settings',
        'nav_logout': 'Logout',
        'nav_login': 'Login',
        'nav_register': 'Register',
        'nav_notifications': 'Notifications',
        'nav_search': 'Search',
        
        'common_save': 'Save',
        'common_cancel': 'Cancel',
        'common_delete': 'Delete',
        'common_edit': 'Edit',
        'common_create': 'Create',
        'common_back': 'Back',
        'common_next': 'Next',
        'common_send': 'Send',
        'common_search': 'Search',
        'common_loading': 'Loading...',
        'common_no_results': 'No results',
        'common_success': 'Operation completed',
        'common_error': 'An error occurred',
        
        'auth_login': 'Login',
        'auth_register': 'Register',
        'auth_logout': 'Logout',
        'auth_email': 'Email',
        'auth_password': 'Password',
        'auth_confirm_password': 'Confirm Password',
        'auth_username': 'Username',
        'auth_first_name': 'First Name',
        'auth_last_name': 'Last Name',
        'auth_phone': 'Phone',
        'auth_remember_me': 'Remember me',
        'auth_forgot_password': 'Forgot password?',
        'auth_no_account': "Don't have an account?",
        'auth_have_account': 'Already have an account?',
        
        'profile_edit': 'Edit Profile',
        'profile_bio': 'Bio',
        'profile_followers': 'Followers',
        'profile_following': 'Following',
        'profile_posts': 'Posts',
        'profile_language': 'Language',
        
        'messages_inbox': 'Inbox',
        'messages_new': 'New message',
        'messages_write': 'Write a message...',
        'messages_search': 'Search conversation...',
        'messages_no_conversations': 'No conversations',
        'messages_select_chat': 'Select a chat',
        'messages_start_conversation': 'Start a conversation',
        
        'events_upcoming': 'Upcoming events',
        'events_past': 'Past events',
        'events_create': 'Create event',
        'events_date': 'Date',
        'events_time': 'Time',
        'events_location': 'Location',
        'events_description': 'Description',
        
        'feed_new_post': 'New post',
        'feed_write_something': 'Write something...',
        'feed_like': 'Like',
        'feed_comment': 'Comment',
        'feed_share': 'Share',
        
        'privacy_cookie_title': 'Privacy & Cookies',
        'privacy_cookie_message': 'This site uses cookies to improve your experience.',
        'privacy_accept': 'Accept',
        'privacy_reject': 'Reject',
        'privacy_settings': 'Settings',
        
        'footer_about': 'About',
        'footer_contact': 'Contact',
        'footer_privacy': 'Privacy',
        'footer_terms': 'Terms',
    }
}


def get_translation(key, lang='it'):
    """Get a translation for a key in the specified language."""
    translations = TRANSLATIONS.get(lang, TRANSLATIONS['it'])
    return translations.get(key, key)


def t(key, lang='it'):
    """Shorthand for get_translation."""
    return get_translation(key, lang)
