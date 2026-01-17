import discord
from discord.ext import commands
from discord import app_commands
import os
import tempfile
import zipfile
import asyncio
import shutil
import traceback
import io


from services.file_parser import (
    analyze_and_parse_toybox_file, 
    SRR_FILE_PATTERN, 
    EHRR_FILE_PATTERN
)
from views.editor_views import (
    ToyboxEditView, 
    SRRFileSelectView, 
    EHRRFileSelectView
)

class ToyboxEditorCog(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot

    @app_commands.command(name="edit_toybox_text", description="Interactively edit texts in a Toybox .txt file.")
    @app_commands.describe(file="Upload the .txt file you want to edit (e.g., SRR2A.txt)")
    async def edit_toybox_text(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not file.filename.endswith('.txt'): 
            await interaction.followup.send("❌ Please upload a valid `.txt` file.", ephemeral=True)
            return
        try:
            parsed_data = analyze_and_parse_toybox_file(await file.read())
            if not parsed_data['toys']: 
                await interaction.followup.send("I couldn't find any editable toys in this file.", ephemeral=True)
                return
            view = ToyboxEditView(parsed_data, file.filename, mode='txt')
            await interaction.followup.send(embed=view.create_embed(), view=view)
        except Exception as e: 
            await interaction.followup.send(f"An unexpected error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)

    @app_commands.command(name="edit_toybox_zip", description="Seamlessly edit texts in a Toybox ZIP file.")
    @app_commands.describe(zip_file="Upload the Toybox ZIP file.")
    async def edit_toybox_zip(self, interaction: discord.Interaction, zip_file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not zip_file.filename.endswith('.zip'): 
            await interaction.followup.send("❌ Please upload a valid `.zip` file.", ephemeral=True)
            return
        temp_dir = tempfile.mkdtemp()
        try:
            zip_path = os.path.join(temp_dir, zip_file.filename)
            await zip_file.save(zip_path)
            extract_folder = os.path.join(temp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_folder)
            
            # Find all SRR files
            srr_files = []
            files_root = None
            for root, _, files in os.walk(extract_folder):
                for file in files:
                    if SRR_FILE_PATTERN.match(file):
                        srr_files.append({
                            'name': file,
                            'path': os.path.join(root, file)
                        })
                        if files_root is None:
                            files_root = root
            
            if not srr_files:
                shutil.rmtree(temp_dir)
                await interaction.followup.send("❌ No SRR files (e.g., SRR2A) found in the ZIP.", ephemeral=True)
                return
            
            script_path = os.path.join(os.getcwd(), 'inflate.py')
            if not os.path.exists(script_path):
                shutil.rmtree(temp_dir)
                await interaction.followup.send(f"❌ `inflate.py` not found in the bot's root directory: {script_path}", ephemeral=True)
                return
            
            # If only one SRR file, process it directly
            if len(srr_files) == 1:
                srr_file = srr_files[0]
                srr_path = srr_file['path']
                txt_path = os.path.join(files_root, f"{srr_file['name']}.txt")
                
                # Decompress the SRR file
                proc = await asyncio.create_subprocess_exec(
                    'python3', script_path, '-d', srr_path, txt_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send(f"❌ Decompression failed: {stderr.decode()}", ephemeral=True)
                    return
                
                # Parse the decompressed file
                with open(txt_path, 'rb') as f:
                    parsed_data = analyze_and_parse_toybox_file(f.read())
                
                if not parsed_data['toys']:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send("❌ I couldn't find any editable toys in the SRR file.", ephemeral=True)
                    return
                
                # Create context and start editing
                context = {
                    'temp_dir': temp_dir,
                    'files_root': files_root,
                    'original_zip_name': zip_file.filename,
                    'srr_path': srr_path,
                    'txt_path': txt_path,
                    'script_path': script_path
                }
                view = ToyboxEditView(parsed_data, srr_file['name'], 'zip', context)
                await interaction.followup.send(embed=view.create_embed(), view=view)
            
            else:
                # Multiple SRR files - check each one for toys and let user choose
                for srr_file in srr_files:
                    try:
                        srr_path = srr_file['path']
                        txt_path = os.path.join(files_root, f"{srr_file['name']}.txt")
                        
                        # Decompress to check for toys
                        proc = await asyncio.create_subprocess_exec(
                            'python3', script_path, '-d', srr_path, txt_path,
                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                        )
                        _, stderr = await proc.communicate()
                        
                        if proc.returncode == 0:
                            # Successfully decompressed, check for toys
                            with open(txt_path, 'rb') as f:
                                parsed_data = analyze_and_parse_toybox_file(f.read())
                            srr_file['toy_count'] = len(parsed_data['toys'])
                        else:
                            srr_file['toy_count'] = 0
                    except Exception:
                        srr_file['toy_count'] = 0
                
                # Find the first SRR file with toys as fallback
                srr_with_toys = next((srr for srr in srr_files if srr.get('toy_count', 0) > 0), None)
                
                if not srr_with_toys:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send("❌ No editable toys found in any of the SRR files.", ephemeral=True)
                    return
                
                # Create selection view
                view = SRRFileSelectView(srr_files, temp_dir, files_root, zip_file.filename, script_path)
                await interaction.followup.send(embed=view.create_embed(), view=view)
                
        except Exception as e:
            shutil.rmtree(temp_dir)
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)


    @app_commands.command(name="edit_name_description", description="Edit the name and description of a Toybox (from EHRR file).")
    @app_commands.describe(zip_file="Upload the Toybox ZIP file containing an EHRR file.")
    async def edit_name_description(self, interaction: discord.Interaction, zip_file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not zip_file.filename.endswith('.zip'):
            await interaction.followup.send("❌ Please upload a valid `.zip` file.", ephemeral=True)
            return
        
        temp_dir = tempfile.mkdtemp()
        try:
            zip_path = os.path.join(temp_dir, zip_file.filename)
            await zip_file.save(zip_path)
            extract_folder = os.path.join(temp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_folder)
            
            # Find all EHRR files
            ehrr_files = []
            files_root = None
            for root, _, files in os.walk(extract_folder):
                for file in files:
                    if EHRR_FILE_PATTERN.match(file):
                        ehrr_files.append({
                            'name': file,
                            'path': os.path.join(root, file)
                        })
                        if files_root is None:
                            files_root = root
            
            if not ehrr_files:
                shutil.rmtree(temp_dir)
                await interaction.followup.send("❌ No EHRR files (e.g., EHRR19) found in the ZIP.", ephemeral=True)
                return
            
            script_path = os.path.join(os.getcwd(), 'inflate.py')
            if not os.path.exists(script_path):
                shutil.rmtree(temp_dir)
                await interaction.followup.send(f"❌ `inflate.py` not found in the bot's root directory.", ephemeral=True)
                return

            # If only one EHRR file, process it directly
            if len(ehrr_files) == 1:
                ehrr_file = ehrr_files[0]
                ehrr_path = ehrr_file['path']
                txt_path = os.path.join(files_root, f"{ehrr_file['name']}.txt")
                
                proc = await asyncio.create_subprocess_exec(
                    'python3', script_path, '-d', ehrr_path, txt_path,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send(f"❌ Decompression failed: {stderr.decode()}", ephemeral=True)
                    return
                
                with open(txt_path, 'rb') as f:
                    parsed_data = analyze_and_parse_toybox_file(f.read())
                
                if not parsed_data['toys']:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send("❌ I couldn't find any editable metadata in the EHRR file.", ephemeral=True)
                    return
                
                context = {
                    'temp_dir': temp_dir,
                    'files_root': files_root,
                    'original_zip_name': zip_file.filename,
                    'srr_path': ehrr_path,
                    'txt_path': txt_path,
                    'script_path': script_path
                }
                view = ToyboxEditView(parsed_data, ehrr_file['name'], 'zip', context)
                await interaction.followup.send(embed=view.create_embed(), view=view)
            
            else:
                # Multiple EHRR files
                view = EHRRFileSelectView(ehrr_files, temp_dir, files_root, zip_file.filename, script_path)
                await interaction.followup.send(embed=view.create_embed(), view=view)

        except Exception as e:
            shutil.rmtree(temp_dir)
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)



    @app_commands.command(name="change_toybox_metadata", description="Change Toybox screenshot and/or name & description.")
    @app_commands.describe(toybox_zip="Upload the Toybox ZIP file.", screenshot="Optional: Upload a new screenshot (PNG/JPG).")
    async def change_toybox_metadata(self, interaction: discord.Interaction, toybox_zip: discord.Attachment, screenshot: discord.Attachment = None):
        await interaction.response.defer(ephemeral=True)
        
        if not toybox_zip.filename.endswith('.zip'):
            await interaction.followup.send("❌ Please upload a valid `.zip` file.", ephemeral=True)
            return
            
        if screenshot and not (screenshot.filename.lower().endswith(('.png', '.jpg', '.jpeg'))):
            await interaction.followup.send("❌ Please upload a valid image file (.png, .jpg, .jpeg) for the screenshot.", ephemeral=True)
            return

        temp_dir = tempfile.mkdtemp()
        try:
            zip_path = os.path.join(temp_dir, toybox_zip.filename)
            zip_data = await toybox_zip.read()
            
            screenshot_updated = False
            
            # 1. Process Screenshot if provided
            if screenshot:
                try:
                    image_data = await screenshot.read()
                    from services.image_injector_service import ImageInjectorService
                    injector = ImageInjectorService()
                    zip_data, _ = injector.process_toybox(zip_data, image_data)
                    screenshot_updated = True
                except Exception as e:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send(f"❌ Failed to process screenshot: {e}", ephemeral=True)
                    return

            # Save zip (either modified or original) to temp dir
            with open(zip_path, 'wb') as f:
                f.write(zip_data)

            # 2. Process Metadata (EHRR)
            extract_folder = os.path.join(temp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(extract_folder)
            
            ehrr_files = []
            files_root = None
            for root, _, files in os.walk(extract_folder):
                for file in files:
                    if EHRR_FILE_PATTERN.match(file):
                        ehrr_files.append({
                            'name': file,
                            'path': os.path.join(root, file)
                        })
                        if files_root is None:
                            files_root = root
            
            # Case A: EHRR Found - Launch Editor
            if ehrr_files:
                script_path = os.path.join(os.getcwd(), 'inflate.py')
                if not os.path.exists(script_path):
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send(f"❌ `inflate.py` not found.", ephemeral=True)
                    return

                if len(ehrr_files) == 1:
                    ehrr_file = ehrr_files[0]
                    ehrr_path = ehrr_file['path']
                    txt_path = os.path.join(files_root, f"{ehrr_file['name']}.txt")
                    
                    proc = await asyncio.create_subprocess_exec(
                        'python3', script_path, '-d', ehrr_path, txt_path,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    _, stderr = await proc.communicate()
                    if proc.returncode != 0:
                        shutil.rmtree(temp_dir)
                        await interaction.followup.send(f"❌ Decompression failed: {stderr.decode()}", ephemeral=True)
                        return
                    
                    with open(txt_path, 'rb') as f:
                        parsed_data = analyze_and_parse_toybox_file(f.read())
                    
                    if not parsed_data['toys']:
                        # Fallback if no editable metadata but screenshot updated
                        if screenshot_updated:
                            file = discord.File(zip_path, filename=toybox_zip.filename)
                            await interaction.followup.send(f"✅ Screenshot updated, but no editable metadata found.", file=file, ephemeral=True)
                            shutil.rmtree(temp_dir)
                            return
                        else:
                            shutil.rmtree(temp_dir)
                            await interaction.followup.send("❌ No editable metadata found.", ephemeral=True)
                            return
                    
                    context = {
                        'temp_dir': temp_dir,
                        'files_root': files_root,
                        'original_zip_name': toybox_zip.filename,
                        'srr_path': ehrr_path,
                        'txt_path': txt_path,
                        'script_path': script_path
                    }
                    view = ToyboxEditView(parsed_data, ehrr_file['name'], 'zip', context)
                    await interaction.followup.send(embed=view.create_embed(), view=view)
                
                else:
                    # Multiple EHRR files
                    view = EHRRFileSelectView(ehrr_files, temp_dir, files_root, toybox_zip.filename, script_path)
                    await interaction.followup.send(embed=view.create_embed(), view=view)

            # Case B: No EHRR Found
            else:
                if screenshot_updated:
                    file = discord.File(zip_path, filename=toybox_zip.filename)
                    await interaction.followup.send(f"✅ Screenshot updated! (No metadata file found to edit)", file=file, ephemeral=True)
                    shutil.rmtree(temp_dir)
                else:
                    shutil.rmtree(temp_dir)
                    await interaction.followup.send("❌ No metadata file (EHRR) found in the ZIP, and no screenshot provided.", ephemeral=True)

        except Exception as e:
            shutil.rmtree(temp_dir)
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)

    @app_commands.command(name="replace_screenshot", description="Replace the screenshot in a Toybox ZIP file.")

    @app_commands.describe(toybox_zip="Upload the Toybox ZIP file.", screenshot="Upload the new screenshot image (PNG/JPG).")
    async def replace_screenshot(self, interaction: discord.Interaction, toybox_zip: discord.Attachment, screenshot: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        
        if not toybox_zip.filename.endswith('.zip'):
            await interaction.followup.send("❌ Please upload a valid `.zip` file for the Toybox.", ephemeral=True)
            return
            
        if not (screenshot.filename.lower().endswith('.png') or screenshot.filename.lower().endswith('.jpg') or screenshot.filename.lower().endswith('.jpeg')):
            await interaction.followup.send("❌ Please upload a valid image file (.png, .jpg, .jpeg) for the screenshot.", ephemeral=True)
            return

        try:
            # Download files
            zip_data = await toybox_zip.read()
            image_data = await screenshot.read()
            
            # Process
            from services.image_injector_service import ImageInjectorService
            injector = ImageInjectorService()
            
            modified_zip_data, filename = injector.process_toybox(zip_data, image_data)
            
            # Send back
            file = discord.File(io.BytesIO(modified_zip_data), filename=filename)
            await interaction.followup.send(f"✅ Successfully replaced screenshot in `{toybox_zip.filename}`!", file=file, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ToyboxEditorCog(bot))