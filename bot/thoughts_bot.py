#!/usr/bin/env python3
import datetime
import json
import logging
import re
from pathlib import Path

import aiohttp
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# States
CONTENT = 1
USERNAME_CONFIRM = 2
AUTHOR_INPUT = 3
PREVIEW = 4
CSS_INPUT = 5  # New state for CSS class input

# Message pattern
URL_REGEX = (
    r"http[s]?:\/\/(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)

# Blacklisted URL patterns
BLACKLISTED_URLS = [
    r"instagram.com/reels/",
    r"youtube.com/shorts/",
    r"tiktok.com",
]

# Callback data
CONFIRM = "confirm"
CANCEL = "cancel"
EDIT = "edit"
OK = "ok"
APPROVE = "approve"  # New callback data for chat approval
APPROVE_LINK = "approve_link"  # New callback data for link approval
REJECT_LINK = "reject_link"  # New callback data for link rejection

# File paths
CREDENTIALS_FILE = Path("./credentials.json")
CONFIG_FILE = Path("./config.json")

# Loading credentials
if not CREDENTIALS_FILE.exists():
    raise FileNotFoundError(
        f"Please create {CREDENTIALS_FILE} from credentials_example.json"
    )

with open(CREDENTIALS_FILE) as f:
    credentials = json.load(f)
    TOKEN = credentials["bot_token"]
    DEVELOPER_CHAT_ID = credentials["admin_chat_id"]
    REPO = credentials["github_repo"]
    GH_TOKEN = credentials["github_token"]


def load_config():
    """Load config file or return empty dict if not exists"""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_config(config):
    """Save config to file"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def check_enabled(func):
    """Decorator to check if user is authorized"""

    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_chat.id)
        config = load_config()

        if user_id in config:
            return await func(self, update, context)
        else:
            await update.message.reply_text(
                "You are not authorized to use this bot. Please contact the administrator."
            )
            return ConversationHandler.END

    return wrapper


def format_datetime(t: datetime):
    return t.isoformat()[:19]


# "thoughts",
# {
#     "author": context.user_data["author"],
#     "css_class": css_class,
#     "content": context.user_data["content"],
# },
# "selected_press", {"url": url, "datetime": now_str, "title": url}


async def trigger_github_action(
    event_type: str,
    payload: dict,
) -> bool:
    """
    Trigger GitHub Action to save content via repository_dispatch event

    Args:
        github_token: GitHub Personal Access Token
        payload: Additional payload data for thought entries

    Returns:
        bool: True if successful, False otherwise
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GH_TOKEN}",
    }

    data = {
        "event_type": event_type,
        "client_payload": payload,
    }

    logging.info(f"Attempting to run action {event_type} for payload {payload}")

    # remember, 64kb max
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.github.com/repos/{REPO}/dispatches"
            async with session.post(url, headers=headers, json=data) as response:
                logging.info(f"github responded: {response.status}")
                return (
                    response.status == 204
                )  # GitHub returns 204 No Content on success
    except Exception as e:
        logging.error(f"Error triggering GitHub Action: {e}")
        return False


