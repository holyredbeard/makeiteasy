import os
from pathlib import Path
import logging
from datetime import datetime
from fpdf import FPDF
from typing import Dict, Literal, Union

# Define font style type
FontStyle = Literal['', 'B', 'I', 'BI']

class PDFStyleManager:
    def __init__(self, template_name="default"):
        self.template_name = template_name
        self.template_dir = Path("static/templates/pdf")
        self.logger = logging.getLogger(__name__)
        self.fonts_loaded = False
        self.font_paths: Dict[FontStyle, str] = {
            '': 'DejaVuSans.ttf',
            'B': 'DejaVuSans-Bold.ttf',
            'I': 'DejaVuSans-Oblique.ttf',
            'BI': 'DejaVuSans-BoldOblique.ttf'
        }
        self._load_template()
        self._verify_fonts()

    def _verify_fonts(self):
        """Verify that all required font files exist"""
        try:
            # Verify font files exist
            for style, filename in self.font_paths.items():
                font_path = Path('static/fonts') / filename
                if not font_path.exists():
                    raise FileNotFoundError(f"Font file not found: {font_path}")
                
            self.fonts_loaded = True
            self.logger.info("All font files verified successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to verify fonts: {e}")
            self.fonts_loaded = False
            raise

    def add_fonts_to_pdf(self, pdf: FPDF):
        """Add DejaVu fonts to a PDF instance"""
        try:
            for style, filename in self.font_paths.items():
                font_path = Path('static/fonts') / filename
                pdf.add_font("DejaVu", style=style, fname=str(font_path))
                self.logger.info(f"Added font: DejaVu {style} from {filename}")
        except Exception as e:
            self.logger.error(f"Failed to add fonts to PDF: {e}")
            raise

    def _load_template(self):
        """Load CSS template from file"""
        template_path = self.template_dir / f"{self.template_name}.css"
        try:
            with open(template_path, 'r') as f:
                self.css = f.read()
            self.logger.info(f"Loaded template: {template_path}")
        except Exception as e:
            self.logger.error(f"Failed to load template {template_path}: {e}")
            # Fall back to default template
            if self.template_name != "default":
                self.template_name = "default"
                self._load_template()

    def get_style(self, element_class):
        """Extract style properties for a specific CSS class"""
        try:
            # Find the class definition in CSS
            start = self.css.find(f".{element_class}")
            if start == -1:
                return {}

            # Find the opening brace
            brace_start = self.css.find("{", start)
            if brace_start == -1:
                return {}

            # Find the closing brace
            brace_end = self.css.find("}", brace_start)
            if brace_end == -1:
                return {}

            # Extract and parse the style rules
            style_block = self.css[brace_start + 1:brace_end].strip()
            style_dict = {}
            
            # FPDF alignment map
            align_map = {
                'left': 'L',
                'right': 'R',
                'center': 'C',
                'justify': 'J'
            }
            
            for rule in style_block.split(";"):
                rule = rule.strip()
                if not rule or ":" not in rule:
                    continue
                    
                prop, value = [x.strip() for x in rule.split(":", 1)]
                # Convert CSS properties to FPDF parameters
                if prop == "font-family":
                    # Always use DejaVu Sans as the font family for Unicode support
                    style_dict["font_family"] = "DejaVu"
                elif prop == "font-size":
                    style_dict["font_size"] = int(value.replace("pt", ""))
                elif prop == "font-weight":
                    style_dict["font_style"] = "B" if value == "bold" else ""
                elif prop == "font-style":
                    if value == "italic":
                        if style_dict.get("font_style") == "B":
                            style_dict["font_style"] = "BI"
                        else:
                            style_dict["font_style"] = "I"
                elif prop == "text-align":
                    style_dict["align"] = align_map.get(value.lower(), 'L')
                elif prop == "color":
                    # Handle hex colors
                    if value.startswith("#"):
                        value = value[1:]
                        style_dict["text_color"] = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
                    # Handle rgb colors
                    elif value.startswith("rgb"):
                        colors = value.strip("rgb()").split(",")
                        style_dict["text_color"] = tuple(int(c.strip()) for c in colors)
                elif prop == "margin-bottom":
                    style_dict["margin_bottom"] = float(value.replace("pt", ""))
                elif prop == "margin-top":
                    style_dict["margin_top"] = float(value.replace("pt", ""))

            return style_dict
            
        except Exception as e:
            self.logger.error(f"Error parsing style for {element_class}: {e}")
            return {}

    def get_page_settings(self):
        """Extract page settings from CSS @page rule"""
        try:
            start = self.css.find("@page")
            if start == -1:
                return {}

            brace_start = self.css.find("{", start)
            brace_end = self.css.find("}", brace_start)
            
            if brace_start == -1 or brace_end == -1:
                return {}

            settings_block = self.css[brace_start + 1:brace_end].strip()
            settings = {}
            
            for rule in settings_block.split(";"):
                rule = rule.strip()
                if not rule:
                    continue
                    
                prop, value = [x.strip() for x in rule.split(":", 1)]
                if prop == "margin":
                    settings["margin"] = float(value.replace("cm", "")) * 10  # Convert to mm
                elif prop == "size":
                    settings["format"] = value.upper()

            return settings
            
        except Exception as e:
            self.logger.error(f"Error parsing page settings: {e}")
            return {} 