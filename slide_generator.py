import os
import textwrap
import yaml
from PIL import Image, ImageDraw, ImageFont

def load_infra():
    with open("infrastructure.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def create_slide(term, definition, example, tag, origin="N/A", synonyms="N/A"):
    infra = load_infra()
    
    # 1. Setup Canvas (Red/Black)
    width, height = 1920, 1080
    background_color = (0, 0, 0)      # Pure Black
    title_color = (255, 0, 0)         # Bright Red
    text_color = (200, 200, 200)      # Light Grey
    label_color = (150, 0, 0)         # Dark Red for labels
    
    img = Image.new('RGB', (width, height), color=background_color)
    draw = ImageDraw.Draw(img)

    try:
        font_path = "arial.ttf" 
        title_font = ImageFont.truetype(font_path, 110)
        tag_font = ImageFont.truetype(font_path, 40)
        body_font = ImageFont.truetype(font_path, 45)
        label_font = ImageFont.truetype("arialbd.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        tag_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        label_font = ImageFont.load_default()

    margin_left = 100
    current_y = 80 

    # TITLE & TAG
    draw.text((margin_left, current_y), term, font=title_font, fill=title_color)
    current_y += 130
    draw.text((margin_left, current_y), f"[{tag.upper()}]", font=tag_font, fill=text_color)
    current_y += 80
    
    draw.line([(margin_left, current_y), (width-100, current_y)], fill=label_color, width=3)
    current_y += 50

    # DEFINITION
    draw.text((margin_left, current_y), "DEFINITION", font=label_font, fill=label_color)
    current_y += 50
    for line in textwrap.wrap(definition, width=60):
        draw.text((margin_left, current_y), line, font=body_font, fill=text_color)
        current_y += 55
    current_y += 40

    # ORIGIN
    if origin and origin != "N/A":
        draw.text((margin_left, current_y), "ORIGIN", font=label_font, fill=label_color)
        current_y += 50
        draw.text((margin_left, current_y), origin, font=body_font, fill=text_color)
        current_y += 90

    # EXAMPLES
    draw.text((margin_left, current_y), "EXAMPLES / USAGE", font=label_font, fill=label_color)
    current_y += 50
    ex_text = f"{example}"
    if synonyms and synonyms != "N/A":
        ex_text = f"Synonyms: {synonyms}\n" + ex_text
    
    for line in textwrap.wrap(ex_text, width=60):
        draw.text((margin_left, current_y), line, font=body_font, fill=text_color)
        current_y += 55

    # SAVE
    output_dir = infra['directories']['flashcards']
    os.makedirs(output_dir, exist_ok=True)
    safe_name = term.replace('"', '').replace("'", "").replace("?", "")
    output_path = os.path.join(output_dir, f"{safe_name}.png")
    img.save(output_path)
    print(f"🖼️ Slide created: {output_path}")
    return output_path