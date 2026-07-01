# ReviewForge 🚀

**ReviewForge** is a powerful, AI-driven command-line pair programming assistant built to help you write, edit, and understand code faster. Simply chat with ReviewForge in your terminal, and it will intelligently edit your source code files and manage your git commits for you.

## ✨ Key Functionality & Features

- **Automated Code Editing:** ReviewForge doesn't just give you code snippets; it directly applies targeted edits, diffs, and whole-file replacements directly to your local files.
- **Git Integration:** It automatically stages and commits its own changes with sensible, AI-generated commit messages. You can easily `/undo` any change you don't like.
- **Chat in your Terminal:** Features a rich, interactive terminal UI with markdown streaming, colorized output, and auto-completion.
- **Multi-Model Support:** By default powered by `gemini-2.0-flash`, but natively supports any major model (Claude, GPT-4, DeepSeek, OpenRouter) via LiteLLM.
- **Advanced Context Management:** Add specific files to the chat using `/add <file>`, drop them with `/drop`, and maintain a sliding window of your chat history.
- **Command-Line Native:** Run terminal commands directly from the chat and feed their output back to the LLM for seamless debugging.

## 📦 Installation

Since the project is hosted on your GitHub, anyone can install it directly via Git, or you can clone it and install it locally:

```bash
# Install directly from your GitHub repository
pip install git+https://github.com/AyushGU12/ReviewForge.git

# OR clone and install locally
git clone https://github.com/AyushGU12/ReviewForge.git
cd ReviewForge
pip install -e .
```

## 🚀 Getting Started

1. **Set your API Key:**  
   ReviewForge needs an LLM to power it. For Gemini:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

2. **Start the assistant:**
   Run the tool inside any of your project directories:
   ```bash
   reviewforge
   ```

3. **Start Coding:**
   Add a file to the chat and ask it to do something!
   ```text
   > /add my_script.py
   > Please refactor this file to use classes instead of global functions.
   ```

## 🛠️ Built-in Commands

Inside the chat, you can use shortcuts to manage your workflow:
- `/add <files>`: Add files so the AI can read and edit them.
- `/drop <files>`: Remove files from the AI's context.
- `/ls`: List all files currently in the chat.
- `/commit`: Manually commit any dirty changes in your repo.
- `/undo`: Undo the last git commit.
- `/clear`: Clear the chat history.
- `/run <command>`: Run a shell command and share the output with the AI.
- `/exit` or `/quit`: Exit ReviewForge.

---
*Built from scratch by Shikhar.*
