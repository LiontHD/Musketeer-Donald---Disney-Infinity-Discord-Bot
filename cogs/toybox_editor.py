import discord
from discord.ext import commands
from discord import app_commands, ui
import re
import io
import os
import tempfile
import zipfile
import asyncio
import shutil
import traceback
from typing import List, Dict, Any

# Regex-Muster zum Extrahieren von Text innerhalb von Anführungszeichen
TEXT_PATTERN = re.compile(r'"([^"]*)"')
SRR_FILE_PATTERN = re.compile(r'^SRR\d+[A-Z]?$')

EHRR_FILE_PATTERN = re.compile(r'^EHRR\d+[A-Z]?$')
AUTHOREDNAME_PATTERN = re.compile(r'AUTHOREDNAME\s*=\s*"([^"]*)"')
AUTHOREDDESC_PATTERN = re.compile(r'AUTHOREDDESC\s*=\s*"([^"]*)"')

def analyze_and_parse_toybox_file(file_content: bytes) -> Dict[str, Any]:
    try:
        # Versuche zuerst, mit UTF-8 zu dekodieren
        lines = file_content.decode('utf-8').splitlines()
    except UnicodeDecodeError:
        # Wenn das fehlschlägt, nutze latin-1 als Fallback
        lines = file_content.decode('latin-1').splitlines()

    # KORREKTUR: Erstelle 'full_text' NACH dem try-except-Block.
    # So ist sichergestellt, dass 'lines' immer existiert und 'full_text'
    # immer definiert wird, bevor es verwendet wird.
    full_text = "\n".join(lines)
    
    toys, tc_count, cm_count, it_count, i = [], 0, 0, 0, 0

    # Suche nach EHRR-Metadaten
    name_match = AUTHOREDNAME_PATTERN.search(full_text)
    desc_match = AUTHOREDDESC_PATTERN.search(full_text)
    if name_match and desc_match:
        # Füge einen neuen "Toy"-Typ für Metadaten hinzu
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




# --- NEU: Ein eigenes Modal für die Bearbeitung von Name und Beschreibung ---
class MetadataEditorModal(ui.Modal, title="Edit Toybox Metadata"):
    def __init__(self, main_view: 'ToyboxEditView'):
        super().__init__(timeout=1200)
        self.main_view = main_view
        
        # Den aktuellen Inhalt der Datei als String holen
        full_text = "\n".join(self.main_view.file_lines)

        # Aktuellen Namen und Beschreibung extrahieren und als Standardwert setzen
        current_name_match = AUTHOREDNAME_PATTERN.search(full_text)
        current_desc_match = AUTHOREDDESC_PATTERN.search(full_text)
        
        current_name = current_name_match.group(1) if current_name_match else ""
        current_desc = current_desc_match.group(1) if current_desc_match else ""

        # UI-Elemente für das Modal hinzufügen
        self.name_input = ui.TextInput(
            label="Toybox Name (AUTHOREDNAME)",
            default=current_name,
            max_length=128, # Ein großzügiges Limit für den Titel
            style=discord.TextStyle.short
        )
        self.add_item(self.name_input)

        self.desc_input = ui.TextInput(
            label="Toybox Description (AUTHOREDDESC)",
            default=current_desc,
            max_length=4000, # Das maximale Limit für "paragraph" style in Modals
            style=discord.TextStyle.paragraph,
            required=False # Beschreibung kann leer sein
        )
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Neue Werte aus dem Modal holen
        new_name = self.name_input.value
        new_desc = self.desc_input.value
        
        # Anführungszeichen im Text escapen
        escaped_name = new_name.replace('"', '""')
        escaped_desc = new_desc.replace('"', '""')

        # Den gesamten Dateiinhalt als einen String behandeln
        full_text = "\n".join(self.main_view.file_lines)
        
        # Ersetze Name und Beschreibung mit den neuen Werten
        full_text = AUTHOREDNAME_PATTERN.sub(f'AUTHOREDNAME = "{escaped_name}"', full_text, 1)
        full_text = AUTHOREDDESC_PATTERN.sub(f'AUTHOREDDESC = "{escaped_desc}"', full_text, 1)

        # Aktualisiere die Zeilen in der Hauptansicht
        self.main_view.file_lines = full_text.splitlines()

        # Markiere das Element als bearbeitet
        self.main_view.mark_as_edited('Metadata', 1)

        # Sende die aktualisierte Hauptansicht zurück an Discord
        await interaction.response.edit_message(embed=self.main_view.create_embed(), view=self.main_view)




