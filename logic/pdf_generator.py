from fpdf import FPDF
from typing import List
import os
from models.types import VideoContent, Step
import logging
import traceback
from datetime import datetime
from pathlib import Path

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('output/pdf_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def log_pdf_step(step: str, message: str, error: bool = False):
    """Helper function for consistent PDF logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_message = f"[PDF {timestamp}] [{step}] {message}"
    if error:
        logger.error(log_message)
    else:
        logger.info(log_message)

def clean_text_for_pdf(text: str) -> str:
    """Clean text to remove problematic characters while preserving Swedish characters"""
    if not text:
        return ""
    
    log_pdf_step("TEXT", f"Cleaning text: {text[:50]}...")
    
    text = text.strip()
    while text and text[0] in ['•', '●', '◦', '‣', '⁃', '▪', '▫', '▸', '‧']:
        text = text[1:].strip()
    
    replacements = {
        """: '"',
        """: '"',
        "'": "'",
        "'": "'",
        "—": "-",
        "–": "-",
        "…": "...",
        "•": "-",
        "●": "-",
        "◦": "-",
        "‣": "-",
        "⁃": "-",
        "▪": "-",
        "▫": "-",
        "▸": "-",
        "‧": "-",
        "‚": ",",
        "„": '"',
        "‹": "<",
        "›": ">",
        "«": '"',
        "»": '"',
    }
    
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    safe_chars = []
    for char in result:
        if (ord(char) < 128 or 
            char in 'åäöÅÄÖéèàáíìúùóòñÑüÜ°' or 
            char.isspace()):
            safe_chars.append(char)
        else:
            log_pdf_step("TEXT", f"Replacing unsafe character: {char} (Unicode: {ord(char)})")
            safe_chars.append('?')
    
    cleaned = ''.join(safe_chars).strip()
    log_pdf_step("TEXT", f"Cleaned text: {cleaned[:50]}...")
    return cleaned

def generate_pdf(video_content: VideoContent, job_id: str, language: str = "en") -> str:
    """Generate PDF from video content."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{job_id}.pdf"
    
    log_pdf_step("START", f"Beginning PDF generation for job {job_id}")
    
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Use Arial as fallback font which has good Unicode support
        log_pdf_step("FONT", "Setting up Arial font")
        pdf.set_font('Arial', '', 12)
        
        # Title - large, bold and centered
        log_pdf_step("TITLE", f"Adding title: {video_content.title}")
        pdf.set_font('Arial', 'B', 24)
        title = clean_text_for_pdf(video_content.title)
        pdf.cell(0, 20, title.upper(), align='C', ln=True)
        pdf.ln(10)
        
        # Description - centered, normal font
        if hasattr(video_content, 'description') and video_content.description:
            log_pdf_step("DESC", "Adding description")
            pdf.set_font('Arial', '', 12)
            description = clean_text_for_pdf(video_content.description)
            lines = pdf.multi_cell(0, 8, description, align='C', split_only=True)
            for line in lines:
                pdf.cell(0, 8, line, align='C', ln=True)
            pdf.ln(5)
        
        # Metadata
        log_pdf_step("META", f"Adding metadata: {len(video_content.steps)} steps, {len(video_content.materials_or_ingredients)} ingredients")
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f"Number of steps: {len(video_content.steps)}", ln=True)
        pdf.cell(0, 8, f"Number of ingredients: {len(video_content.materials_or_ingredients)}", ln=True)
        pdf.ln(15)
        
        # Ingredients header
        log_pdf_step("INGREDIENTS", "Starting ingredients section")
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, "Ingredients:", ln=True)
        pdf.ln(5)
        
        # Split ingredients into two columns
        total_ingredients = len(video_content.materials_or_ingredients)
        mid_point = (total_ingredients + 1) // 2
        col_width = pdf.w / 2 - 20
        
        pdf.set_font('Arial', '', 12)
        start_x = pdf.get_x()
        start_y = pdf.get_y()
        
        # Left column
        log_pdf_step("INGREDIENTS", "Adding left column")
        for i, item in enumerate(video_content.materials_or_ingredients[:mid_point]):
            pdf.set_xy(start_x, start_y + i * 8)
            clean_item = clean_text_for_pdf(item)
            pdf.cell(col_width, 8, f"- {clean_item}")
        
        # Right column
        log_pdf_step("INGREDIENTS", "Adding right column")
        for i, item in enumerate(video_content.materials_or_ingredients[mid_point:]):
            pdf.set_xy(start_x + pdf.w/2, start_y + i * 8)
            clean_item = clean_text_for_pdf(item)
            pdf.cell(col_width, 8, f"- {clean_item}")
        
        # Move cursor past ingredients
        pdf.set_xy(start_x, start_y + max(mid_point, total_ingredients - mid_point) * 8 + 20)
        
        # Instructions header
        log_pdf_step("INSTRUCTIONS", "Starting instructions section")
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, "Instructions:", ln=True)
        pdf.ln(10)
        
        # Process each step
        for step in video_content.steps:
            log_pdf_step("STEP", f"Processing step {step.number}: {step.action}")
            
            if pdf.get_y() > pdf.h - 60:
                log_pdf_step("PAGE", "Adding new page")
                pdf.add_page()
            
            start_y = pdf.get_y()
            
            # Text column width
            text_col_width = pdf.w * 0.6 if step.image_path else pdf.w - 20
            
            # Step number and title
            pdf.set_font('Arial', 'B', 14)
            pdf.set_xy(pdf.l_margin, start_y)
            action = clean_text_for_pdf(step.action)
            pdf.cell(text_col_width, 10, f"{step.number}. {action}", ln=True)
            
            # Step explanation
            pdf.set_font('Arial', '', 12)
            pdf.set_xy(pdf.l_margin, pdf.get_y() + 2)
            explanation = clean_text_for_pdf(step.explanation)
            pdf.multi_cell(text_col_width, 8, explanation)
            
            # Image handling
            if step.image_path and os.path.exists(step.image_path):
                try:
                    log_pdf_step("IMAGE", f"Adding image for step {step.number}: {step.image_path}")
                    image_x = pdf.l_margin + text_col_width + 10
                    image_width = pdf.w * 0.35
                    image_height = 50
                    
                    image_y = start_y
                    pdf.image(str(step.image_path), x=image_x, y=image_y, w=image_width)
                    log_pdf_step("IMAGE", f"Successfully added image for step {step.number}")
                    
                    # Ensure proper spacing
                    current_y = pdf.get_y()
                    image_bottom = image_y + image_height
                    pdf.set_y(max(current_y, image_bottom) + 5)
                    
                except Exception as e:
                    log_pdf_step("IMAGE", f"Error adding image for step {step.number}: {e}", error=True)
                    log_pdf_step("IMAGE", f"Traceback: {traceback.format_exc()}", error=True)
            else:
                log_pdf_step("IMAGE", f"No image available for step {step.number}")
            
            # Add separator between steps
            if step.number < len(video_content.steps):
                pdf.ln(8)
                pdf.set_draw_color(230, 230, 230)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        
        # Footer
        log_pdf_step("FOOTER", "Adding footer")
        pdf.ln(15)
        pdf.set_font('Arial', 'I', 9)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, f"Generated by MakeItEasy - {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align='C')
        
        # Save PDF
        log_pdf_step("SAVE", f"Saving PDF to {output_path}")
        pdf.output(str(output_path))
        
        log_pdf_step("COMPLETE", f"PDF created successfully: {output_path}")
        return str(output_path)
        
    except Exception as e:
        log_pdf_step("ERROR", f"PDF generation error: {e}", error=True)
        log_pdf_step("ERROR", f"Traceback: {traceback.format_exc()}", error=True)
        
        # Create simple fallback PDF
        try:
            log_pdf_step("FALLBACK", "Attempting to create fallback PDF")
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, "PDF generation failed", ln=True)
            pdf.ln(10)
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, "An error occurred while creating the PDF file.", ln=True)
            pdf.ln(5)
            pdf.cell(0, 10, f"Error message: {str(e)}", ln=True)
            pdf.ln(10)
            pdf.cell(0, 10, "Try processing the video again or contact support.", ln=True)
            
            pdf.output(str(output_path))
            log_pdf_step("FALLBACK", "Fallback PDF created successfully")
            return str(output_path)
            
        except Exception as fallback_error:
            log_pdf_step("CRITICAL", f"Fallback PDF creation failed: {fallback_error}", error=True)
            return str(output_path) 