import os
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk

def create_icon():
    """Create a music-focused icon for Music Concierge SOB Checklists"""
    # Create a 32x32 pixel image with transparent background
    size = 32
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle with gradient effect
    draw.ellipse([2, 2, 30, 30], fill='#1e1e1e', outline='#0078d4', width=2)
    
    # Musical notes - main focus
    # First note (eighth note)
    draw.ellipse([6, 12, 10, 16], fill='#4fc3f7')  # Note head
    draw.rectangle([9, 8, 11, 20], fill='#4fc3f7')  # Stem
    draw.rectangle([11, 8, 16, 10], fill='#4fc3f7')  # Flag
    
    # Second note (quarter note)
    draw.ellipse([14, 16, 18, 20], fill='#00c853')  # Note head
    draw.rectangle([17, 10, 19, 20], fill='#00c853')  # Stem
    
    # Third note (smaller)
    draw.ellipse([20, 14, 23, 17], fill='#ff9800')  # Note head
    draw.rectangle([22, 8, 24, 17], fill='#ff9800')  # Stem
    
    # Musical staff lines
    for y in range(8, 24, 3):
        draw.line([4, y, 28, y], fill='#404040', width=1)
    
    # Treble clef symbol (simplified)
    draw.arc([22, 6, 28, 12], start=0, end=180, fill='#0078d4', width=2)
    draw.ellipse([24, 10, 26, 12], fill='#0078d4')
    
    # Small musical notes decoration
    draw.ellipse([4, 4, 6, 6], fill='#4fc3f7')
    draw.ellipse([26, 22, 28, 24], fill='#00c853')
    
    return img

def save_icon():
    """Save the icon as .ico file"""
    try:
        icon_img = create_icon()
        # Save as ICO file
        icon_img.save('music_concierge_icon.ico', format='ICO', sizes=[(32, 32)])
        print("Music-focused icon created successfully!")
        return True
    except Exception as e:
        print(f"Error creating icon: {e}")
        return False

if __name__ == "__main__":
    save_icon()
