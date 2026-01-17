import os
import zipfile
import re
import tempfile
import io

def test_batch_logic():
    print("Testing batch renumbering logic...")
    
    # Mock inputs
    sequence = [1, 2, 15]
    
    # Mock zip content
    # Zip 1: SRR234.txt
    zip1 = io.BytesIO()
    with zipfile.ZipFile(zip1, 'w') as zf:
        zf.writestr("SRR234.txt", "content1")
    
    # Zip 2: JAILHOUSE_SRS5.bin
    zip2 = io.BytesIO()
    with zipfile.ZipFile(zip2, 'w') as zf:
        zf.writestr("JAILHOUSE_SRS5.bin", "content2")
        
    # Zip 3: FOLDER/SRR99.txt (nested)
    zip3 = io.BytesIO()
    with zipfile.ZipFile(zip3, 'w') as zf:
        zf.writestr("FOLDER/SRR99.txt", "content3")

    zips = [zip1.getvalue(), zip2.getvalue(), zip3.getvalue()]
    
    with tempfile.TemporaryDirectory() as temp_dir:
        merged_dir = os.path.join(temp_dir, "merged")
        os.makedirs(merged_dir)
        
        for idx, data in enumerate(zips):
            new_number = sequence[idx]
            print(f"Processing Zip {idx+1} with new number {new_number}")
            
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for file_info in zf.infolist():
                    if file_info.filename.endswith('/'): continue
                    
                    original_name = os.path.basename(file_info.filename)
                    print(f"  Found file: {original_name}")
                    
                    new_name = original_name
                    match = re.search(r'([A-Z]+)(\d+)(\.[^.]+)$', original_name)
                    if match:
                        prefix_part, old_num, ext = match.groups()
                        new_name = original_name[:match.start(2)] + str(new_number) + original_name[match.end(2):]
                        print(f"  Renamed to: {new_name}")
                    else:
                        print(f"  No match for regex, keeping: {new_name}")
                        
                    with open(os.path.join(merged_dir, new_name), 'wb') as f:
                        f.write(b"dummy")
                        
        print("\nMerged directory content:")
        for f in os.listdir(merged_dir):
            print(f" - {f}")

if __name__ == "__main__":
    test_batch_logic()
