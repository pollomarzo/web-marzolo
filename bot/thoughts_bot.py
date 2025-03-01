#!/usr/bin/env python3
import asyncio
import datetime
import json
import logging
import os
import subprocess
from pathlib import Path

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

# Callback data
CONFIRM = "confirm"
CANCEL = "cancel"
EDIT = "edit"
OK = "ok"

GIT_USER = "thoughts_bot"
GIT_EMAIL = "thoughts_bot@marzolo.com"  # github action checks for this!
BRANCH_NAME = "main"

# File paths
CURRENT_DIR = Path(__file__).parent.resolve()
CREDENTIALS_FILE = CURRENT_DIR / "credentials.json"
CONFIG_FILE = CURRENT_DIR / "config.json"
THOUGHTS_DIR = CURRENT_DIR.parent / "src" / "thoughts"
SSH_KEY_PATH = CURRENT_DIR.parent / "secrets/bot_ssh_key"
ALLOWED_FOLDER = CURRENT_DIR.parent / "src/thoughts"

# Loading credentials
if not CREDENTIALS_FILE.exists():
    raise FileNotFoundError(
        f"Please create {CREDENTIALS_FILE} from credentials_example.json"
    )

with open(CREDENTIALS_FILE) as f:
    credentials = json.load(f)
    TOKEN = credentials["bot_token"]
    DEVELOPER_CHAT_ID = credentials["admin_chat_id"]


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


def git_operations(now_str: str):
    """Handle git add, commit and push"""
    try:
        author = f"{GIT_USER} <{GIT_EMAIL}>"

        # Git add
        # subprocess.run(["git", "add", filepath], check=True)
        subprocess.run(["git", "add", ALLOWED_FOLDER], check=True)

        # Git commit
        commit_message = f"Add thought {now_str} from Telegram bot"
        subprocess.run(
            ["git", "commit", "--author", author, "-m", commit_message], check=True
        )

        # Git push with strict SSH key usage
        ssh_cmd = (
            f'ssh -i "{SSH_KEY_PATH}" '  # Use the specified key
            "-o IdentitiesOnly=yes "  # Ignore keys from SSH agent
            "-o AddKeysToAgent=no"  # Prevent adding keys to agent
        )

        # Prepare environment
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = ssh_cmd

        # Block SSH agent access by removing its socket variable
        if "SSH_AUTH_SOCK" in env:
            del env["SSH_AUTH_SOCK"]

        # Push with the custom environment
        subprocess.run(
            ["git", "push", "-u", "origin", BRANCH_NAME], check=True, env=env
        )
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Git operation failed: {e}")
        return False


def format_datetime(t: datetime):
    return t.isoformat()[:19]


