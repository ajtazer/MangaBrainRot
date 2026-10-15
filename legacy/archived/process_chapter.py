#!/usr/bin/env python3
"""
Manga Chapter to Video Reel Generator

Downloads manga chapters from MangaDex, extracts text using OCR,
generates voiceover using TTS, and compiles into a video reel.
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

import requests
import edge_tts
from PIL import Image


# Configuration
MANGADEX_API_URL = "https://api.mangadex.org"
OUTPUT_DIR = Path("output")


def download_chapter(chapter_id: str) -> list[Path]:
    """Downloads pages of a chapter from MangaDex.
    
    Args:
        chapter_id: MangaDex chapter UUID
        
    Returns:
        List of paths to downloaded images
    """
    print(f"[1/4] Fetching chapter {chapter_id} metadata...")
    
    # Get MangaDex Home Server URL
    at_home_url = f"{MANGADEX_API_URL}/at-home/server/{chapter_id}"
    
    try:
        r = requests.get(at_home_url, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: Failed to get chapter data: {e}")
        return []
    
    data = r.json()
    base_url = data["baseUrl"]
    chapter_hash = data["chapter"]["hash"]
    filenames = data["chapter"]["data"]
    
    chapter_dir = OUTPUT_DIR / chapter_id
    chapter_dir.mkdir(parents=True, exist_ok=True)
    
    image_paths = []
    total = len(filenames)
    
    print(f"[1/4] Downloading {total} pages...")
    for idx, filename in enumerate(filenames, 1):
        local_path = chapter_dir / filename
        
        if not local_path.exists():
            image_url = f"{base_url}/data/{chapter_hash}/{filename}"
            try:
                img_r = requests.get(image_url, timeout=60)
                img_r.raise_for_status()
                local_path.write_bytes(img_r.content)
                print(f"  Downloaded page {idx}/{total}")
            except requests.RequestException as e:
                print(f"  WARNING: Failed to download {filename}: {e}")
                continue
        else:
            print(f"  Page {idx}/{total} already exists, skipping...")
        
        image_paths.append(local_path)
    
    print(f"[1/4] Downloaded {len(image_paths)}/{total} pages successfully")
    return image_paths


def ocr_pages(image_paths: list[Path]) -> list[tuple[Path, str]]:
    """Extracts text from manga pages using Tesseract OCR.
    
    Args:
        image_paths: List of image file paths
        
    Returns:
        List of (image_path, extracted_text) tuples
    """
    import pytesseract
    import re
    
    print("[2/4] Using Tesseract OCR for English text...")
    
    results = []
    total = len(image_paths)
    
    # Tesseract config for better manga/comic text detection
    # PSM 6 = Assume a single uniform block of text
    # PSM 11 = Sparse text. Find as much text as possible in no particular order
    # PSM 12 = Sparse text with OSD
    custom_config = r'--oem 3 --psm 11'
    
    print(f"[2/4] OCR processing {total} pages...")
    for idx, img_path in enumerate(image_paths, 1):
        try:
            # Open image and convert to RGB for better OCR
            img = Image.open(img_path).convert('RGB')
            
            # Enhance image for better OCR (increase contrast)
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(img)
            img_enhanced = enhancer.enhance(1.5)  # Increase contrast by 50%
            
            # Use Tesseract with English language and custom config
            text = pytesseract.image_to_string(img_enhanced, lang='eng', config=custom_config)
            text = text.strip()
            
            # Clean up the text - keep only letters, numbers, spaces, and basic punctuation
            # Keep: letters, numbers, spaces, commas, periods, question marks, exclamation, apostrophes
            text = re.sub(r"[^a-zA-Z0-9\s,.'?!]", '', text)
            # Remove excessive whitespace
            text = ' '.join(text.split())
            
            # Include ALL pages, even without text (text will be empty string)
            results.append((img_path, text))
            
            if text:
                display_text = text[:50] + '...' if len(text) > 50 else text
                print(f"  Page {idx}/{total}: '{display_text}'")
            else:
                print(f"  Page {idx}/{total}: (no text - will show image only)")
        except Exception as e:
            # Still include the page even if OCR fails
            results.append((img_path, ''))
            print(f"  WARNING: OCR failed for page {idx}: {e} (will show image only)")
    
    text_count = sum(1 for _, t in results if t)
    print(f"[2/4] Processed {total} pages ({text_count} with text, {total - text_count} image-only)")
    return results


def detect_language(text: str) -> str:
    """Detects if text is primarily Japanese or English.
    
    Returns:
        'ja' for Japanese, 'en' for English
    """
    # Count Japanese characters (hiragana, katakana, kanji)
    japanese_chars = 0
    for char in text:
        code = ord(char)
        # Hiragana: 3040-309F, Katakana: 30A0-30FF, CJK: 4E00-9FFF
        if (0x3040 <= code <= 0x309F or 
            0x30A0 <= code <= 0x30FF or 
            0x4E00 <= code <= 0x9FFF):
            japanese_chars += 1
    
    # If more than 30% Japanese characters, treat as Japanese
    if len(text) > 0 and japanese_chars / len(text) > 0.3:
        return 'ja'
    return 'en'


VOICE_MAP = {
    'ja': 'ja-JP-NanamiNeural',   # Japanese female voice
    'en': 'en-US-ChristopherNeural',  # English male voice
}


async def generate_audio_files(
    ocr_results: list[tuple[Path, str]], 
    voice: str | None = None
) -> list[tuple[Path, Path | None]]:
    """Generates audio files from extracted text using Edge TTS.
    
    Args:
        ocr_results: List of (image_path, text) tuples
        voice: Voice model to use (auto-detect if None)
        
    Returns:
        List of (image_path, audio_path or None) tuples
    """
    # Filter only pages with text for language detection
    texts_with_content = [text for _, text in ocr_results if text]
    
    # Auto-detect language from first few texts if voice not specified
    if voice is None or voice == 'auto':
        sample_text = ' '.join(texts_with_content[:5]) if texts_with_content else ''
        detected_lang = detect_language(sample_text) if sample_text else 'en'
        voice = VOICE_MAP.get(detected_lang, VOICE_MAP['en'])
        print(f"[3/4] Auto-detected language: {detected_lang.upper()}, using voice: {voice}")
    
    print(f"[3/4] Generating audio for {len(ocr_results)} pages...")
    
    results = []
    total = len(ocr_results)
    audio_count = 0
    
    for idx, (img_path, text) in enumerate(ocr_results, 1):
        if not text:
            # No text - include page with no audio (will use default duration)
            results.append((img_path, None))
            print(f"  Page {idx}/{total}: (image only, no audio)")
            continue
            
        audio_path = img_path.parent / f"audio_{idx:03d}.mp3"
        
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(audio_path))
            results.append((img_path, audio_path))
            audio_count += 1
            print(f"  Generated audio {idx}/{total}")
        except Exception as e:
            # If TTS fails, still include the page without audio
            results.append((img_path, None))
            print(f"  WARNING: TTS failed for page {idx}: {e} (will show image only)")
    
    print(f"[3/4] Generated {audio_count} audio files, {total - audio_count} image-only pages")
    return results


def create_video(
    image_audio_pairs: list[tuple[Path, Path | None]], 
    output_path: Path,
    bgm_path: Path | None = None,
    default_duration: float = 3.0
):
    """Composes video from images and audio.
    
    Args:
        image_audio_pairs: List of (image_path, audio_path or None) tuples
        output_path: Path for output video file
        bgm_path: Optional path to background music file
        default_duration: Duration for pages without audio (default 3s)
    """
    # Lazy import to avoid loading heavy library on startup
    from moviepy.editor import (
        ImageClip, 
        AudioFileClip, 
        concatenate_videoclips,
        CompositeAudioClip
    )
    
    print(f"[4/4] Creating video from {len(image_audio_pairs)} clips...")
    
    clips = []
    
    for idx, (img_path, audio_path) in enumerate(image_audio_pairs, 1):
        try:
            # Determine duration based on audio or default
            if audio_path and audio_path.exists():
                audio = AudioFileClip(str(audio_path))
                duration = audio.duration + 0.5  # Add slight pause
            else:
                audio = None
                duration = default_duration  # Default duration for image-only pages
            
            # Pre-resize image using PIL to avoid cv2 issues
            img = Image.open(img_path)
            
            # Convert to RGB (remove alpha channel if present)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background and paste image on it
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            if img.width != 1080:
                # Calculate new height maintaining aspect ratio
                new_height = int(img.height * (1080 / img.width))
                img = img.resize((1080, new_height), Image.Resampling.LANCZOS)
            
            # Save processed image to temp location
            resized_path = img_path.parent / f"processed_{img_path.stem}.jpg"
            img.save(resized_path, 'JPEG', quality=95)
            img_to_use = str(resized_path)
            
            # Create Image Clip
            clip = ImageClip(img_to_use).set_duration(duration)
            if audio:
                clip = clip.set_audio(audio)
            
            clips.append(clip)
            print(f"  Prepared clip {idx}/{len(image_audio_pairs)}")
        except Exception as e:
            print(f"  WARNING: Failed to create clip {idx}: {e}")
    
    if not clips:
        print("ERROR: No clips created, cannot produce video")
        return
    
    print("[4/4] Concatenating clips...")
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Add background music if available
    if bgm_path and bgm_path.exists():
        print("[4/4] Adding background music...")
        try:
            bgm = AudioFileClip(str(bgm_path))
            
            # Loop or trim BGM to match video duration
            if bgm.duration < final_video.duration:
                # Loop the BGM
                loops_needed = int(final_video.duration / bgm.duration) + 1
                from moviepy.editor import concatenate_audioclips
                bgm = concatenate_audioclips([bgm] * loops_needed)
            
            bgm = bgm.subclip(0, final_video.duration)
            bgm = bgm.volumex(0.15)  # Lower volume
            
            # Mix with original audio
            if final_video.audio:
                final_audio = CompositeAudioClip([final_video.audio, bgm])
                final_video = final_video.set_audio(final_audio)
        except Exception as e:
            print(f"  WARNING: Failed to add BGM: {e}")
    
    print(f"[4/4] Rendering video to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    final_video.write_videofile(
        str(output_path), 
        fps=24,
        codec='libx264',
        audio_codec='aac',
        logger='bar'  # Show progress bar
    )
    
    # Cleanup
    final_video.close()
    for clip in clips:
        clip.close()
    
    print(f"[4/4] Video saved to: {output_path}")


async def process_chapter(chapter_id: str, voice: str, bgm_path: Path | None = None):
    """Main processing pipeline for a manga chapter.
    
    Args:
        chapter_id: MangaDex chapter UUID
        voice: TTS voice to use
        bgm_path: Optional path to background music
    """
    print(f"\n{'='*60}")
    print(f"Processing Chapter: {chapter_id}")
    print(f"{'='*60}\n")
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Download chapter images
    image_paths = download_chapter(chapter_id)
    if not image_paths:
        print("\nERROR: No images downloaded. Exiting.")
        return
    
    # Step 2: OCR all pages (returns all pages, some may have empty text)
    ocr_results = ocr_pages(image_paths)
    
    # Step 3: Generate audio for pages with text (returns all pages, some may have None audio)
    image_audio_pairs = await generate_audio_files(ocr_results, voice)
    
    # Step 4: Create video
    output_path = OUTPUT_DIR / f"{chapter_id}_reel.mp4"
    create_video(image_audio_pairs, output_path, bgm_path)
    
    print(f"\n{'='*60}")
    print("DONE!")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert a manga chapter to a video reel with voiceover",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 process_chapter.py abc123-uuid-here
  python3 process_chapter.py abc123-uuid-here --voice en-GB-SoniaNeural
  python3 process_chapter.py abc123-uuid-here --bgm background_music.mp3
        """
    )
    parser.add_argument(
        "chapter_id", 
        help="MangaDex Chapter UUID"
    )
    parser.add_argument(
        "--voice", 
        default="auto", 
        help="Edge TTS voice or 'auto' for language detection (default: auto)"
    )
    parser.add_argument(
        "--bgm", 
        type=Path,
        default=Path("bgm.mp3") if Path("bgm.mp3").exists() else None,
        help="Path to background music file (default: bgm.mp3 if exists)"
    )
    
    args = parser.parse_args()
    
    # Run the async pipeline
    asyncio.run(process_chapter(args.chapter_id, args.voice, args.bgm))


if __name__ == "__main__":
    main()
