# Donald Bot (Oracle Instance)

A Discord bot for managing Disney Infinity toyboxes, including features for downloading, renumbering, and analyzing toybox files.

## Features
- **Toybox Management**: Download, analyze, and verify toybox files.
- **Bundle Creation**: Interactive `/add_to_bundle` command to collect and package multiple toyboxes correctly renumbered.
- **File Conversion**: Tools to convert between Toybox and Toybox Game formats.
- **RAG Integration**: Ask questions about toyboxes using Google Gemini.

## Setup

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd <repo-name>
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Create a `.env` file in the root directory (do not commit this file!) with the following variables:
   ```ini
   BOT_TOKEN=your_discord_bot_token
   AIRTABLE_API_KEY=your_airtable_key
   AIRTABLE_BASE_ID=your_airtable_base_id
   GEMINI_API_KEY=your_gemini_key
   ```

4. **Run the bot:**
   ```bash
   python main.py
   ```

## Development
- **Configuration**: Settings are managed in `config.py`.
- **Cogs**: Features are modularized in the `cogs/` directory.

## License
[Your License Here]
