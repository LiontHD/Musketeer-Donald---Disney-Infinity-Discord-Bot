import os
import zipfile
import io
import asyncio
import shutil
import tempfile
from services.image_injector_service import ImageInjectorService
from services.file_parser import analyze_and_parse_toybox_file, EHRR_FILE_PATTERN

async def test_change_toybox_metadata_logic():
    print("Testing /change_toybox_metadata logic...")
    
    # 1. Create a mock toybox zip with SCCA0 and a mock EHRR file
    scca0_path = "meta/DI3SaveGameEditor/SCCA0"
    if not os.path.exists(scca0_path):
        print(f"Error: {scca0_path} not found.")
        return

    with open(scca0_path, 'rb') as f:
        scca0_data = f.read()
        
    # Create a mock EHRR file (valid toybox format)
    # We need a valid compressed file for inflate.py to work, or we can just mock the logic
    # Since we can't easily create a valid compressed EHRR without the tool, 
    # let's just test the screenshot injection part + zip handling part of the logic.
    # We will assume the EHRR part works if the zip is structured correctly.
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SCCA0", scca0_data)
        zf.writestr("EHRR19", b"mock_ehrr_data") # This won't decompress, but we can check if it's found
    
    zip_bytes = zip_buffer.getvalue()
    print(f"Created mock zip ({len(zip_bytes)} bytes)")

    # 2. Mock inputs
    image_path = "meta/DI3SaveGameEditor/avengers.jpg"
    with open(image_path, 'rb') as f:
        image_bytes = f.read()

    # 3. Simulate the command logic
    temp_dir = tempfile.mkdtemp()
    try:
        zip_path = os.path.join(temp_dir, "test.zip")
        
        # Logic Step 1: Process Screenshot
        injector = ImageInjectorService()
        modified_zip_bytes, _ = injector.process_toybox(zip_bytes, image_bytes)
        print("Screenshot injection successful.")
        
        with open(zip_path, 'wb') as f:
            f.write(modified_zip_bytes)
            
        # Logic Step 2: Check Zip Content
        extract_folder = os.path.join(temp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_folder)
            
        ehrr_found = False
        scca_modified = False
        
        for root, _, files in os.walk(extract_folder):
            for file in files:
                if file == "EHRR19":
                    ehrr_found = True
                if file == "SCCA0":
                    with open(os.path.join(root, file), 'rb') as f:
                        if f.read() != scca0_data:
                            scca_modified = True
                            
        if ehrr_found:
            print("SUCCESS: EHRR file preserved/found.")
        else:
            print("FAILURE: EHRR file lost.")
            
        if scca_modified:
            print("SUCCESS: SCCA0 file modified.")
        else:
            print("FAILURE: SCCA0 file not modified.")

    except Exception as e:
        print(f"FAILURE: Exception: {e}")
        import traceback
        traceback.print_exc()
    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    asyncio.run(test_change_toybox_metadata_logic())
