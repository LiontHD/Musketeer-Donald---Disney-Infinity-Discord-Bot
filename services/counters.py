import re
import zipfile
import io
import os
import tempfile
import shutil
from collections import defaultdict

class ToyboxCounter:
    def __init__(self):
        self.counting_sessions = {}
        self.progress_messages = {}  # Store progress message IDs
        
    def count_srr_files(self, zip_data: bytes, filename: str) -> int:
        count = 0
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
            file_list = zip_ref.namelist()
            for file in file_list:
                base_name = os.path.basename(file)
                if re.match(r'^SRR\d+[A-Z]', base_name):
                    count += 1
        return count

class SlotCounter:
    def __init__(self):
        self.pattern = re.compile(r"SHRR(\d+)([A-J]?)")

    async def download_and_extract_zip(self, url):
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download file: {response.status}")
                zip_data = await response.read()
        
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                # Get all file paths in the zip
                file_list = zip_ref.namelist()
                # Filter for SHRR files
                shrr_files = [f for f in file_list if "SHRR" in f.upper()]
                # Extract only SHRR files
                for file in shrr_files:
                    zip_ref.extract(file, temp_dir)
            
            # Walk through all subdirectories to find the SHRR files
            shrr_paths = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if "SHRR" in file.upper():
                        shrr_paths.append(os.path.join(root, file))
            
            if not shrr_paths:
                raise Exception("No SHRR files found in the zip file")
                
            # Use the directory containing the SHRR files
            base_path = os.path.dirname(shrr_paths[0])
            return base_path, temp_dir
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise Exception(f"Failed to process zip file: {str(e)}")

    def count_unique_files(self, folder_path):
        counts = defaultdict(set)
        
        # Walk through all subdirectories
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if "SHRR" in filename.upper():  # Only process SHRR files
                    match = self.pattern.match(filename)
                    if match:
                        number, letter = match.groups()
                        counts[number].add(letter if letter else '')
        
        total_count = sum(len(letters) for letters in counts.values())
        
        # Format results
        results = []
        for number, letters in sorted(counts.items(), key=lambda x: int(x[0])):
            letters_str = ', '.join(sorted(letter for letter in letters if letter))
            base = f"SHRR{number}"
            if letters_str:
                results.append(f"{base}: {letters_str}")
            else:
                results.append(base)
            
        return total_count, results

    def find_missing_numbers(self, folder_path, min_num=0, max_num=300):
        all_numbers = set(range(min_num, max_num + 1))
        found_numbers = set()
        
        # Walk through all subdirectories
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if "SHRR" in filename.upper():  # Only process SHRR files
                    match = re.findall(r'SHRR(\d+)', filename.upper())
                    if match:
                        found_numbers.update(map(int, match))
        
        missing_numbers = all_numbers - found_numbers
        return sorted(missing_numbers)
