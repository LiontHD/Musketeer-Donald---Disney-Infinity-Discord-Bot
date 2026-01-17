import re
from typing import Dict, Any, List

# Regex patterns
TEXT_PATTERN = re.compile(r'"([^"]*)"')
SRR_FILE_PATTERN = re.compile(r'^SRR\d+[A-Z]?$')
EHRR_FILE_PATTERN = re.compile(r'^EHRR\d+[A-Z]?$')
AUTHOREDNAME_PATTERN = re.compile(r'AUTHOREDNAME\s*=\s*"([^"]*)"')
AUTHOREDDESC_PATTERN = re.compile(r'AUTHOREDDESC\s*=\s*"([^"]*)"')

def analyze_and_parse_toybox_file(file_content: bytes) -> Dict[str, Any]:
    try:
        # Try UTF-8 first
        lines = file_content.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        # Fallback to latin-1
        lines = file_content.decode('latin-1').splitlines()

    full_text = "\n".join(lines)
    
    toys, tc_count, cm_count, it_count, i = [], 0, 0, 0, 0

    # Search for EHRR metadata
    name_match = AUTHOREDNAME_PATTERN.search(full_text)
    desc_match = AUTHOREDDESC_PATTERN.search(full_text)
    if name_match and desc_match:
        toys.append({"type": "Metadata", "id": 1})

    while i < len(lines):
        line = lines[i].strip()
        if '"@AR_TextInput1_Default"' in line and i + 9 < len(lines) and all(f'"@AR_TextInput{j+1}_Default"' in lines[i+j].strip() for j in range(1, 10)):
            tc_count += 1
            toys.append({"type": "Text Creator", "id": tc_count, "line_indices": {f'line_{j+1}': i + j for j in range(10)}})
            i += 10
            continue
        if '"@AR_ChallengeTitle"' in line and i + 1 < len(lines) and '"@AR_ChallengeDescription"' in lines[i+1].strip():
            cm_count += 1
            toys.append({"type": "Challenge Maker", "id": cm_count, "line_indices": {"title": i, "description": i + 1}})
            i += 2
            continue
        if '"@AR_PromptText"' in line:
            it_count += 1
            toys.append({"type": "Input Toy", "id": it_count, "line_indices": {"prompt": i}})
            i += 1
            continue
        i += 1
    return {"toys": toys, "lines": lines}