class ThoughtsBotHandler:
    def __init__(self):
        self.application = Application.builder().token(TOKEN).build()
        self.config = load_config()
        self.setup_handlers()

    def setup_handlers(self):
        """Set up all command and conversation handlers"""
        self.application.add_handler(CommandHandler("addchat", self.add_chat))
        self.application.add_handler(CommandHandler("removechat", self.remove_chat))

        # Chat approval handlers
        self.application.add_handler(
            CallbackQueryHandler(self.handle_chat_refusal, pattern=f"^{CANCEL}:.*$")
        )
        # Handle admin text responses for CSS class
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.Chat(chat_id=DEVELOPER_CHAT_ID) & filters.REPLY,
                self.handle_chat_approval,
            )
        )

        # Main conversation handler
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.start_thought)
            ],
            states={
                USERNAME_CONFIRM: [CallbackQueryHandler(self.handle_username_confirm)],
                AUTHOR_INPUT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.save_custom_author
                    )
                ],
                PREVIEW: [CallbackQueryHandler(self.handle_preview_choice)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

        self.application.add_handler(conv_handler)
        self.application.add_error_handler(self.error_handler)

    @check_enabled
    async def start_thought(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the thought creation process"""
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
        """Save the thought to file and push to git"""
        now = context.user_data["creation_time"]
        year_month = now.strftime("%Y-%m")
        now_str = format_datetime(now)

        # Create directory if it doesn't exist
        thought_dir = THOUGHTS_DIR / year_month
        thought_dir.mkdir(parents=True, exist_ok=True)

        # Create thought file
        filename = f"{now_str}.json"
        filepath = thought_dir / filename

        # Get chat's css_class from config
        config = load_config()
        chat_id = str(update.effective_chat.id)
        css_class = config.get(chat_id, {}).get("css_class", "default")

        thought_data = {
            "author": context.user_data["author"],
            "label": context.user_data["author"],  # Keep original author as label
            "css_class": css_class,
            "datetime": now_str + "Z",
            "content": context.user_data["content"],
        }
        logging.info(f"saving thought in {filepath}")

        with open(filepath, "w") as f:
            json.dump(thought_data, f, indent=4)

        # Git operations
        if git_operations(now_str):
            await update.callback_query.edit_message_text(
                "Thought saved and pushed to repository successfully!"
            )
        else:
            await update.callback_query.edit_message_text(
                "Thought saved but there was an error pushing to the repository. "
                "Please check the logs and push manually."
            )
            # Notify admin
            await self.application.bot.send_message(
                chat_id=DEVELOPER_CHAT_ID,
                text=f"Error pushing thought to repository: {filepath}",
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

        # Send approval request to admin with only Cancel button
        keyboard = [
            [
                InlineKeyboardButton("Cancel", callback_data=f"{CANCEL}:{chat_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send message to admin - they can reply with CSS class to approve
        await self.application.bot.send_message(
            chat_id=DEVELOPER_CHAT_ID,
            text=(
                f"Chat registration request:\n"
                f"ID: {chat_id}\n"
                f"Name: {chat_name}\n\n"
                "Reply with CSS class to approve, or click Cancel to deny"
            ),
            reply_markup=reply_markup,
        )

        await update.message.reply_text(
            "Registration request sent to administrator. Please wait for approval."
        )

    async def handle_chat_refusal(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        await query.answer()
        if str(query.from_user.id) != DEVELOPER_CHAT_ID:
            raise Exception("A non-admin received an approval request!")
        action, chat_id = query.data.split(":")
        await query.edit_message_text(
            f"Chat {chat_id} registration request has been cancelled."
        )
        # Notify the user
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text="Your chat registration request has been cancelled by the administrator.",
            )
        except Exception as e:
            raise Exception(f"Failed to notify chat {chat_id}: {e}")

    async def handle_chat_approval(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle admin's response to chat registration requests"""
        if not (
            "Chat registration request"
            in update.effective_message.reply_to_message.text
        ):
            logging.warning(
                f"Received a reply to a non-approval message. Discarding as accidental"
            )
            return

        css_class = update.message.text
        chat_id = update.effective_message.reply_to_message.from_user.id
        chat_name = update.effective_message.reply_to_message.from_user.username

        config = load_config()
        config[chat_id] = {
            "name": chat_name,
            "css_class": css_class,
        }
        save_config(config)

        await update.message.reply_text(
            f"Chat {chat_id} has been approved with CSS class '{css_class}'."
        )

        # Notify the user
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text="Your chat registration has been approved! You can now use the bot.",
            )
        except Exception as e:
            logging.error(f"Failed to notify chat {chat_id}: {e}")
        return

    async def remove_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a chat from config"""
        if str(update.effective_chat.id) != DEVELOPER_CHAT_ID:
            await update.message.reply_text("Only the admin can remove chats.")
            return

        try:
            chat_id = context.args[0]
        except IndexError:
            await update.message.reply_text("Usage: /removechat <chat_id>")
            return

        config = load_config()
        if chat_id in config:
            del config[chat_id]
            save_config(config)
            await update.message.reply_text(f"Chat {chat_id} removed successfully!")
        else:
            await update.message.reply_text(f"Chat {chat_id} not found in config.")

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
    bot.run()
