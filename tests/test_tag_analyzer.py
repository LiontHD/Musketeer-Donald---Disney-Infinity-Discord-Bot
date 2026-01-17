import pytest
import os
import sys
import json

# Add project root to path
sys.path.append(os.getcwd())

from services.tag_analyzer import SimpleTagAnalyzer

@pytest.fixture
def tag_analyzer():
    # Create a temporary tags file for testing
    test_tags = {
        "Disney": ["mickey", "donald"],
        "Marvel": ["iron man", "thor"],
        "Star Wars": ["luke", "vader"]
    }
    with open("test_tags.json", "w") as f:
        json.dump(test_tags, f)
    
    analyzer = SimpleTagAnalyzer("test_tags.json")
    yield analyzer
    
    # Cleanup
    if os.path.exists("test_tags.json"):
        os.remove("test_tags.json")

def test_analyze_text_disney(tag_analyzer):
    tags = tag_analyzer.analyze_text("I love Mickey Mouse!")
    assert "Disney" in tags
    assert "Marvel" not in tags

def test_analyze_text_marvel(tag_analyzer):
    tags = tag_analyzer.analyze_text("Iron Man is cool.")
    assert "Marvel" in tags

def test_analyze_text_multiple(tag_analyzer):
    tags = tag_analyzer.analyze_text("Luke Skywalker met Thor.")
    assert "Star Wars" in tags
    assert "Marvel" in tags

def test_analyze_text_other(tag_analyzer):
    tags = tag_analyzer.analyze_text("Just a random sentence.")
    assert "Other" in tags
    assert len(tags) == 1
