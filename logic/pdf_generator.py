from fpdf import FPDF
from typing import List, Optional
import os
from models.types import Recipe, Step, RecipeContent
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

def crop_image_if_needed(image_path: str, crop_top: float, crop_bottom: float, job_id: str) -> str:
    """
    Crop image from top and bottom if crop values are specified.
    Returns: path to cropped image (or original if no cropping needed)
    """
    if crop_top <= 0 and crop_bottom <= 0:
        return image_path  # No cropping needed
    
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Convert points to pixels (assuming 72 DPI)
            crop_top_px = int(crop_top * 72 / 72)  # Points to pixels
            crop_bottom_px = int(crop_bottom * 72 / 72)  # Points to pixels
            
            # Calculate crop box
            left = 0
            top = crop_top_px
            right = width
            bottom = height - crop_bottom_px
            
            # Ensure valid crop box
            if bottom <= top:
                log_pdf_step("CROP", f"Invalid crop dimensions for {image_path}, skipping crop", job_id=job_id)
                return image_path
            
            # Crop the image
            cropped_img = img.crop((left, top, right, bottom))
            
            # Save cropped image with suffix
            path_obj = Path(image_path)
            cropped_path = path_obj.parent / f"{path_obj.stem}_cropped{path_obj.suffix}"
            cropped_img.save(cropped_path)
            
            log_pdf_step("CROP", f"Cropped image: {crop_top}pt top, {crop_bottom}pt bottom -> {cropped_path}", job_id=job_id)
            return str(cropped_path)
            
    except Exception as e:
        log_pdf_step("CROP", f"Error cropping image {image_path}: {e}", error=True, job_id=job_id)
        return image_path  # Return original on error

def get_image_style_from_orientation(orientation: str, image_type: str) -> str:
    """
    Get CSS class name based on image orientation and type.
    image_type: 'thumbnail' or 'step'
    orientation: 'portrait', 'landscape', or 'square'
    """
    if image_type == "thumbnail":
        return f"thumbnail-{orientation}" if orientation in ['portrait', 'landscape'] else "thumbnail-landscape"
    elif image_type == "step":
        return f"step-image-{orientation}" if orientation in ['portrait', 'landscape'] else "step-image-landscape"
    else:
        return "step-image-landscape"  # Default fallback

async def convert_recipe_content_to_recipe(content: RecipeContent) -> Recipe:
    """Converts a RecipeContent object to a Recipe object for PDF generation."""
    
    # Convert ingredients
    ingredients_list = []
    if content.ingredients:
        for ing in content.ingredients:
            line = f"{ing.quantity} {ing.name}"
            if ing.notes:
                line += f" ({ing.notes})"
            ingredients_list.append(line)

    # Convert instructions to steps
    steps_list = []
    if content.instructions:
        for inst in content.instructions:
            steps_list.append(Step(step_number=inst.step, description=inst.description, image_path=inst.image_path))
            
    # Add chef tips to the end of instructions, if any
    if content.chef_tips:
        last_step = len(steps_list)
        for i, tip in enumerate(content.chef_tips, 1):
            steps_list.append(Step(step_number=last_step + i, description=f"Chef's Tip: {tip}"))

    return Recipe(
        title=content.title,
        description=content.description,
        serves=content.servings,
        prep_time=content.prep_time,
        cook_time=content.cook_time,
        ingredients=ingredients_list,
        steps=steps_list,
        thumbnail_path=getattr(content, 'thumbnail_path', None)
    )
    
