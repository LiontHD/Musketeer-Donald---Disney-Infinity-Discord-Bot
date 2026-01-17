import discord
from discord import ui
import re
import io
import os
import zipfile
import asyncio
import shutil
import traceback
from typing import List, Dict, Any

from services.file_parser import (
    analyze_and_parse_toybox_file, 
    TEXT_PATTERN, 
    AUTHOREDNAME_PATTERN, 
    AUTHOREDDESC_PATTERN
)

class MetadataEditorModal(ui.Modal, title="Edit Toybox Metadata"):
    def __init__(self, main_view: 'ToyboxEditView'):
        super().__init__(timeout=1200)
        self.main_view = main_view
        
        full_text = "\n".join(self.main_view.file_lines)

        current_name_match = AUTHOREDNAME_PATTERN.search(full_text)
        current_desc_match = AUTHOREDDESC_PATTERN.search(full_text)
        
        current_name = current_name_match.group(1) if current_name_match else ""
        current_desc = current_desc_match.group(1) if current_desc_match else ""

        self.name_input = ui.TextInput(
            label="Toybox Name (AUTHOREDNAME)",
            default=current_name,
            max_length=128,
            style=discord.TextStyle.short
        )
        self.add_item(self.name_input)

        self.desc_input = ui.TextInput(
            label="Toybox Description (AUTHOREDDESC)",
            default=current_desc,
            max_length=4000,
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.add_item(self.desc_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value
        new_desc = self.desc_input.value
        
        escaped_name = new_name.replace('"', '""')
        escaped_desc = new_desc.replace('"', '""')

        full_text = "\n".join(self.main_view.file_lines)
        
        full_text = AUTHOREDNAME_PATTERN.sub(f'AUTHOREDNAME = "{escaped_name}"', full_text, 1)
        full_text = AUTHOREDDESC_PATTERN.sub(f'AUTHOREDDESC = "{escaped_desc}"', full_text, 1)

        self.main_view.file_lines = full_text.splitlines()
        self.main_view.mark_as_edited('Metadata', 1)
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

        self.page = 0
        self.items_per_page = 25
        self.total_pages = (len(self.toys) + self.items_per_page - 1) // self.items_per_page

        self.update_components()

    def update_components(self):
        self.clear_items()
        self.add_item(self.create_toy_select())
        if self.total_pages > 1:
            self.add_item(self.create_previous_button())
            self.add_item(self.create_next_button())
        self.add_item(self.create_finish_button())
        self.add_item(self.create_cancel_button())

    def create_toy_select(self) -> ui.Select:
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        current_toys = self.toys[start_index:end_index]

        options = []
        for t in current_toys:
            emoji = "❓"
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
            await interaction.response.defer()

    async def on_next_page(self, interaction: discord.Interaction):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_components()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

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
            srr_path = selected_srr['path']
            txt_path = os.path.join(self.files_root, f"{selected_srr['name']}.txt")
            proc = await asyncio.create_subprocess_exec(
                'python3', self.script_path, '-d', srr_path, txt_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise Exception(f"Decompression failed: {stderr.decode()}")
            with open(txt_path, 'rb') as f:
                parsed_data = analyze_and_parse_toybox_file(f.read())
            if not parsed_data['toys']:
                await interaction.followup.send("❌ No editable toys found in the selected SRR file.", ephemeral=True)
                return
            context = {
                'temp_dir': self.temp_dir,
                'files_root': self.files_root,
                'original_zip_name': self.original_zip_name,
                'srr_path': srr_path,
                'txt_path': txt_path,
                'script_path': self.script_path
            }
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
                'srr_path': ehrr_path,
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