class TextEditorModal(ui.Modal):
    def __init__(self, toy_data: Dict[str, Any], parent_view: ui.View, line_range: range = None):
        self.toy_data, self.parent_view = toy_data, parent_view
        self.main_view = parent_view if isinstance(parent_view, ToyboxEditView) else parent_view.main_view
        title_suffix = f" (Lines {line_range.start}-{line_range.stop - 1})" if line_range else ""
        super().__init__(title=f"Edit {toy_data['type']} #{toy_data['id']}{title_suffix}", timeout=1200)
        self._populate_fields(line_range)
    def _populate_fields(self, line_range: range):
        if self.toy_data['type'] == 'Text Creator' and line_range:
            for j in line_range:
                line_index = self.toy_data['line_indices'][f'line_{j}']
                current_text = TEXT_PATTERN.search(self.main_view.file_lines[line_index]).group(1)
                self.add_item(ui.TextInput(label=f"Line {j}", custom_id=f"line_{j}", default=current_text if not current_text.startswith('@AR_') else "", required=False, max_length=256, style=discord.TextStyle.paragraph))
        elif self.toy_data['type'] == 'Challenge Maker':
            for key in ["title", "description"]:
                line_index = self.toy_data['line_indices'][key]
                current_text = TEXT_PATTERN.search(self.main_view.file_lines[line_index]).group(1)
                self.add_item(ui.TextInput(label=key.capitalize(), custom_id=key, default=current_text if not current_text.startswith('@AR_') else "", max_length=512 if key == "description" else 256, style=discord.TextStyle.paragraph if key == "description" else discord.TextStyle.short))
        elif self.toy_data['type'] == 'Input Toy':
            line_index = self.toy_data['line_indices']['prompt']
            current_text = TEXT_PATTERN.search(self.main_view.file_lines[line_index]).group(1)
            self.add_item(ui.TextInput(label="Prompt Text", custom_id="prompt", default=current_text if not current_text.startswith('@AR_') else "", max_length=256))
    async def on_submit(self, interaction: discord.Interaction):
        for component in self.children:
            new_text = component.value
            if new_text or new_text == "":
                line_key = component.custom_id
                line_index = self.toy_data['line_indices'][line_key]
                escaped_new_text = new_text.replace('"', '""') if new_text else ""
                original_line = self.main_view.file_lines[line_index]
                self.main_view.file_lines[line_index] = re.sub(TEXT_PATTERN, f'"{escaped_new_text}"', original_line, 1)
        self.main_view.mark_as_edited(self.toy_data['type'], self.toy_data['id'])
        if isinstance(self.parent_view, TextCreatorPartSelectView):
            await interaction.response.edit_message(embed=self.parent_view.create_embed(), view=self.parent_view)
        else:
            await interaction.response.edit_message(embed=self.main_view.create_embed(), view=self.main_view)