def generate_pdf(recipe: Recipe, job_id: str, template_name: str = "default", language: str = "en", video_url: Optional[str] = None, video_title: Optional[str] = None, show_top_image: bool = True, show_step_images: bool = True) -> str:
    """Generate PDF from recipe content using a CSS template."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Use video title for filename if provided, otherwise use job_id
    if video_title:
        filename = f"{video_title}-recipe-guide.pdf"
    else:
        filename = f"{job_id}.pdf"
    
    output_path = output_dir / filename
    
    log_pdf_step("START", "Starting PDF generation", job_id=job_id)
    log_pdf_step("CONFIG", f"Using template: {template_name}, language: {language}", job_id=job_id)
    
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
            # Default dimensions (will be overridden by CSS if available)
            image_width = usable_width * 0.48
            image_height = image_width * 0.75
            
            # Left column - Image or Placeholder with text
            if show_top_image and recipe.thumbnail_path and os.path.exists(recipe.thumbnail_path):
                log_pdf_step("HEADER", f"✅ Found thumbnail: {recipe.thumbnail_path}", job_id=job_id)
                # Check image orientation and get appropriate CSS style
                orientation = get_image_orientation(recipe.thumbnail_path)
                log_pdf_step("HEADER", f"Thumbnail orientation: {orientation}", job_id=job_id)
                
                # Get orientation-specific CSS style
                thumbnail_style_class = get_image_style_from_orientation(orientation, "thumbnail")
                thumbnail_style = style_manager.get_style(thumbnail_style_class)
                log_pdf_step("HEADER", f"Using thumbnail style: {thumbnail_style_class} -> {thumbnail_style}", job_id=job_id)
                
                # Get dimensions from CSS or use defaults
                if thumbnail_style.get("width"):
                    image_width = thumbnail_style["width"]
                elif thumbnail_style.get("width_percent"):
                    image_width = usable_width * (thumbnail_style["width_percent"] / 100)
                else:
                    image_width = usable_width * (0.35 if orientation == 'portrait' else 0.48)
                
                if thumbnail_style.get("height"):
                    image_height = thumbnail_style["height"]
                elif thumbnail_style.get("height_percent"):
                    image_height = image_width * (thumbnail_style["height_percent"] / 100)
                else:
                    image_height = image_width * (1.4 if orientation == 'portrait' else 0.75)
                
                # Apply max dimensions from CSS
                if thumbnail_style.get("max_width"):
                    image_width = min(image_width, thumbnail_style["max_width"])
                if thumbnail_style.get("max_height"):
                    image_height = min(image_height, thumbnail_style["max_height"])
                
                # Apply cropping if specified for portrait images
                thumbnail_path = recipe.thumbnail_path
                if orientation == 'portrait':
                    crop_top = thumbnail_style.get("crop_top", 0)
                    crop_bottom = thumbnail_style.get("crop_bottom", 0)
                    thumbnail_path = crop_image_if_needed(thumbnail_path, crop_top, crop_bottom, job_id)
                
                # Use CSS dimensions directly for consistent sizing
                img_width, img_height = image_width, image_height
                
                # Always align thumbnail top with the start position
                pdf.image(thumbnail_path, x=pdf.l_margin, y=start_y, w=img_width, h=img_height)
                image_height = img_height  # Update for layout calculation
            elif show_top_image:
                log_pdf_step("HEADER", "Thumbnail not found or path is invalid.", job_id=job_id)
                pdf.set_fill_color(230, 230, 230) # Light gray
                pdf.rect(pdf.l_margin, start_y, image_width, image_height, 'F')
                pdf.set_xy(pdf.l_margin, start_y + (image_height / 2) - 5)
                pdf.set_font("DejaVu", style="I", size=12)
                pdf.multi_cell(image_width, 10, "Image not available", align="C")
            # If show_images is false, this block is skipped entirely.

            # Calculate description column layout based on actual image width
            gap = 10  # Gap between image and text
            desc_x = pdf.l_margin + image_width + gap
            desc_width = usable_width - image_width - gap
            
            # Ensure minimum width for description text
            min_desc_width = 80  # Minimum 80pt for text
            if desc_width < min_desc_width:
                # If calculated width is too small, use full width layout instead
                log_pdf_step("HEADER", f"Description width too small ({desc_width}pt), using full-width layout", job_id=job_id)
                desc_x = pdf.l_margin
                desc_width = usable_width
                desc_y = start_y + image_height + 10  # Place text below image
            else:
                desc_y = start_y  # Place text beside image

            # Right column - Description and metadata
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
            
            ingredient_style = style_manager.get_style("ingredient-item")
            log_pdf_step("DEBUG", f"Ingredient style: {ingredient_style}", job_id=job_id)
            pdf.set_font("DejaVu", 
                        style=ingredient_style.get("font_style", ""), 
                        size=ingredient_style.get("font_size", 12))
            
            # Hantera grupperad eller platt lista
            ingredients_data = recipe.ingredients
            col_width = (pdf.w - pdf.l_margin - pdf.r_margin) / 2 - 5
            gap = 10  # Gap mellan kolumner
            left_x = pdf.l_margin
            right_x = pdf.l_margin + col_width + gap
            start_y = pdf.get_y() + 5
            margin_bottom = 5
            max_y = pdf.h - pdf.b_margin - 10
            line_height = 8

            # Gör om till platt lista av rader (strängar)
            if ingredients_data and isinstance(ingredients_data, list) and isinstance(ingredients_data[0], dict) and 'title' in ingredients_data[0]:
                # Grupperad lista
                flat_ingredients = []
                for block in ingredients_data:
                    if isinstance(block, dict):
                        flat_ingredients.append({'type': 'title', 'text': block.get('title', '')})
                        for item in block.get('items', []):
                            flat_ingredients.append({'type': 'item', 'text': f"• {item}"})
                    else:
                        flat_ingredients.append({'type': 'item', 'text': f"• {str(block)}"})
            else:
                # Platt lista
                flat_ingredients = [{'type': 'item', 'text': f"• {item}"} for item in (ingredients_data if ingredients_data else [])]

            # Dynamisk tvåkolumnslayout
            y_left = start_y
            y_right = start_y
            x_left = left_x
            x_right = right_x
            col = 1  # 1 = vänster, 2 = höger
            i = 0
            while i < len(flat_ingredients):
                entry = flat_ingredients[i]
                # Välj kolumn
                if col == 1:
                    pdf.set_xy(x_left, y_left)
                else:
                    pdf.set_xy(x_right, y_right)
                # Sätt font och beräkna höjd
                if entry['type'] == 'title':
                    pdf.set_font("DejaVu", style="B", size=14)
                    # Beräkna höjd för rubrik
                    n_lines = pdf.get_string_width(entry['text']) // col_width + 1
                    h = line_height * n_lines
                else:
                    pdf.set_font("DejaVu", size=12)
                    n_lines = pdf.get_string_width(entry['text']) // col_width + 1
                    h = line_height * n_lines
                # Rita ut
                pdf.multi_cell(col_width, line_height, entry['text'])
                # Uppdatera y-position
                if col == 1:
                    y_left = pdf.get_y()
                    # Om vi når botten, byt till kolumn 2
                    if y_left + h > max_y:
                        col = 2
                else:
                    y_right = pdf.get_y()
                    # Om vi når botten, byt sida
                    if y_right + h > max_y:
                        pdf.add_page()
                        y_left = y_right = pdf.get_y() + 5
                        col = 1
                # Gå till nästa rad
                i += 1
            # Sätt y till efter den högsta kolumnen
            final_y = max(y_left, y_right)
            pdf.set_y(final_y + margin_bottom)

        except Exception as e:
            log_pdf_step("ERROR", f"Failed to add ingredients section: {str(e)}", error=True, job_id=job_id)
            raise
        
        # Instructions section
        try:
            pdf.set_font("DejaVu", 
                        style=header_style.get("font_style", ""), 
                        size=header_style.get("font_size", 24))
            pdf.cell(0, 12, "Instructions:", align=header_style.get("align", "L"), ln=True)
            
            step_style = style_manager.get_style("step")
            step_content_style = style_manager.get_style("step-content")
            log_pdf_step("DEBUG", f"Step style: {step_style}", job_id=job_id)
            log_pdf_step("DEBUG", f"Step content style: {step_content_style}", job_id=job_id)
            
            # DEBUG: Let's see what margin-bottom value we're actually getting
            step_margin_bottom = step_style.get("margin_bottom", 80)
            log_pdf_step("DEBUG", f"Step margin-bottom from CSS: {step_margin_bottom}pt", job_id=job_id)
            
            for idx, step in enumerate(recipe.steps, 1):
                usable_width = pdf.w - pdf.l_margin - pdf.r_margin
                
                # Check if step has an image to determine layout
                has_image = show_step_images and step.image_path and os.path.exists(step.image_path)
                
                # Parse step description
                if ':' in step.description:
                    title, desc = step.description.split(':', 1)
                    title = title.strip()
                    desc = desc.strip()
                else:
                    title = step.description.strip()
                    desc = ""

                # Check if we need a new page
                if pdf.get_y() + 60 > pdf.h - pdf.b_margin:
                    pdf.add_page()
                
                start_y = pdf.get_y()
                
                # Layout configuration using CSS styles
                if has_image and step.image_path:
                    # Get image orientation and appropriate CSS style
                    step_orientation = get_image_orientation(step.image_path)
                    step_image_style_class = get_image_style_from_orientation(step_orientation, "step")
                    step_image_style = style_manager.get_style(step_image_style_class)
                    log_pdf_step("STEP", f"Step {idx} image orientation: {step_orientation}, using style: {step_image_style_class}", job_id=job_id)
                    
                    # Get dimensions from CSS or use defaults
                    if step_image_style.get("width"):
                        image_width = step_image_style["width"]
                    else:
                        image_width = usable_width * (0.30 if step_orientation == 'portrait' else 0.40)
                    
                    if step_image_style.get("height"):
                        image_height = step_image_style["height"]
                    else:
                        image_height = 120 if step_orientation == 'portrait' else 67
                    
                    # Calculate text width based on image width
                    gap = 24  # 24pt gap from CSS
                    text_width = usable_width - image_width - gap
                    
                    # Apply cropping if specified for portrait images
                    step_image_path = step.image_path
                    if step_orientation == 'portrait':
                        crop_top = step_image_style.get("crop_top", 0)
                        crop_bottom = step_image_style.get("crop_bottom", 0)
                        step_image_path = crop_image_if_needed(step_image_path, crop_top, crop_bottom, job_id)
                    
                    # Use CSS dimensions directly for consistent sizing
                    img_width, img_height = image_width, image_height
                    
                    # Position image on the right with gap from CSS
                    img_x = pdf.l_margin + text_width + gap
                    img_y = start_y + 5
                    
                    pdf.image(step_image_path, x=img_x, y=img_y, w=img_width, h=img_height)
                    log_pdf_step("STEP", f"Added {step_orientation} image for step {idx}: {img_width}x{img_height} at ({img_x}, {img_y})", job_id=job_id)
                else:
                    # No image: use full width for text
                    text_width = usable_width
                
                # Add text content using CSS styles
                pdf.set_xy(pdf.l_margin, start_y + 5)
                
                # Title and description using CSS step-content styles
                numbered_title = f"{idx}. {title}"
                pdf.set_font("DejaVu", 
                           style=step_content_style.get("font_style", ""), 
                           size=step_content_style.get("font_size", 12))
                pdf.multi_cell(text_width, step_content_style.get("line_height", 6), numbered_title, align=step_content_style.get("align", "L"))
                
                # Description
                if desc:
                    pdf.set_font("DejaVu", 
                               style=step_content_style.get("font_style", ""), 
                               size=step_content_style.get("font_size", 12))
                    pdf.multi_cell(text_width, step_content_style.get("line_height", 6), desc, align=step_content_style.get("align", "L"))
                
                # Move to next step using CSS margin-bottom from .step class
                current_y = pdf.get_y()
                step_margin_bottom = step_style.get("margin_bottom", 80)  # Default 80pt from CSS
                pdf.set_y(current_y + step_margin_bottom)
                log_pdf_step("STEP", f"Step {idx} completed, moved {step_margin_bottom}pt down", job_id=job_id)
                
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