class ThoughtsBotHandler:
    def __init__(self):
        self.application = Application.builder().token(TOKEN).build()
        self.config = load_config()
        self.github_token = credentials.get("github_token")
        if not self.github_token:
            raise ValueError("GitHub token not found in credentials")
        self.setup_handlers()

    def setup_handlers(self):
        """Set up all command and conversation handlers"""
        self.application.add_handler(CommandHandler("addchat", self.add_chat))

        # Chat registration handler
        self.application.add_handler(
            CallbackQueryHandler(self.handle_chat_refusal, pattern=f"^{CANCEL}:.*$")
        )

        # Chat registration handler for CSS input state
        self.application.add_handler(
            ConversationHandler(
                entry_points=[
                    CallbackQueryHandler(
                        self.handle_chat_approval, pattern=f"^{APPROVE}:.*$"
                    )
                ],
                states={
                    CSS_INPUT: [
                        MessageHandler(
                            filters.REPLY
                            & filters.TEXT
                            & filters.Chat(chat_id=DEVELOPER_CHAT_ID)
                            & ~filters.COMMAND,
                            self.handle_css_input,
                        )
                    ],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )

        # Main thought creation handler
        self.application.add_handler(
            ConversationHandler(
                entry_points=[
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                        self.start_thought,
                    )
                ],
                states={
                    USERNAME_CONFIRM: [
                        CallbackQueryHandler(self.handle_username_confirm)
                    ],
                    AUTHOR_INPUT: [
                        MessageHandler(
                            filters.TEXT & ~filters.COMMAND, self.save_custom_author
                        )
                    ],
                    PREVIEW: [CallbackQueryHandler(self.handle_preview_choice)],
                },
                fallbacks=[CommandHandler("cancel", self.cancel)],
            )
        )

        # URL detection handler for group chats
        self.application.add_handler(
            MessageHandler(
                (
                    filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP
                )  # Only in groups
                & filters.Regex(URL_REGEX)  # Match URLs
                & ~filters.COMMAND,  # Ignore commands
                self.handle_url_detection,
            )
        )

        # Link approval handlers
        self.application.add_handler(
            CallbackQueryHandler(
                self.handle_link_approval, pattern=f"^{APPROVE_LINK}:.*$"
            )
        )
        self.application.add_handler(
            CallbackQueryHandler(
                self.handle_link_rejection, pattern=f"^{REJECT_LINK}:.*$"
            )
        )

        self.application.add_error_handler(self.error_handler)

    @check_enabled
    async def start_thought(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the thought creation process"""
        # Check chat type - only proceed in private chats
        if update.effective_chat.type != "private":
            return ConversationHandler.END

        context.user_data["content"] = update.message.text
        context.user_data["creation_time"] = (
            datetime.datetime.now()
        )  # doesn't deal with timezones

        # Get user's saved name from config
        config = load_config()
        chat_id = str(update.effective_chat.id)
        saved_name = config[chat_id]["default_author"]
        await update.message.reply_text(
            f"You are saved as: {saved_name}\nWould you like to continue with this name?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("OK", callback_data=OK),
                        InlineKeyboardButton("Edit", callback_data=EDIT),
                    ]
                ]
            ),
        )
        context.user_data["saved_name"] = saved_name
        return USERNAME_CONFIRM

    async def handle_username_confirm(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle username confirmation response"""
        query = update.callback_query
        await query.answer()

        if query.data == OK:
            context.user_data["author"] = context.user_data["saved_name"]
            return await self.show_preview(update, context)
        else:  # EDIT
            await query.edit_message_text("Please enter your new name:")
            return AUTHOR_INPUT

    async def save_custom_author(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Save custom author name and update config"""
        new_name = update.message.text
        chat_id = str(update.effective_chat.id)

        # Update config with new default author
        config = load_config()
        config[chat_id]["default_author"] = new_name
        save_config(config)

        context.user_data["author"] = new_name
        return await self.show_preview(update, context)

    async def show_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show preview of the thought"""
        content = context.user_data["content"]
        author = context.user_data["author"]
        time = context.user_data["creation_time"]

        preview = (
            "Preview of your thought:\n\n"
            f"Content: {content}\n"
            f"Author: {author}\n"
            f"Time: {format_datetime(time)}"
        )

        keyboard = [
            [
                InlineKeyboardButton("Submit", callback_data=CONFIRM),
                InlineKeyboardButton("Cancel", callback_data=CANCEL),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if isinstance(update.callback_query, CallbackQuery):
            await update.callback_query.edit_message_text(
                preview, reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(preview, reply_markup=reply_markup)

        return PREVIEW

    async def handle_preview_choice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle preview confirmation"""
        query = update.callback_query
        await query.answer()

        if query.data == CONFIRM:
            return await self.save_thought(update, context)
        else:
            await query.edit_message_text("Thought creation cancelled.")
            return ConversationHandler.END

    async def save_thought(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Save the thought by triggering GitHub Action"""
        now = context.user_data["creation_time"]
        now_str = format_datetime(now)

        # Get chat's css_class from config
        config = load_config()
        chat_id = str(update.effective_chat.id)
        css_class = config.get(chat_id, {}).get("css_class", "default")

        logging.info(f"Triggering GitHub Action to save thought")
        await update.callback_query.edit_message_text("Saving thought...")

        # Trigger GitHub Action
        success = await trigger_github_action(
            "add_thought",
            {
                "author": context.user_data["author"],
                "css_class": css_class,
                "content": context.user_data["content"],
                "datetime": now_str,
                "label": "",  # TODO
            },
        )

        if success:
            await update.callback_query.edit_message_text(
                "Thought action submitted successfully!"
            )
        else:
            error_msg = "Error saving thought via GitHub API"
            await update.callback_query.edit_message_text(error_msg)
            await self.application.bot.send_message(
                chat_id=DEVELOPER_CHAT_ID, text=error_msg
            )

        return ConversationHandler.END

    async def add_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Request to add a new chat"""
        chat_id = str(update.effective_chat.id)
        config = load_config()

        if chat_id in config:
            await update.message.reply_text("This chat is already registered!")
            return

        chat_name = update.effective_chat.title or update.effective_chat.username
        chat_type = update.effective_chat.type

        # Embed chat info in callback data for both buttons
        chat_data = f"{chat_id}:{chat_name}:{chat_type}"

        # Send message to admin
        await self.application.bot.send_message(
            chat_id=DEVELOPER_CHAT_ID,
            text=(
                f"Chat registration request:\n"
                f"ID: {chat_id}\n"
                f"Name: {chat_name}\n"
                f"Type: {chat_type}"
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Approve",
                            callback_data=f"{APPROVE}:{chat_data}",
                        ),
                        InlineKeyboardButton(
                            "Cancel",
                            callback_data=f"{CANCEL}:{chat_data}",
                        ),
                    ]
                ]
            ),
        )

        # Custom message based on chat type
        if chat_type == "private":
            user_message = (
                "Registration request sent to administrator. "
                "Once approved, you'll be able to record thoughts using this bot."
            )
        else:
            user_message = (
                "Registration request sent to administrator. "
                "Once approved, I will monitor this group for links."
            )

        await update.message.reply_text(user_message)

    async def handle_chat_refusal(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle admin's refusal of chat registration"""
        query = update.callback_query
        await query.answer()

        if str(query.from_user.id) != DEVELOPER_CHAT_ID:
            raise Exception("A non-admin received an approval request!")

        # Parse embedded data
        try:
            action, chat_id, chat_name, chat_type = query.data.split(":")
        except ValueError:
            logging.error("Invalid callback data format")
            return

        # Customize message based on chat type
        chat_desc = f"{chat_name} ({chat_type})"
        await query.edit_message_text(
            f"Chat registration request for {chat_desc} has been cancelled."
        )

        # Customize notification based on chat type
        try:
            if chat_type == "private":
                message = (
                    "Your chat registration request has been cancelled by the administrator. "
                    "You won't be able to record thoughts with this bot."
                )
            else:
                message = (
                    "This group's registration request has been cancelled by the administrator. "
                    "The bot won't monitor messages in this group."
                )

            await self.application.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            raise Exception(f"Failed to notify chat {chat_desc}: {e}")

    async def handle_chat_approval(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle admin's approval of chat registration"""
        query = update.callback_query
        await query.answer()

        if str(query.from_user.id) != DEVELOPER_CHAT_ID:
            raise Exception("A non-admin received an approval request!")

        # Parse embedded data
        try:
            action, chat_id, chat_name, chat_type = query.data.split(":")
        except ValueError:
            raise Exception("Invalid callback data format in handle_chat_approval")

        config = load_config()

        # For private chats, request CSS class
        if chat_type == "private":
            # Store chat info for CSS handler
            context.bot_data["pending_css"] = {
                "chat_id": chat_id,
                "chat_name": chat_name,
                "chat_type": chat_type,
            }

            await query.edit_message_text(
                f"Chat {chat_name} ({chat_type}) approval pending.\n"
                f"Please enter the CSS class for this user: (REPLY!)"
            )
            return CSS_INPUT

        # For group chats, approve immediately
        config[chat_id] = {"name": chat_name, "type": chat_type}
        save_config(config)

        await query.edit_message_text(
            f"Chat {chat_name} ({chat_type}) has been approved."
        )

        # Notify the chat
        try:
            message = (
                "This group has been registered! "
                "The bot will now monitor messages for links."
            )
            await self.application.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logging.error(f"Failed to notify chat {chat_name} ({chat_type}): {e}")
        return ConversationHandler.END

    async def handle_css_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle CSS class input for private chats"""
        if str(update.effective_chat.id) != DEVELOPER_CHAT_ID:
            return

        # Get pending chat info
        pending = context.bot_data.get("pending_css")
        if not pending:
            logging.warning("Received CSS input but no pending chat")
            return

        css_class = update.message.text
        chat_id = pending["chat_id"]
        chat_name = pending["chat_name"]
        chat_type = pending["chat_type"]

        # Save to config
        config = load_config()
        config[chat_id] = {
            "name": chat_name,
            "type": chat_type,
            "css_class": css_class,
            "default_author": chat_name,  # Initialize default_author with chat name
        }
        save_config(config)

        # Clean up pending state
        del context.bot_data["pending_css"]

        # Notify admin
        await update.message.reply_text(
            f"Chat {chat_name} has been approved with CSS class: {css_class}"
        )

        # Notify the user
        try:
            message = (
                "Your chat registration has been approved! "
                "You can now use this bot to record thoughts."
            )
            await self.application.bot.send_message(chat_id=chat_id, text=message)
        except Exception as e:
            logging.error(f"Failed to notify chat {chat_name}: {e}")
        return ConversationHandler.END

    async def handle_url_detection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle URL detection in group messages"""
        # Only proceed if chat is enabled
        chat_id = str(update.effective_chat.id)
        config = load_config()
        if chat_id not in config:
            return

        # Extract URLs from message
        message_text = update.message.text
        urls = re.findall(URL_REGEX, message_text)

        if not urls:
            return

        # Check each URL against blacklist
        for url in urls:
            if any(re.search(pattern, url) for pattern in BLACKLISTED_URLS):
                continue
            logging.info(f"{APPROVE_LINK}:{url}")

            # Create approval request for admin
            # Create a unique identifier for this URL request
            url_id = len(context.bot_data.get("pending_urls", []))

            # Store URL in bot data
            if "pending_urls" not in context.bot_data:
                context.bot_data["pending_urls"] = []
            context.bot_data["pending_urls"].append(url)

            keyboard = [
                [
                    InlineKeyboardButton(
                        "Approve", callback_data=f"{APPROVE_LINK}:{url_id}"
                    ),
                    InlineKeyboardButton(
                        "Reject", callback_data=f"{REJECT_LINK}:{url_id}"
                    ),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            chat_name = update.effective_chat.title
            user_name = (
                update.effective_user.username or update.effective_user.first_name
            )

            await self.application.bot.send_message(
                chat_id=DEVELOPER_CHAT_ID,
                text=(
                    f"New link shared in <{chat_name}> by @{user_name}:\n\n"
                    f"<{url}>\n\n"
                    f"Context: {message_text}"
                ),
                reply_markup=reply_markup,
            )

    async def handle_link_approval(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle admin's approval of shared link

        When a link is approved:
        1. Gets the URL from pending_urls using the ID in callback data
        2. Triggers a GitHub Action to create the selected press entry
        3. Updates the message with success/failure status
        """
        query = update.callback_query
        await query.answer()

        if str(query.from_user.id) != DEVELOPER_CHAT_ID:
            raise Exception("A non-admin received a link approval request!")

        # Extract URL ID from callback data and get URL from bot data
        url_id = int(query.data.split(":", 1)[1])

        try:
            if "pending_urls" not in context.bot_data:
                await query.edit_message_text("Error: No pending URLs found")
                return

            url = context.bot_data["pending_urls"][url_id]
            # Clean up the used URL
            context.bot_data["pending_urls"].pop(url_id)

            # Get current timestamp
            now = datetime.datetime.now()
            now_str = format_datetime(now)

            # Update status
            await query.edit_message_text(f"{url}\nSaving link...")

            # Trigger GitHub Action to save the link
            # TODO fetch the title maaaan
            if await trigger_github_action(
                "add_press", {"url": url, "datetime": now_str, "title": url}
            ):
                await query.edit_message_text(f"Link action started for {url}")
            else:
                error_msg = f"Error saving link via GitHub API: {url}"
                await query.edit_message_text(error_msg)
                # Notify admin
                await self.application.bot.send_message(
                    chat_id=DEVELOPER_CHAT_ID, text=error_msg
                )

        except Exception as e:
            logging.error(f"Error saving approved link: {e}")
            await query.edit_message_text(f"Error saving link: {e}")

    async def handle_link_rejection(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle admin's rejection of shared link"""
        query = update.callback_query
        await query.answer()

        if str(query.from_user.id) != DEVELOPER_CHAT_ID:
            raise Exception("A non-admin received a link rejection request!")

        # Extract URL ID from callback data and get URL from bot data
        url_id = int(query.data.split(":", 1)[1])

        if "pending_urls" not in context.bot_data:
            await query.edit_message_text("Error: No pending URLs found")
            return

        url = context.bot_data["pending_urls"][url_id]
        # Clean up the used URL
        context.bot_data["pending_urls"].pop(url_id)

        await query.edit_message_text(f"Link rejected: {url}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the conversation"""
        await update.message.reply_text(f"Thought creation cancelled.")
        return ConversationHandler.END

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logging.error(f"Error: {context.error}")
        # Notify admin
        await self.application.bot.send_message(
            chat_id=DEVELOPER_CHAT_ID, text=f"Error in bot: {context.error}"
        )

    def run(self):
        """Run the bot"""
        print("Starting thoughts bot...")
        self.application.run_polling()


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    bot = ThoughtsBotHandler()
    logging.warning("\n\n\nSTARTING BOT\n\n")
    bot.run()