class TextCreatorPartSelectView(ui.View):
    def __init__(self, toy_data: Dict[str, Any], main_view: 'ToyboxEditView'):
        super().__init__(timeout=1800)
        self.toy_data = toy_data
        self.main_view = main_view
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"✍️ Editing Text Creator #{self.toy_data['id']}", description="Here are the current texts for all 10 lines. Click a button to edit a group of lines.", color=discord.Color.blue())
        lines_text = []
        for i in range(1, 11):
            line_index = self.toy_data['line_indices'][f'line_{i}']
            current_text = TEXT_PATTERN.search(self.main_view.file_lines[line_index]).group(1)
            display_text = f'`{current_text}`' if not current_text.startswith("@AR_") else "*(Placeholder)*"
            lines_text.append(f"**Line {i}:** {display_text}")
        embed.add_field(name="Current Lines", value="\n".join(lines_text), inline=False)
        return embed
    @ui.button(label="Edit Lines 1-5", style=discord.ButtonStyle.primary)
    async def edit_part_1(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(TextEditorModal(self.toy_data, self, line_range=range(1, 6)))
    @ui.button(label="Edit Lines 6-10", style=discord.ButtonStyle.primary)
    async def edit_part_2(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(TextEditorModal(self.toy_data, self, line_range=range(6, 11)))
    @ui.button(label="Back to Main Menu", style=discord.ButtonStyle.grey, emoji="↩️", row=2)
    async def go_back(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.edit_message(embed=self.main_view.create_embed(), view=self.main_view); self.stop()

class SRRFileSelectView(ui.View):
    def __init__(self, srr_files: List[Dict[str, str]], temp_dir: str, files_root: str, original_zip_name: str, script_path: str):
        super().__init__(timeout=1800)
        self.srr_files = srr_files
        self.temp_dir = temp_dir
        self.files_root = files_root
        self.original_zip_name = original_zip_name
        self.script_path = script_path
        self.add_item(self.create_srr_select())
        self.add_item(self.create_cancel_button())
    
    def create_srr_select(self) -> ui.Select:
        options = []
        for i, srr_file in enumerate(self.srr_files):
            toy_count = srr_file.get('toy_count', 0)
            description = f"{toy_count} toys found" if toy_count > 0 else "No toys found"
            options.append(discord.SelectOption(
                label=srr_file['name'],
                value=str(i),
                description=description,
                emoji="📁"
            ))
        
        select = ui.Select(placeholder="Select an SRR file to edit...", options=options, custom_id="srr_select")
        select.callback = self.on_srr_select
        return select
    
    def create_cancel_button(self) -> ui.Button:
        button = ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌", custom_id="cancel_srr_select")
        button.callback = self.on_cancel
        return button
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Multiple SRR Files Found",
            description="I found multiple SRR files in your ZIP. Please select which one you want to edit:",
            color=discord.Color.blue()
        )
        
        srr_list = []
        for srr_file in self.srr_files:
            toy_count = srr_file.get('toy_count', 0)
            status = f"✅ {toy_count} toys" if toy_count > 0 else "❌ No toys"
            srr_list.append(f"📁 **{srr_file['name']}** - {status}")
        
        embed.add_field(name="Available SRR Files", value="\n".join(srr_list), inline=False)
        embed.set_footer(text="Select a file from the dropdown below")
        return embed
    
    async def on_srr_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        selected_index = int(interaction.data['values'][0])
        selected_srr = self.srr_files[selected_index]
        
        try:
            # Process the selected SRR file
            srr_path = selected_srr['path']
            txt_path = os.path.join(self.files_root, f"{selected_srr['name']}.txt")
            
            # Decompress the selected SRR file
            proc = await asyncio.create_subprocess_exec(
                'python3', self.script_path, '-d', srr_path, txt_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"Decompression failed: {stderr.decode()}")
            
            # Parse the decompressed file
            with open(txt_path, 'rb') as f:
                parsed_data = analyze_and_parse_toybox_file(f.read())
            
            if not parsed_data['toys']:
                await interaction.followup.send("❌ No editable toys found in the selected SRR file.", ephemeral=True)
                return
            
            # Create context for the editor
            context = {
                'temp_dir': self.temp_dir,
                'files_root': self.files_root,
                'original_zip_name': self.original_zip_name,
                'srr_path': srr_path,
                'txt_path': txt_path,
                'script_path': self.script_path
            }
            
            # Create and show the editor view
            view = ToyboxEditView(parsed_data, selected_srr['name'], 'zip', context)
            await interaction.edit_original_response(embed=view.create_embed(), view=view)
            self.stop()
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)
    
    async def on_cancel(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            embed=discord.Embed(title="❌ Cancelled", description="SRR file selection cancelled.", color=discord.Color.red()),
            view=self
        )
        self.cleanup()
    
    async def on_timeout(self) -> None:
        self.cleanup()
    
    def cleanup(self):
        self.stop()
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                print(f"Error cleaning up temp directory: {e}")

# In toybox_editor.py

class ToyboxEditView(ui.View):
    def __init__(self, parsed_data: Dict[str, Any], original_filename: str, mode: str, context: Dict = None):
        super().__init__(timeout=1800)
        self.file_lines = parsed_data['lines']
        self.original_filename = original_filename
        self.toys = parsed_data['toys']
        self.edited_toys = set()
        self.mode = mode
        self.context = context if context else {}
        
        sort_order = {"Metadata": -1, "Text Creator": 0, "Challenge Maker": 1, "Input Toy": 2}
        self.toys.sort(key=lambda t: (sort_order.get(t['type'], 99), t['id']))

        # --- NEU: Paginierungs-Logik ---
        self.page = 0
        self.items_per_page = 25  # Discord's Limit für Select-Optionen
        self.total_pages = (len(self.toys) + self.items_per_page - 1) // self.items_per_page

        self.update_components()

    def update_components(self):
        """Entfernt alle Komponenten und baut sie basierend auf der aktuellen Seite neu auf."""
        self.clear_items()
        
        # Füge das Dropdown-Menü für die aktuelle Seite hinzu
        self.add_item(self.create_toy_select())
        
        # Füge Paginierungs-Buttons hinzu, falls mehr als eine Seite existiert
        if self.total_pages > 1:
            self.add_item(self.create_previous_button())
            self.add_item(self.create_next_button())

        # Füge die Haupt-Aktionsbuttons hinzu
        self.add_item(self.create_finish_button())
        self.add_item(self.create_cancel_button())

    def create_toy_select(self) -> ui.Select:
        """Erstellt das Dropdown-Menü nur für die Toys auf der aktuellen Seite."""
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        
        current_toys = self.toys[start_index:end_index]

        options = []
        for t in current_toys:
            emoji = "❓" # Default
            # --- MODIFIZIERT: Emoji für den neuen Typ hinzufügen ---
            if t['type'] == 'Text Creator': emoji = "✍️"
            elif t['type'] == 'Challenge Maker': emoji = "🏆"
            elif t['type'] == 'Input Toy': emoji = "💬"
            elif t['type'] == 'Metadata': emoji = "📝"
            
            options.append(discord.SelectOption(
                label=f"{t['type']} #{t['id']}" if t['type'] != 'Metadata' else "Toybox Name & Description",
                value=f"{t['type']}_{t['id']}", 
                emoji=emoji,
                description=f"Click to edit this item"
            ))
        
        placeholder = f"Select an item (Page {self.page + 1}/{self.total_pages})..."
        select = ui.Select(placeholder=placeholder, options=options, custom_id="toy_select_final_v2")
        select.callback = self.on_toy_select
        return select

    # --- NEU: Buttons für die Paginierung ---
    def create_previous_button(self) -> ui.Button:
        button = ui.Button(label="Previous Page", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev_page_final_v2", row=1)
        button.disabled = self.page == 0
        button.callback = self.on_previous_page
        return button

    def create_next_button(self) -> ui.Button:
        button = ui.Button(label="Next Page", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next_page_final_v2", row=1)
        button.disabled = self.page >= self.total_pages - 1
        button.callback = self.on_next_page
        return button

    async def on_previous_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_components()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer() # Button sollte bereits deaktiviert sein, aber sicher ist sicher

    async def on_next_page(self, interaction: discord.Interaction):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_components()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    # --- Bestehende Button-Erstellungs-Methoden ---
    def create_finish_button(self) -> ui.Button:
        button = ui.Button(label="Finish & Download", style=discord.ButtonStyle.green, emoji="✅", custom_id="finish_edit_final_v2", row=2)
        button.callback = self.on_finish
        return button

    def create_cancel_button(self) -> ui.Button:
        button = ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌", custom_id="cancel_edit_final_v2", row=2)
        button.callback = self.on_cancel
        return button

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Toybox Text Editor", description="I've analyzed your file. Use the dropdown to edit an item.\n", color=discord.Color.gold())
        
        # Anzeige der Toys für die aktuelle Seite
        start_index = self.page * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(self.toys))
        
        toys_list_str = []
        if not self.toys: 
            toys_list_str.append("No editable toys found.")
        else:
            for i in range(start_index, end_index):
                t = self.toys[i]
                toy_type, toy_id = t['type'], t['id']
                is_edited_key = f"{toy_type}_{toy_id}"
                is_edited = is_edited_key in self.edited_toys
                status_emoji = "✅" if is_edited else "▫️"
                emoji = "❓"
                display_name = f"{toy_type} #{toy_id}"
                if toy_type == 'Text Creator': emoji = "✍️"
                elif toy_type == 'Challenge Maker': emoji = "🏆"
                elif toy_type == 'Input Toy': emoji = "💬"
                elif toy_type == 'Metadata':
                    emoji = "📝"
                    display_name = "Toybox Name & Description"
                
                toys_list_str.append(f"{status_emoji} {emoji} {display_name}")

        embed.add_field(name=f"Editable Items (Page {self.page + 1}/{self.total_pages})", value="\n".join(toys_list_str), inline=False)
        embed.set_footer(text=f"Editing: {self.original_filename} | Total Items: {len(self.toys)} | ✅ = Edited")
        return embed

    def mark_as_edited(self, toy_type: str, toy_id: int): 
        self.edited_toys.add(f"{toy_type}_{toy_id}")

    async def on_toy_select(self, interaction: discord.Interaction):
        selected_type, selected_id = interaction.data['values'][0].split('_')
        selected_id = int(selected_id)
        toy_to_edit = next((t for t in self.toys if t['type'] == selected_type and t['id'] == selected_id), None)
        if toy_to_edit:
            if toy_to_edit['type'] == 'Text Creator':
                view = TextCreatorPartSelectView(toy_to_edit, self)
                await interaction.response.edit_message(embed=view.create_embed(), view=view)
            # --- NEU: Fall für Metadaten-Bearbeitung ---
            elif toy_to_edit['type'] == 'Metadata':
                await interaction.response.send_modal(MetadataEditorModal(self))
            else: 
                await interaction.response.send_modal(TextEditorModal(toy_to_edit, self))

    async def on_finish(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            final_file = None
            if self.mode == 'txt':
                final_content = "\n".join(self.file_lines).encode('utf-8')
                final_file = discord.File(io.BytesIO(final_content), filename=f"edited_{self.original_filename}")
            elif self.mode == 'zip':
                with open(self.context['txt_path'], 'w', encoding='utf-8') as f:
                    f.write("\n".join(self.file_lines))
                proc = await asyncio.create_subprocess_exec('python3', self.context['script_path'], '-c', self.context['txt_path'], self.context['srr_path'], self.context['srr_path'], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                _, stderr = await proc.communicate()
                if proc.returncode != 0: 
                    raise Exception(f"Compression failed: {stderr.decode()}")
                
                os.remove(self.context['txt_path'])

                new_zip_path = os.path.join(self.context['temp_dir'], f"edited_{self.context['original_zip_name']}")
                with zipfile.ZipFile(new_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(self.context['files_root']):
                        for file in files:
                            zf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), self.context['files_root']))
                final_file = discord.File(new_zip_path, filename=os.path.basename(new_zip_path))
            
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(embed=discord.Embed(title="✅ Finished", description=f"Your file `{self.original_filename}` has been processed.", color=discord.Color.green()), view=self)
            await interaction.followup.send("✅ Here is your edited file!", file=final_file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred during final processing: {e}", ephemeral=True)
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
        finally:
            self.cleanup()

    async def on_cancel(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(title="❌ Cancelled", description="The editing session has been cancelled.", color=discord.Color.red()), view=self)
        self.cleanup()

    async def on_timeout(self) -> None:
        self.cleanup()

    def cleanup(self):
        self.stop()
        if self.mode == 'zip' and self.context.get('temp_dir') and os.path.exists(self.context.get('temp_dir')):
            try:
                shutil.rmtree(self.context['temp_dir'])
            except Exception as e:
                print(f"Error cleaning up temp directory: {e}")

class EHRRFileSelectView(ui.View):
    def __init__(self, ehrr_files: List[Dict[str, str]], temp_dir: str, files_root: str, original_zip_name: str, script_path: str):
        super().__init__(timeout=1800)
        self.ehrr_files = ehrr_files
        self.temp_dir = temp_dir
        self.files_root = files_root
        self.original_zip_name = original_zip_name
        self.script_path = script_path
        self.add_item(self.create_ehrr_select())
        self.add_item(self.create_cancel_button())
    
    def create_ehrr_select(self) -> ui.Select:
        options = [
            discord.SelectOption(
                label=ehrr_file['name'],
                value=str(i),
                description="Contains Toybox Name & Description",
                emoji="📁"
            ) for i, ehrr_file in enumerate(self.ehrr_files)
        ]
        
        select = ui.Select(placeholder="Select an EHRR file to edit...", options=options, custom_id="ehrr_select")
        select.callback = self.on_ehrr_select
        return select
    
    def create_cancel_button(self) -> ui.Button:
        button = ui.Button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌", custom_id="cancel_ehrr_select")
        button.callback = self.on_cancel
        return button
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="Multiple EHRR Files Found",
            description="I found multiple EHRR files in your ZIP. Please select which one you want to edit:",
            color=discord.Color.blue()
        )
        ehrr_list = [f"📁 **{f['name']}**" for f in self.ehrr_files]
        embed.add_field(name="Available EHRR Files", value="\n".join(ehrr_list), inline=False)
        embed.set_footer(text="Select a file from the dropdown below")
        return embed
    
    async def on_ehrr_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_index = int(interaction.data['values'][0])
        selected_ehrr = self.ehrr_files[selected_index]
        try:
            ehrr_path = selected_ehrr['path']
            # Wichtig: EHRR-Dateien werden oft als .txt dekomprimiert, um lesbar zu sein
            txt_path = os.path.join(self.files_root, f"{selected_ehrr['name']}.txt")
            
            proc = await asyncio.create_subprocess_exec(
                'python3', self.script_path, '-d', ehrr_path, txt_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"Decompression failed: {stderr.decode()}")
            
            with open(txt_path, 'rb') as f:
                parsed_data = analyze_and_parse_toybox_file(f.read())
            
            if not parsed_data['toys']:
                await interaction.followup.send("❌ No editable metadata found in the selected EHRR file.", ephemeral=True)
                return
            
            context = {
                'temp_dir': self.temp_dir,
                'files_root': self.files_root,
                'original_zip_name': self.original_zip_name,
                'srr_path': ehrr_path, # Benennen wir es konsistent, auch wenn es ein EHRR ist
                'txt_path': txt_path,
                'script_path': self.script_path
            }
            view = ToyboxEditView(parsed_data, selected_ehrr['name'], 'zip', context)
            await interaction.edit_original_response(embed=view.create_embed(), view=view)
            self.stop()
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)
    
    async def on_cancel(self, interaction: discord.Interaction):
        for item in self.children: item.disabled = True
        await interaction.response.edit_message(embed=discord.Embed(title="❌ Cancelled", color=discord.Color.red()), view=self)
        self.cleanup()
    
    async def on_timeout(self) -> None: self.cleanup()
    
    def cleanup(self):
        self.stop()
        if os.path.exists(self.temp_dir):
            try: shutil.rmtree(self.temp_dir)
            except Exception as e: print(f"Error cleaning up temp directory: {e}")


class ToyboxEditorCog(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @app_commands.command(name="edit_toybox_text", description="Interactively edit texts in a Toybox .txt file.")
    @app_commands.describe(file="Upload the .txt file you want to edit (e.g., SRR2A.txt)")
    async def edit_toybox_text(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not file.filename.endswith('.txt'): await interaction.followup.send("❌ Please upload a valid `.txt` file.", ephemeral=True); return
        try:
            parsed_data = analyze_and_parse_toybox_file(await file.read())
            if not parsed_data['toys']: await interaction.followup.send("I couldn't find any editable toys in this file.", ephemeral=True); return
            view = ToyboxEditView(parsed_data, file.filename, mode='txt')
            await interaction.followup.send(embed=view.create_embed(), view=view)
        except Exception as e: await interaction.followup.send(f"An unexpected error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)

    @app_commands.command(name="edit_toybox_zip", description="Seamlessly edit texts in a Toybox ZIP file.")
    @app_commands.describe(zip_file="Upload the Toybox ZIP file.")
    async def edit_toybox_zip(self, interaction: discord.Interaction, zip_file: discord.Attachment):
        await interaction.response.defer(ephemeral=True)
        if not zip_file.filename.endswith('.zip'): await interaction.followup.send("❌ Please upload a valid `.zip` file.", ephemeral=True); return
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


    # --- NEU: Der Befehl zum Bearbeiten von Name und Beschreibung ---
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
            
            # Finde alle EHRR-Dateien
            ehrr_files = []
            files_root = None
            for root, _, files in os.walk(extract_folder):
                for file in files:
                    # Wir verwenden hier das neue EHRR_FILE_PATTERN
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

            # Wenn nur eine EHRR-Datei vorhanden ist, direkt bearbeiten
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
                    'srr_path': ehrr_path, # Wiederverwendung des Schlüssels
                    'txt_path': txt_path,
                    'script_path': script_path
                }
                view = ToyboxEditView(parsed_data, ehrr_file['name'], 'zip', context)
                await interaction.followup.send(embed=view.create_embed(), view=view)
            else:
                # Bei mehreren EHRR-Dateien, lass den Benutzer wählen
                view = EHRRFileSelectView(ehrr_files, temp_dir, files_root, zip_file.filename, script_path)
                await interaction.followup.send(embed=view.create_embed(), view=view)
                
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            await interaction.followup.send(f"❌ An error occurred: {e}\n```py\n{traceback.format_exc()}\n```", ephemeral=True)


async def setup(bot): await bot.add_cog(ToyboxEditorCog(bot))