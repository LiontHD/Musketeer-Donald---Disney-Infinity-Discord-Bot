import os
import zipfile
import io
from services.image_injector_service import ImageInjectorService

def test_image_injector():
    print("Testing ImageInjectorService...")
    
    # 1. Create a mock toybox zip
    # We'll use the SCCA0 file we have and put it in a zip
    scca0_path = "meta/DI3SaveGameEditor/SCCA0"
    if not os.path.exists(scca0_path):
        print(f"Error: {scca0_path} not found.")
        return

    with open(scca0_path, 'rb') as f:
        scca0_data = f.read()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SCCA0", scca0_data)
        zf.writestr("other_file.txt", "just some text")
    
    zip_bytes = zip_buffer.getvalue()
    print(f"Created mock zip with SCCA0 ({len(zip_bytes)} bytes)")

    # 2. Load an image
    image_path = "meta/DI3SaveGameEditor/avengers.jpg"
    if not os.path.exists(image_path):
        print(f"Error: {image_path} not found.")
        return

    with open(image_path, 'rb') as f:
        image_bytes = f.read()
    print(f"Loaded image ({len(image_bytes)} bytes)")

    # 3. Run the service
    injector = ImageInjectorService()
    try:
        modified_zip_bytes, filename = injector.process_toybox(zip_bytes, image_bytes)
        print(f"Service returned {len(modified_zip_bytes)} bytes, filename: {filename}")
        
        # 4. Verify the output
        with zipfile.ZipFile(io.BytesIO(modified_zip_bytes), 'r') as zf:
            print("Contents of modified zip:")
            for item in zf.infolist():
                print(f" - {item.filename}: {item.file_size} bytes")
                
            # Check if SCCA0 was modified
            if "SCCA0" in zf.namelist():
                new_scca0_data = zf.read("SCCA0")
                if new_scca0_data != scca0_data:
                    print("SUCCESS: SCCA0 data has been modified.")
                else:
                    print("FAILURE: SCCA0 data is identical to original.")
            else:
                print("FAILURE: SCCA0 not found in modified zip.")

    except Exception as e:
        print(f"FAILURE: Service raised exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_image_injector()
