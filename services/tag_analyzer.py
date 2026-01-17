import json
import os
import logging

logger = logging.getLogger("DonaldBot")

class SimpleTagAnalyzer:
    def __init__(self, tags_file="data/tags.json"):
        self.tags_file = tags_file
        self.disney_keywords = set()
        self.marvel_keywords = set()
        self.star_wars_keywords = set()
        self.load_tags()

    def load_tags(self):
        """Loads tags from the JSON file."""
        if not os.path.exists(self.tags_file):
            logger.error(f"❌ Tags file not found: {self.tags_file}")
            return

        try:
            with open(self.tags_file, 'r') as f:
                data = json.load(f)
                self.disney_keywords = set(data.get("Disney", []))
                self.marvel_keywords = set(data.get("Marvel", []))
                self.star_wars_keywords = set(data.get("Star Wars", []))
            logger.info(f"✅ Loaded tags from {self.tags_file}")
        except Exception as e:
            logger.error(f"❌ Error loading tags: {e}")

    def analyze_text(self, text: str) -> list[str]:
        """
        Analyzes text and returns matching franchise tags.
        Returns "Other" if no franchise tags are found.
        """
        text = text.lower()
        tags = []
        
        # Check for each franchise using keywords
        if any(keyword in text for keyword in self.disney_keywords):
            tags.append("Disney")
            
        if any(keyword in text for keyword in self.marvel_keywords):
            tags.append("Marvel")
            
        if any(keyword in text for keyword in self.star_wars_keywords):
            tags.append("Star Wars")
            
        # If no tags were found, add "Other"
        if not tags:
            tags.append("Other")
            
        return tags
