
DIGITS = {
    '0': [
        "██████",
        "█    █",
        "█    █",
        "█    █",
        "██████"
    ],
    '1': [
        "  ██  ",
        "  ██  ",
        "  ██  ",
        "  ██  ",
        "  ██  "
    ],
    '2': [
        "██████",
        "     █",
        "██████",
        "█     ",
        "██████"
    ],
    '3': [
        "██████",
        "     █",
        "██████",
        "     █",
        "██████"
    ],
    '4': [
        "█    █",
        "█    █",
        "██████",
        "     █",
        "     █"
    ],
    '5': [
        "██████",
        "█     ",
        "██████",
        "     █",
        "██████"
    ],
    '6': [
        "██████",
        "█     ",
        "██████",
        "█    █",
        "██████"
    ],
    '7': [
        "██████",
        "     █",
        "     █",
        "     █",
        "     █"
    ],
    '8': [
        "██████",
        "█    █",
        "██████",
        "█    █",
        "██████"
    ],
    '9': [
        "██████",
        "█    █",
        "██████",
        "     █",
        "██████"
    ]
}

def get_big_number(number: int) -> str:
    """Converts a number into a large ASCII art string."""
    num_str = str(number)
    lines = ["", "", "", "", ""]
    
    for digit in num_str:
        if digit in DIGITS:
            digit_lines = DIGITS[digit]
            for i in range(5):
                lines[i] += digit_lines[i] + "  "  # Add spacing between digits
                
    return "\n".join(lines)
