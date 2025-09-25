import os
import struct
import argparse
import glob

def swap_endianness(data):
    """ Swap endianness of the given byte data in 4-byte chunks. """
    swapped = bytearray()
    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        swapped.extend(chunk[::-1])  # Reverse byte order
    return swapped

def process_files(file_patterns):
    """ Process each file by swapping specific byte ranges and saving to a subdirectory. """
    output_dir = "converted_files"
    os.makedirs(output_dir, exist_ok=True)  # Create directory if it doesn't exist

    file_list = []
    for pattern in file_patterns:
        file_list.extend(glob.glob(pattern))  # Expand wildcards into actual file names

    if not file_list:
        print("No matching files found.")
        return

    for file in file_list:
        if not os.path.isfile(file):
            print(f"Skipping {file}: File not found.")
            continue

        with open(file, "rb") as f:
            original_data = f.read()

        if len(original_data) < 84:
            print(f"Skipping {file}: File is smaller than required 84 bytes.")
            continue

        # Swap endianness for first 64 bytes (0-63)
        swapped_first_64 = swap_endianness(original_data[:64])

        # Keep bytes 64-67 unchanged
        unchanged_bytes = original_data[64:68]

        # Swap endianness for bytes 68-83
        swapped_68_83 = swap_endianness(original_data[68:84])

        # Construct new file content
        new_data = swapped_first_64 + unchanged_bytes + swapped_68_83 + original_data[84:]

        output_path = os.path.join(output_dir, os.path.basename(file))
        with open(output_path, "wb") as f:
            f.write(new_data)

        print(f"Processed {file} → {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swap endianness for specific sections of files using wildcards.")
    parser.add_argument("patterns", nargs="+", help="Wildcard file patterns (e.g., *.dds)")
    args = parser.parse_args()

    process_files(args.patterns)