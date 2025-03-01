# Thoughts Bot

Simple Telegram bot to create blog content through chat messages.

## States Flow

```
[User sends message]
      ↓
   CONTENT
      ↓
AUTHOR_CONFIRM → [Use default] → PREVIEW
      ↓                            ↓
[Custom name] → AUTHOR_INPUT → PREVIEW → [Confirm] → Save & Push
```

## Admin Commands

- `/addchat <chat_id> <default_author>`: Enables a chat with default author
- `/removechat <chat_id>`: Disables a chat

## File Structure

- `credentials.json`: Bot token and admin chat ID
- `config.json`: Enabled chats with their default authors
- Output: Creates JSON files in `src/thoughts/YYYY-MM/` and auto-pushes to git

## Notes

- Error notifications sent to admin chat
- Files are automatically committed with message "Add thought from Telegram bot"
- Bot runs with `python thoughts_bot.py`