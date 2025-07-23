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
        # Font configuration with all available styles
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
                    self.logger.warning(f"Font file not found: {font_path}, using fallback")
                    # Use fallback to basic fonts if DejaVu not available
                    self.font_paths = {}
                    return
                
            self.fonts_loaded = True
            self.logger.info("Font files verified successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to verify fonts: {e}")
            self.fonts_loaded = False
            # Don't raise exception, just use fallback fonts

    def add_fonts_to_pdf(self, pdf: FPDF):
        """Add fonts to a PDF instance with fallback to system fonts"""
        try:
            if not self.fonts_loaded:
                # Use system fonts as fallback
                self.logger.info("Using system fonts as fallback")
                return
                
            for style, filename in self.font_paths.items():
                font_path = Path('static/fonts') / filename
                if font_path.exists():
                    pdf.add_font("DejaVu", style=style, fname=str(font_path))
                    self.logger.info(f"Added font: DejaVu {style} from {filename}")
                else:
                    self.logger.warning(f"Font file missing: {font_path}")
                    
        except Exception as e:
            self.logger.error(f"Failed to add fonts to PDF: {e}")
            # Continue without custom fonts - FPDF will use defaults

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
                self.logger.info(f"CSS class '.{element_class}' not found in template")
                return {}

            # Find the opening brace
            brace_start = self.css.find("{", start)
            if brace_start == -1:
                self.logger.error(f"No opening brace found for '.{element_class}'")
                return {}

            # Find the closing brace
            brace_end = self.css.find("}", brace_start)
            if brace_end == -1:
                self.logger.error(f"No closing brace found for '.{element_class}'")
                return {}

            # Extract the CSS rules
            css_rules = self.css[brace_start + 1:brace_end].strip()
            self.logger.info(f"CSS rules for '.{element_class}': {css_rules}")

            # Parse the CSS rules
            style_dict = {}
            for rule in css_rules.split(";"):
                rule = rule.strip()
                if not rule:
                    continue
                
                if ":" not in rule:
                    self.logger.warning(f"Invalid CSS rule: {rule}")
                    continue
                
                prop, value = rule.split(":", 1)
                prop = prop.strip()
                value = value.strip()
                
                self.logger.info(f"Parsing CSS property: {prop} = {value}")
                
                # Convert CSS properties to FPDF parameters
                if prop == "font-family":
                    style_dict["font_family"] = value.replace('"', '')
                elif prop == "font-size":
                    if value.endswith("pt"):
                        style_dict["font_size"] = int(float(value.replace("pt", "")))
                    else:
                        style_dict["font_size"] = 12  # Default
                elif prop == "font-weight":
                    if value == "bold":
                        style_dict["font_style"] = "B"
                elif prop == "font-style":
                    if value == "italic":
                        style_dict["font_style"] = "I"
                elif prop == "text-align":
                    if value == "center":
                        style_dict["align"] = "C"
                    elif value == "right":
                        style_dict["align"] = "R"
                    else:
                        style_dict["align"] = "L"
                elif prop == "color":
                    # Convert hex color to RGB
                    if value.startswith("#"):
                        hex_color = value[1:]
                        if len(hex_color) == 6:
                            r = int(hex_color[0:2], 16)
                            g = int(hex_color[2:4], 16)
                            b = int(hex_color[4:6], 16)
                            style_dict["text_color"] = (r, g, b)
                elif prop == "margin-bottom":
                    style_dict["margin_bottom"] = float(value.replace("pt", ""))
                    self.logger.info(f"SET margin_bottom to: {style_dict['margin_bottom']}")
                elif prop == "margin-top":
                    style_dict["margin_top"] = float(value.replace("pt", ""))
                elif prop == "line-height":
                    # Convert line-height to FPDF line height
                    if value.endswith("pt"):
                        style_dict["line_height"] = float(value.replace("pt", ""))
                    elif value.replace(".", "").isdigit():
                        # Numeric multiplier (e.g., 1.5)
                        style_dict["line_height"] = float(value) * 6  # Assume 6pt base
                    else:
                        style_dict["line_height"] = 6  # Default
                elif prop == "width":
                    if value.endswith("pt"):
                        style_dict["width"] = float(value.replace("pt", ""))
                    elif value.endswith("%"):
                        style_dict["width_percent"] = float(value.replace("%", ""))
                elif prop == "height":
                    if value.endswith("pt"):
                        style_dict["height"] = float(value.replace("pt", ""))
                    elif value.endswith("%"):
                        style_dict["height_percent"] = float(value.replace("%", ""))
                elif prop == "max-width":
                    if value.endswith("pt"):
                        style_dict["max_width"] = float(value.replace("pt", ""))
                elif prop == "max-height":
                    if value.endswith("pt"):
                        style_dict["max_height"] = float(value.replace("pt", ""))
                elif prop == "crop-top":
                    if value.endswith("pt"):
                        style_dict["crop_top"] = float(value.replace("pt", ""))
                    else:
                        style_dict["crop_top"] = 0.0
                elif prop == "crop-bottom":
                    if value.endswith("pt"):
                        style_dict["crop_bottom"] = float(value.replace("pt", ""))
                    else:
                        style_dict["crop_bottom"] = 0.0
            
            self.logger.info(f"Final style dict for '.{element_class}': {style_dict}")
            return style_dict
            
        except Exception as e:
            self.logger.error(f"Error parsing CSS for '.{element_class}': {str(e)}")
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