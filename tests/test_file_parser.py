import pytest
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.file_parser import analyze_and_parse_toybox_file

def test_parse_metadata():
    content = b'AUTHOREDNAME = "Test Toybox"\nAUTHOREDDESC = "A test description"'
    result = analyze_and_parse_toybox_file(content)
    
    toys = result['toys']
    assert len(toys) == 1
    assert toys[0]['type'] == 'Metadata'

def test_parse_text_creator():
    # Simulate a Text Creator block (10 lines)
    lines = []
    for i in range(1, 11):
        lines.append(f'"@AR_TextInput{i}_Default" = "Line {i}"')
    
    content = "\n".join(lines).encode('utf-8')
    result = analyze_and_parse_toybox_file(content)
    
    toys = result['toys']
    assert len(toys) == 1
    assert toys[0]['type'] == 'Text Creator'
    assert toys[0]['id'] == 1

def test_parse_challenge_maker():
    content = b'"@AR_ChallengeTitle" = "Challenge"\n"@AR_ChallengeDescription" = "Desc"'
    result = analyze_and_parse_toybox_file(content)
    
    toys = result['toys']
    assert len(toys) == 1
    assert toys[0]['type'] == 'Challenge Maker'

def test_parse_input_toy():
    content = b'"@AR_PromptText" = "Prompt"'
    result = analyze_and_parse_toybox_file(content)
    
    toys = result['toys']
    assert len(toys) == 1
    assert toys[0]['type'] == 'Input Toy'
