import io
import struct
import zlib
import re
import zipfile
import logging
import numpy as np
from PIL import Image
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class ImageInjectorService:
    """
    Service to handle the injection of custom screenshots into Disney Infinity 3.0 save files.
    """

    def __init__(self):
        pass

    def process_toybox(self, zip_bytes: bytes, image_bytes: bytes) -> tuple[bytes, str]:
        """
        Processes a Toybox ZIP file, replacing the screenshot in the save file with the provided image.
        
        Args:
            zip_bytes: The raw bytes of the input ZIP file.
            image_bytes: The raw bytes of the input image (PNG/JPG).
            
        Returns:
            A tuple containing (modified_zip_bytes, filename_of_modified_zip).
        """
        try:
            # 1. Load and convert image to binary DXT1
            bin_data = self._convert_image_to_bin(image_bytes)
            
            # 2. Process ZIP file
            output_zip_io = io.BytesIO()
            
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as in_zip, \
                 zipfile.ZipFile(output_zip_io, 'w', zipfile.ZIP_DEFLATED) as out_zip:
                
                found_save_file = False
                
                for item in in_zip.infolist():
                    file_data = in_zip.read(item.filename)
                    
                    # Check if this is a save file (SCCA* or SCRR*)
                    # Usually they are at the root or in a folder, but we look for the filename pattern
                    filename = Path(item.filename).name
                    if (filename.startswith("SCCA") or filename.startswith("SCRR")) and not filename.endswith(".dec"):
                        logger.info(f"Found save file candidate: {item.filename}")
                        
                        try:
                            # Attempt to process this file
                            modified_data = self._inject_into_save_file(file_data, bin_data)
                            out_zip.writestr(item, modified_data)
                            found_save_file = True
                            logger.info(f"Successfully modified {item.filename}")
                        except Exception as e:
                            logger.error(f"Failed to process {item.filename}: {e}")
                            # If we fail, just write the original file back? 
                            # Or maybe we shouldn't fail silently. For now, write original back.
                            out_zip.writestr(item, file_data)
                    else:
                        # Copy other files as is
                        out_zip.writestr(item, file_data)
                
                if not found_save_file:
                    raise ValueError("No valid save file (SCCA* or SCRR*) found in the ZIP.")

            return output_zip_io.getvalue(), "modified_toybox.zip"

        except Exception as e:
            logger.error(f"Error in process_toybox: {e}")
            raise

    def _convert_image_to_bin(self, image_bytes: bytes) -> bytes:
        """Converts an image (bytes) to DXT1 binary format, resizing if necessary."""
        img = Image.open(io.BytesIO(image_bytes))
        
        # Resize to 384x208 if needed
        target_size = (384, 208)
        if img.size != target_size:
            logger.info(f"Resizing image from {img.size} to {target_size}")
            img = img.resize(target_size, Image.Resampling.LANCZOS)
            
        return self._compress_dxt1(img)

    def _inject_into_save_file(self, save_file_data: bytes, bin_data: bytes) -> bytes:
        """Full pipeline: Decompress -> Inject -> Recompress"""
        
        # 1. Decompress
        decompressed_data, header_info = self._decompress_file(save_file_data)
        
        # 2. Inject
        # Convert binary data to hex string
        hex_blob = bin_data.hex()
        
        # Decode bytes to string for regex replacement (assuming latin-1 or utf-8, usually safe for these files)
        # These files are mixed binary/text, but the part we need is text.
        # However, Python strings are unicode. We need to be careful.
        # The safest way is to treat it as bytes or decode with error replacement.
        # Given the previous scripts used read_text(), let's try decoding as utf-8 or latin-1.
        try:
            text_content = decompressed_data.decode('utf-8')
        except UnicodeDecodeError:
            text_content = decompressed_data.decode('latin-1')

        pattern = re.compile(r'(SCREENSHOT\s*=\s*\$)(.*?)(?=\$)', re.DOTALL)
        if not pattern.search(text_content):
            raise ValueError("Could not find 'SCREENSHOT = $' block in decompressed data.")
            
        # Replace
        # Note: The original script used re.sub with a string.
        new_text_content = pattern.sub(r'\1' + hex_blob, text_content, count=1)
        
        # Encode back to bytes
        new_decompressed_data = new_text_content.encode('utf-8') # Or latin-1? Usually these are ASCII/UTF-8 compatible.
        
        # 3. Recompress
        return self._compress_file_fixed(new_decompressed_data, save_file_data)

    # --- Helper methods adapted from existing scripts ---

    def _hash_file(self, k: bytes, length: int, initval: int) -> int:
        """Jenkins hash implementation from inflate.py"""
        def mix(a, b, c):
            a = (a - b - c) & 0xffffffff; a ^= (c >> 13)
            b = (b - c - a) & 0xffffffff; b ^= (a << 8) & 0xffffffff
            c = (c - a - b) & 0xffffffff; c ^= (b >> 13)
            a = (a - b - c) & 0xffffffff; a ^= (c >> 12)
            b = (b - c - a) & 0xffffffff; b ^= (a << 16) & 0xffffffff
            c = (c - a - b) & 0xffffffff; c ^= (b >> 5)
            a = (a - b - c) & 0xffffffff; a ^= (c >> 3)
            b = (b - c - a) & 0xffffffff; b ^= (a << 10) & 0xffffffff
            c = (c - a - b) & 0xffffffff; c ^= (b >> 15)
            return a & 0xffffffff, b & 0xffffffff, c & 0xffffffff

        a = b = 0x9e3779b9
        c = initval
        pos = 0

        while length - pos >= 12:
            a += int.from_bytes(k[pos:pos+4], 'little')
            b += int.from_bytes(k[pos+4:pos+8], 'little')
            c += int.from_bytes(k[pos+8:pos+12], 'little')
            a, b, c = mix(a & 0xffffffff, b & 0xffffffff, c & 0xffffffff)
            pos += 12

        c += length
        remainder = k[pos:]

        if len(remainder) >= 11: c += remainder[10] << 24
        if len(remainder) >= 10: c += remainder[9] << 16
        if len(remainder) >= 9:  c += remainder[8] << 8
        if len(remainder) >= 8:  b += remainder[7] << 24
        if len(remainder) >= 7:  b += remainder[6] << 16
        if len(remainder) >= 6:  b += remainder[5] << 8
        if len(remainder) >= 5:  b += remainder[4]
        if len(remainder) >= 4:  a += remainder[3] << 24
        if len(remainder) >= 3:  a += remainder[2] << 16
        if len(remainder) >= 2:  a += remainder[1] << 8
        if len(remainder) >= 1:  a += remainder[0]

        a, b, c = mix(a & 0xffffffff, b & 0xffffffff, c & 0xffffffff)
        return c & 0xffffffff

    def _decompress_file(self, data: bytes) -> tuple[bytes, dict]:
        """Decompresses the save file data."""
        # Read Main Header
        # version = struct.unpack('<I', data[0:4])[0]
        # total_filesize = struct.unpack('<I', data[4:8])[0]
        
        # Find CMP1 marker
        try:
            cmp1_offset = data.index(b'CMP1')
        except ValueError:
            raise ValueError("'CMP1' magic string not found in file.")

        # Read CMP1 Header
        cmp1_header_offset = cmp1_offset + 4
        # uncompressed_size = struct.unpack('<i', data[cmp1_header_offset:cmp1_header_offset+4])[0]
        compressed_size = struct.unpack('<i', data[cmp1_header_offset+4:cmp1_header_offset+8])[0]
        
        # The actual compressed data starts after the CMP1 header (20 bytes total)
        compressed_data_offset = cmp1_offset + 20
        compressed_data = data[compressed_data_offset : compressed_data_offset + compressed_size]

        try:
            decompressed_data = zlib.decompress(compressed_data)
            return decompressed_data, {} # We don't strictly need the header info for recompression as we use the original file as template
        except zlib.error as e:
            raise ValueError(f"Decompression failed: {e}")

    def _compress_file_fixed(self, raw_data: bytes, original_file_data: bytes) -> bytes:
        """Compresses the data back into the save file format."""
        
        # --- Compression (Level 1) ---
        compressed_data = zlib.compress(raw_data, 1)
        
        uncompressed_size = len(raw_data)
        compressed_size = len(compressed_data)

        uncompressed_checksum = self._hash_file(raw_data, len(raw_data), 0)
        compressed_checksum = self._hash_file(compressed_data, len(compressed_data), 0)

        # Build CMP1 block header
        cmp1_header = b'CMP1'
        cmp1_header += struct.pack('<iiII', uncompressed_size, compressed_size, uncompressed_checksum, compressed_checksum)

        # Combine header and compressed data
        cmp1_block_unpadded = cmp1_header + compressed_data
        
        # --- FINAL FIX v3: Pad to the next 64-byte boundary ---
        pad_len = (64 - (len(cmp1_block_unpadded) % 64)) % 64
        padding = b'\x00' * pad_len
        
        # Final CMP1 block
        final_cmp1_block = cmp1_block_unpadded + padding
        unpadded_size_new = len(final_cmp1_block)
        
        # --- Reuse the original main header but overwrite ALL size-related values ---
        cmp1_offset = 64
        total_filesize_new = cmp1_offset + unpadded_size_new

        final_data = bytearray(original_file_data) 
        final_data[4:8] = struct.pack('<I', total_filesize_new)
        final_data[12:16] = struct.pack('<I', uncompressed_size)
        final_data[16:20] = struct.pack('<I', unpadded_size_new)
        
        # Construct the final file
        final_data = final_data[:cmp1_offset] + final_cmp1_block
        
        # Ensure the final byte stream has the correct total length
        final_data = final_data[:total_filesize_new]
        
        return bytes(final_data)

    def _convert_rgb_to_565(self, r, g, b):
        return ((int(r) >> 3) << 11) | ((int(g) >> 2) << 5) | (int(b) >> 3)

    def _pack_dxt1_block(self, block):
        pixels = block.reshape(-1, 3)
        min_col = np.min(pixels, axis=0)
        max_col = np.max(pixels, axis=0)
        
        c0 = self._convert_rgb_to_565(*max_col)
        c1 = self._convert_rgb_to_565(*min_col)
        
        if c0 < c1:
            c0, c1 = c1, c0
            max_col, min_col = min_col, max_col

        def expand565(c):
            r = ((c >> 11) & 0x1F) * 255 // 31
            g = ((c >>  5) & 0x3F) * 255 // 63
            b = ( c        & 0x1F) * 255 // 31
            return np.array([r, g, b])

        rgb0 = expand565(c0)
        rgb1 = expand565(c1)
        
        palette = np.zeros((4, 3))
        palette[0] = rgb0
        palette[1] = rgb1
        palette[2] = (2 * rgb0 + rgb1) // 3
        palette[3] = (rgb0 + 2 * rgb1) // 3
        
        indices = []
        for p in pixels:
            dists = np.sum((palette - p)**2, axis=1)
            indices.append(np.argmin(dists))
            
        packed_indices = 0
        for i, idx in enumerate(indices):
            packed_indices |= (idx << (2 * i))
            
        return struct.pack('<HHI', c0, c1, packed_indices)

    def _compress_dxt1(self, img):
        width, height = img.size
        # Ensure dimensions are multiples of 4
        # (The resize step should handle this, but good to be safe)
        
        arr = np.array(img.convert('RGB'))
        blocks_x = width // 4
        blocks_y = height // 4
        
        dxt_data = bytearray()
        
        for by in range(blocks_y):
            for bx in range(blocks_x):
                y0, x0 = by * 4, bx * 4
                block = arr[y0:y0+4, x0:x0+4]
                
                if block.shape != (4, 4, 3):
                    padded = np.zeros((4, 4, 3), dtype=np.uint8)
                    h, w, _ = block.shape
                    padded[:h, :w, :] = block
                    block = padded
                    
                dxt_data.extend(self._pack_dxt1_block(block))
                
        return bytes(dxt_data)
