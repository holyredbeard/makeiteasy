from fpdf import FPDF
from typing import List, Optional
import os
from models.types import Recipe, Step
import logging
import traceback
from datetime import datetime
from pathlib import Path
from .pdf_styles import PDFStyleManager
from PIL import Image

# Ensure output directory exists
output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

# Configure logging with more detailed format
log_file = output_dir / "pdf_debug.log"
try:
    # Test write to log file
    with open(log_file, 'a') as f:
        f.write(f"\n--- PDF Generator Started {datetime.now().isoformat()} ---\n")
except Exception as e:
    print(f"Warning: Could not write to log file: {e}")
    # Fallback to just console logging if file is not writable
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[logging.StreamHandler()]
    )
else:
    # Configure file handler
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [pdf] %(message)s',
        datefmt='%H:%M:%S'
    ))
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    
    # Configure logger
    logger = logging.getLogger('pdf_generator')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False  # Prevent duplicate logs

logger = logging.getLogger('pdf_generator')
logger.info("PDF Generator initialized")

def log_pdf_step(step: str, message: str, error: bool = False, job_id: Optional[str] = None):
    """Helper function for consistent PDF logging"""
    try:
        job_info = f"[Job {job_id}] " if job_id else ""
        step_info = f"[{step}] "
        log_message = f"{job_info}{step_info}{message}"
        
        # Write directly to log file
        log_file = Path("output/pdf_debug.log")
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{'ERROR' if error else 'INFO'}] [pdf] {log_message}\n"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry)
            f.flush()  # Force write to disk
            os.fsync(f.fileno())  # Ensure it's written to disk
        
        # Also log through logging system
        if error:
            logger.error(log_message)
            logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.info(log_message)
            
    except Exception as e:
        # If logging fails, print to console as last resort
        print(f"Logging failed: {e}")
        print(f"Original message: {message}")
        if error:
            print(f"Traceback: {traceback.format_exc()}")

def clean_text_for_pdf(text: str, job_id: Optional[str] = None) -> str:
    """Clean text to remove problematic characters while preserving Unicode characters"""
    if not text:
        return ""
    
    log_pdf_step("TEXT", f"Cleaning text: {text[:50]}...", job_id=job_id)
    return text.strip()

def add_metadata_item(pdf: FPDF, label: str, value: str, x_pos: float):
    """Helper function to add a metadata item with a bold label."""
    if not value:  # Don't display if value is empty
        return
        
    pdf.set_x(x_pos)
    pdf.set_font("DejaVu", style="B", size=11)
    pdf.cell(pdf.get_string_width(label) + 1, 7, label)
    
    pdf.set_font("DejaVu", style="", size=11)
    pdf.multi_cell(0, 7, value, align="L")

