# Musketeer Donald ⚔️

> **AI-Powered Community Manager for Disney Infinity**
> 
> *Revolutionizing content discovery for 4,700 members with Retrieval-Augmented Generation (RAG).*

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Discord](https://img.shields.io/badge/Discord-Bot-5865F2.svg?style=for-the-badge&logo=discord&logoColor=white)
![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2.svg?style=for-the-badge&logo=google&logoColor=white)
![Oracle Cloud](https://img.shields.io/badge/Deployed%20on-Oracle%20Cloud-du2c38.svg?style=for-the-badge&logo=oracle&logoColor=white)

## 📖 Overview

**Musketeer Donald** is a sophisticated Discord bot designed to solve a critical User Experience bottleneck for the [Disney Infinity Community](https://discord.gg/disneyinfinity). With a database of over 1,000+ assets (toyboxes), finding specific content was a manual and repetitive process. 


This project solves that by acting as an **Intelligent Archive Manager**, using Google's Gemini AI to understand natural language queries and instantly retrieve relevant game saves, tutorials, and community resources.

## ✨ Key Features

### 🤖 Intelligent Content Discovery (RAG)
- **Semantic Search:** Users can ask questions naturally (e.g., *"Find me a Star Wars racing map"*).
- **RAG Architecture:** Leverages **Google Gemini** to analyze and index metadata from 1,000+ files.
- **Instant Answers:** Reduces discovery time from minutes to seconds.

### 📦 Automated Asset Management (DevOps)
- **`/add_to_bundle`:** A powerful automated pipeline that collects ZIP files from Discord threads, extracts them, renumbers the internal game files (`SRR`, `EHRR` formats), and repackages them into a single downloadable bundle.
- **Legacy File Conversion:** Custom utilities to convert between "Toybox" and "Toybox Game" file formats automatically.

### ⚙️ Full-Stack Integration
- **Airtable Sync:** Seamlessly syncs community ratings and metadata with an Airtable backend.
- **Dynamic Rating System:** Allows users to rate and review content directly within Discord.
- **Zero-Cost Infrastructure:** Architected to run 24/7 on Oracle Cloud's Free Tier.

## 🛠️ Tech Stack

*   **Core:** Python, `discord.py`
*   **AI & Search:** Google Gemini (LLM), ChromaDB (Vector Search / RAG)
*   **Data & Storage:** Airtable API, JSON
*   **Infrastructure:** Oracle Cloud Compute
*   **Utilities:** `aiohttp` for async operations, custom binary file parsers.

## 🚀 Installation & Setup

1.  **Clone the repository**
    ```bash
    git clone https://github.com/LiontHD/Musketeer-Donald---Disney-Infinity-Discord-Bot.git
    cd Musketeer-Donald---Disney-Infinity-Discord-Bot
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Configuration**
    Create a `.env` file in the root directory:
    ```ini
    BOT_TOKEN=your_discord_token
    GEMINI_API_KEY=your_gemini_key
    AIRTABLE_API_KEY=your_airtable_key
    AIRTABLE_BASE_ID=your_base_id
    ```

4.  **Run the Bot**
    ```bash
    python main.py
    ```

## ☁️ Deployment (Recommended)

To host the bot 24/7 for **free**, I highly recommend using **Oracle Cloud Free Tier**:
1.  Create an account on Oracle Cloud.
2.  Provision an **Always Free VM instance** (e.g., ARM Ampere).
3.  Clone this repo and run it using a process manager like `systemd` or `screen`.


## 📜 License

This project is open-source and available under the MIT License.

---
*Built with ❤️ for the Disney Infinity Community.*
