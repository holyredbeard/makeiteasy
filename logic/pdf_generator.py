from fpdf import FPDF
from typing import List
import os
from models.types import VideoContent, Step

def clean_text_for_pdf(text: str) -> str:
    """Clean text to remove problematic characters while preserving Swedish characters"""
    if not text:
        return ""
    
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
            safe_chars.append('?')
    
    return ''.join(safe_chars).strip()

def generate_pdf(video_content: VideoContent, job_id: str, language: str = "en") -> str:
    """Generate PDF from video content."""
    pdf = FPDF()
    pdf.add_page()
    
    # Add font with Unicode support for Swedish characters
    pdf.add_font('DejaVu', '', '/System/Library/Fonts/Supplemental/DejaVuSans.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', '/System/Library/Fonts/Supplemental/DejaVuSans-Bold.ttf', uni=True)
    
    # Title - large, bold and centered
    pdf.set_font('DejaVu', 'B', 24)
    title = clean_text_for_pdf(video_content.title)
    pdf.cell(0, 20, title.upper(), align='C', ln=True)
    pdf.ln(10)
    
    # Description - centered, normal font
    if hasattr(video_content, 'description') and video_content.description:
        pdf.set_font('DejaVu', '', 12)
        description = clean_text_for_pdf(video_content.description)
        # Calculate width to center the text block
        lines = pdf.multi_cell(0, 8, description, align='C', split_only=True)
        for line in lines:
            pdf.cell(0, 8, line, align='C', ln=True)
        pdf.ln(5)
    
    # Number of steps and ingredients - on separate lines
    pdf.set_font('DejaVu', '', 12)
    pdf.cell(0, 8, f"Number of steps: {len(video_content.steps)}", ln=True)
    pdf.cell(0, 8, f"Number of ingredients: {len(video_content.materials_or_ingredients)}", ln=True)
    pdf.ln(15)
    
    # Ingredients header
    pdf.set_font('DejaVu', 'B', 16)
    pdf.cell(0, 10, "Ingredients:", ln=True)
    pdf.ln(5)
    
    # Split ingredients into two columns with proper spacing
    total_ingredients = len(video_content.materials_or_ingredients)
    mid_point = (total_ingredients + 1) // 2
    col_width = pdf.w / 2 - 20
    
    pdf.set_font('DejaVu', '', 12)
    start_x = pdf.get_x()
    start_y = pdf.get_y()
    
    # Left column
    for i, item in enumerate(video_content.materials_or_ingredients[:mid_point]):
        pdf.set_xy(start_x, start_y + i * 8)
        pdf.cell(col_width, 8, f"- {clean_text_for_pdf(item)}")
    
    # Right column
    for i, item in enumerate(video_content.materials_or_ingredients[mid_point:]):
        pdf.set_xy(start_x + pdf.w/2, start_y + i * 8)
        pdf.cell(col_width, 8, f"- {clean_text_for_pdf(item)}")
    
    # Move cursor past ingredients with proper spacing
    pdf.set_xy(start_x, start_y + max(mid_point, total_ingredients - mid_point) * 8 + 20)
    
    # Instructions header
    pdf.set_font('DejaVu', 'B', 16)
    pdf.cell(0, 10, "Instructions:", ln=True)
    pdf.ln(10)
    
    # Process each step
    for step in video_content.steps:
        if pdf.get_y() > pdf.h - 60:
            pdf.add_page()
        
        start_y = pdf.get_y()
        
        # Text column width - adjusted to match example
        text_col_width = pdf.w * 0.6 if step.image_path else pdf.w - 20
        
        # Step number and title
        pdf.set_font('DejaVu', 'B', 14)
        pdf.set_xy(pdf.l_margin, start_y)
        pdf.cell(text_col_width, 10, f"{step.number}. {clean_text_for_pdf(step.action)}", ln=True)
        
        # Step explanation with proper spacing
        pdf.set_font('DejaVu', '', 12)
        pdf.set_xy(pdf.l_margin, pdf.get_y() + 2)
        pdf.multi_cell(text_col_width, 8, clean_text_for_pdf(step.explanation))
        
        # Image handling with proper sizing and positioning
        if step.image_path and os.path.exists(step.image_path):
            try:
                image_x = pdf.l_margin + text_col_width + 10
                image_width = pdf.w * 0.35  # Slightly wider than before
                image_height = 50  # Adjusted height to match example
                
                # Calculate image position to align with text
                image_y = start_y
                pdf.image(step.image_path, x=image_x, y=image_y, w=image_width, h=image_height)
            except Exception as e:
                print(f"Error embedding image {step.image_path}: {e}")
        
        # Add proper spacing between steps
        current_y = pdf.get_y()
        if step.image_path:
            current_y = max(current_y, start_y + image_height)
        pdf.set_y(current_y + 15)

    output_path = f"output/{job_id}.pdf"
    pdf.output(output_path)
    return output_path 