def get_image_orientation(image_path: str) -> str:
    """
    Detect image orientation (portrait, landscape, or square).
    Returns: 'portrait', 'landscape', or 'square'
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            if height > width:
                return 'portrait'
            elif width > height:
                return 'landscape'
            else:
                return 'square'
    except Exception as e:
        logger.error(f"Error detecting image orientation: {e}")
        return 'landscape'  # Default fallback

def calculate_image_dimensions(image_path: str, max_width: float, max_height: float) -> tuple:
    """
    Calculate optimal image dimensions while maintaining aspect ratio.
    Returns: (width, height)
    """
    try:
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            aspect_ratio = original_width / original_height
            
            # Calculate dimensions that fit within max constraints
            if aspect_ratio > 1:  # Landscape
                width = min(max_width, max_height * aspect_ratio)
                height = width / aspect_ratio
            else:  # Portrait or square
                height = min(max_height, max_width / aspect_ratio)
                width = height * aspect_ratio
            
            return width, height
    except Exception as e:
        logger.error(f"Error calculating image dimensions: {e}")
        return max_width, max_height  # Default fallback

def generate_pdf(recipe: Recipe, job_id: str, template_name: str = "default", language: str = "en", video_url: Optional[str] = None) -> str:
    """Generate PDF from recipe content using a CSS template."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{job_id}.pdf"
    
    log_pdf_step("START", "Starting PDF generation", job_id=job_id)
    log_pdf_step("CONFIG", f"Using template: {template_name}, language: {language}", job_id=job_id)
    log_pdf_step("DEBUG", f"Recipe content: {recipe.model_dump()}", job_id=job_id)
    
    try:
        # Initialize style manager and PDF
        log_pdf_step("INIT", "Initializing style manager", job_id=job_id)
        style_manager = PDFStyleManager(template_name)
        
        # Ensure fonts are loaded before proceeding
        if not style_manager.fonts_loaded:
            raise RuntimeError("Fonts failed to initialize properly")
        
        pdf = FPDF()
        pdf.set_doc_option("core_fonts_encoding", "utf-8")
        # Lägg till fonter på denna instans
        log_pdf_step("FONTS", "Adding fonts to PDF", job_id=job_id)
        style_manager.add_fonts_to_pdf(pdf)
        
        # Testa att fonten verkligen finns
        try:
            pdf.set_font("DejaVu", style="B", size=10)
        except Exception as e:
            log_pdf_step("FONTS", f"Font test misslyckades: {e}", error=True, job_id=job_id)
            raise
        
        # Apply page settings from CSS
        log_pdf_step("SETTINGS", "Applying page settings from CSS", job_id=job_id)
        page_settings = style_manager.get_page_settings()
        pdf.set_margins(page_settings.get("margin", 20), page_settings.get("margin", 20))
        pdf.set_auto_page_break(True, margin=page_settings.get("margin", 20))
        
        pdf.add_page()
        
        # --- Main Title (Recipe Name) ---
        try:
            log_pdf_step("TITLE", f"Adding recipe title: {recipe.title}", job_id=job_id)
            title_style = style_manager.get_style("title")
            pdf.set_font("DejaVu", 
                        style=title_style.get("font_style", "B"), 
                        size=title_style.get("font_size", 28))
            title = clean_text_for_pdf(recipe.title, job_id)
            pdf.multi_cell(0, 12, title.upper(), align=title_style.get("align", "L"), ln=True)
            pdf.ln(10) # Add space after title
        except Exception as e:
            log_pdf_step("ERROR", f"Failed to add main title: {str(e)}", error=True, job_id=job_id)
            raise
        
        # --- Recipe Header Section ---
        try:
            log_pdf_step("HEADER", "Starting recipe header section", job_id=job_id)
            start_y = pdf.get_y()
            
            # Define column layout
            usable_width = pdf.w - pdf.l_margin - pdf.r_margin
            image_width = usable_width * 0.48
            image_height = image_width * 0.75
            desc_x = pdf.l_margin + image_width + (usable_width * 0.04)
            desc_width = usable_width * 0.48
            
            # Left column - Image or Placeholder with text
            if recipe.thumbnail_path and os.path.exists(recipe.thumbnail_path):
                # Check image orientation and adjust dimensions
                orientation = get_image_orientation(recipe.thumbnail_path)
                log_pdf_step("HEADER", f"Thumbnail orientation: {orientation}", job_id=job_id)
                
                if orientation == 'portrait':
                    # For portrait images, make them taller and narrower
                    image_width = usable_width * 0.35
                    image_height = image_width * 1.4  # Portrait ratio
                    desc_x = pdf.l_margin + image_width + (usable_width * 0.04)
                    desc_width = usable_width * 0.57
                
                # Calculate optimal dimensions maintaining aspect ratio
                img_width, img_height = calculate_image_dimensions(
                    recipe.thumbnail_path, image_width, image_height
                )
                
                # Always align thumbnail top with the start position
                pdf.image(recipe.thumbnail_path, x=pdf.l_margin, y=start_y, w=img_width, h=img_height)
                image_height = img_height  # Update for layout calculation
            else:
                pdf.set_fill_color(230, 230, 230) # Light gray
                pdf.rect(pdf.l_margin, start_y, image_width, image_height, 'F')
                pdf.set_xy(pdf.l_margin, start_y + (image_height / 2) - 5)
                pdf.set_font("DejaVu", style="I", size=12)
                pdf.multi_cell(image_width, 10, "Image not available", align="C")

            # Right column - Description and metadata
            desc_y = start_y
            if recipe.description:
                desc_style = style_manager.get_style("description")
                pdf.set_xy(desc_x, desc_y)
                pdf.set_font("DejaVu", 
                           style=desc_style.get("font_style", ""), 
                           size=desc_style.get("font_size", 12))
                pdf.multi_cell(desc_width, 7, recipe.description, align=desc_style.get("align", "L"))
                desc_y = pdf.get_y() + 5
            
            # Metadata - always appears below description (or at the top if no description)
            pdf.set_y(desc_y)
            add_metadata_item(pdf, "Serves: ", str(getattr(recipe, 'servings', '') or ''), desc_x)
            add_metadata_item(pdf, "Prep Time: ", str(getattr(recipe, 'prep_time', '') or ''), desc_x)
            add_metadata_item(pdf, "Cook Time: ", str(getattr(recipe, 'cook_time', '') or ''), desc_x)
            
            # Calculate final Y position
            text_bottom = pdf.get_y()
            image_bottom = start_y + image_height
            pdf.set_y(max(text_bottom, image_bottom) + 15)
            
        except Exception as e:
            log_pdf_step("ERROR", f"Error in recipe header: {str(e)}", error=True, job_id=job_id)
            pdf.ln(10)
        
        # Ingredients section
        try:
            header_style = style_manager.get_style("section-header")
            log_pdf_step("DEBUG", f"Header style: {header_style}", job_id=job_id)
            pdf.set_font("DejaVu", 
                        style=header_style.get("font_style", ""), 
                        size=header_style.get("font_size", 24))
            pdf.cell(0, 12, "Ingredients:", align=header_style.get("align", "L"), ln=True)
            
            # Split ingredients into two columns
            ingredient_style = style_manager.get_style("ingredient-item")
            log_pdf_step("DEBUG", f"Ingredient style: {ingredient_style}", job_id=job_id)
            pdf.set_font("DejaVu", 
                        style=ingredient_style.get("font_style", ""), 
                        size=ingredient_style.get("font_size", 12))
            
            total_ingredients = len(recipe.ingredients)
            log_pdf_step("DEBUG", f"Total ingredients: {total_ingredients}", job_id=job_id)
            mid_point = (total_ingredients + 1) // 2
            col_width = (pdf.w - pdf.l_margin - pdf.r_margin) / 2 # No gap, use full width
            
            start_x = pdf.l_margin
            start_y = pdf.get_y() + 5
            
            # Left column
            current_y = start_y
            for item in recipe.ingredients[:mid_point]:
                pdf.set_xy(start_x, current_y)
                clean_item = "• " + clean_text_for_pdf(item, job_id)
                pdf.multi_cell(col_width - 5, 8, clean_item, align=ingredient_style.get("align", "L")) # Subtract padding
                current_y = pdf.get_y() + 1 # Smaller gap
            left_col_height = current_y

            # Right column
            current_y = start_y
            for item in recipe.ingredients[mid_point:]:
                pdf.set_xy(start_x + col_width, current_y)
                clean_item = "• " + clean_text_for_pdf(item, job_id)
                pdf.multi_cell(col_width - 5, 8, clean_item, align=ingredient_style.get("align", "L")) # Subtract padding
                current_y = pdf.get_y() + 1 # Smaller gap
            right_col_height = current_y
            
            # Move cursor past ingredients
            pdf.set_y(max(left_col_height, right_col_height) + 10)
        except Exception as e:
            log_pdf_step("ERROR", f"Failed to add ingredients section: {str(e)}", error=True, job_id=job_id)
            raise
        
        # Instructions section
        try:
            pdf.set_font("DejaVu", 
                        style=header_style.get("font_style", ""), 
                        size=header_style.get("font_size", 24))
            pdf.cell(0, 12, "Instructions:", align=header_style.get("align", "L"), ln=True)
            
            step_style = style_manager.get_style("step-item")
            log_pdf_step("DEBUG", f"Step style: {step_style}", job_id=job_id)
            
            for idx, step in enumerate(recipe.steps, 1):
                usable_width = pdf.w - pdf.l_margin - pdf.r_margin
                
                # Check if step has an image to determine layout
                has_image = step.image_path and os.path.exists(step.image_path)
                
                if has_image and step.image_path:
                    # Detect image orientation
                    orientation = get_image_orientation(step.image_path)
                    log_pdf_step("STEP", f"Step {idx} image orientation: {orientation}", job_id=job_id)
                    
                    if orientation == 'portrait':
                        # Portrait layout: image takes more vertical space, less horizontal
                        text_col_width = usable_width * 0.65
                        image_col_width = usable_width * 0.30
                        max_image_height = 80  # Taller for portrait images
                    else:
                        # Landscape layout: traditional side-by-side
                        text_col_width = usable_width * 0.50
                        image_col_width = usable_width * 0.40
                        max_image_height = 50  # Standard height for landscape
                    
                    # Calculate actual image dimensions
                    img_width, img_height = calculate_image_dimensions(
                        step.image_path, image_col_width, max_image_height
                    )
                else:
                    # No image: use full width for text
                    text_col_width = usable_width
                    img_width = img_height = 0
                
                # Parse step description
                if ':' in step.description:
                    title, desc = step.description.split(':', 1)
                    title = title.strip()
                    desc = desc.strip()
                else:
                    title = step.description.strip()
                    desc = ""

                # Calculate text height
                numbered_title = f"{idx}. {title}"
                pdf.set_font("DejaVu", style="", size=14)
                title_lines = pdf.multi_cell(text_col_width, 8, numbered_title, align="L", split_only=True)
                pdf.set_font("DejaVu", style="", size=12)
                desc_lines = pdf.multi_cell(text_col_width, 8, desc, align="L", split_only=True) if desc else []
                text_height = (len(title_lines) * 8) + (len(desc_lines) * 8)

                # Calculate needed height
                needed_height = max(text_height, img_height) + 15
                
                # Check if we need a new page
                if pdf.get_y() + needed_height > pdf.h - pdf.b_margin:
                    pdf.add_page()
                    start_y = pdf.get_y()
                else:
                    start_y = pdf.get_y()

                # Add text content
                pdf.set_xy(pdf.l_margin, start_y)
                pdf.set_font("DejaVu", style="", size=14)
                pdf.multi_cell(text_col_width, 8, numbered_title, align="L")
                if desc:
                    pdf.set_font("DejaVu", style="", size=12)
                    pdf.multi_cell(text_col_width, 8, desc, align="L")

                # Add image if available
                if has_image:
                    img_x = pdf.l_margin + text_col_width + 10
                    img_y = start_y  # Always align image top with text top
                    
                    pdf.image(step.image_path, x=img_x, y=img_y, w=img_width, h=img_height)
                    log_pdf_step("STEP", f"Added {orientation} image for step {idx}: {img_width}x{img_height} at position ({img_x}, {img_y})", job_id=job_id)

                # Move to next step
                pdf.set_y(start_y + max(text_height, img_height) + 15)
                
        except Exception as e:
            log_pdf_step("ERROR", f"Failed to add instructions section: {str(e)}", error=True, job_id=job_id)
            raise
        
        # Footer
        try:
            footer_style = style_manager.get_style("footer")
            log_pdf_step("DEBUG", f"Footer style: {footer_style}", job_id=job_id)
            pdf.set_font("DejaVu", 
                        style=footer_style.get("font_style", "I"), 
                        size=footer_style.get("font_size", 9))
            if "text_color" in footer_style:
                pdf.set_text_color(*footer_style["text_color"])
            
            # Generate timestamp
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
            footer_text = f"Generated by Food2Guide - {timestamp}"
            
            # Add footer text
            pdf.cell(0, 5, footer_text, ln=True, align=footer_style.get("align", "C"))
            
            # Add video URL if provided
            if video_url:
                pdf.ln(3)  # Small space
                pdf.set_font("DejaVu", style="", size=8)
                pdf.cell(0, 5, f"Original video: {video_url}", ln=True, align="C")
                
        except Exception as e:
            log_pdf_step("ERROR", f"Failed to add footer: {str(e)}", error=True, job_id=job_id)
            raise
        
        # Save PDF
        try:
            log_pdf_step("SAVE", f"Saving PDF to {output_path}", job_id=job_id)
            pdf.output(str(output_path))
            log_pdf_step("COMPLETE", f"PDF created successfully at {output_path}", job_id=job_id)
            return str(output_path)
        except Exception as e:
            log_pdf_step("ERROR", f"Failed to save PDF: {str(e)}", error=True, job_id=job_id)
            raise
            
    except Exception as e:
        log_pdf_step("ERROR", f"PDF generation error: {str(e)}", error=True, job_id=job_id)
        log_pdf_step("ERROR", f"Traceback: {traceback.format_exc()}", error=True, job_id=job_id)
        raise 