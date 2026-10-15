#!/usr/bin/env python3
"""
One-time script to download anime/manga BGM from YouTube
Uses yt-dlp (more reliable than RapidAPI)

Requirements:
    pip install yt-dlp
    
Also needs ffmpeg installed:
    Mac: brew install ffmpeg
    Linux: sudo apt install ffmpeg
    Windows: Download from ffmpeg.org
"""

import os
import time
import subprocess
import shutil
from pathlib import Path

# Output directory
MUSIC_DIR = Path(__file__).parent / "music"
MUSIC_DIR.mkdir(exist_ok=True)

# Check if yt-dlp is available
def check_dependencies():
    if not shutil.which("yt-dlp"):
        print("❌ yt-dlp not found! Install with: pip install yt-dlp")
        return False
    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg not found! Install with: brew install ffmpeg")
        return False
    return True

# Song list: (filename, search query)
# 55+ songs - Mix of Viral Trending, Classics & Anime
SONGS = [
    # ═══════════════════════════════════════════════════════════════
    # 🎌 ANIME MUSIC (25 tracks)
    # ═══════════════════════════════════════════════════════════════
    
    # Attack on Titan
    ("Shinzou wo Sasageyo", "Linked Horizon Shinzou wo Sasageyo Attack on Titan"),
    ("Guren no Yumiya", "Linked Horizon Guren no Yumiya Attack on Titan OP1"),
    ("The Rumbling", "SiM The Rumbling Attack on Titan Final Season"),
    ("Barricades", "Hiroyuki Sawano Barricades Attack on Titan"),
    
    # Demon Slayer
    ("Gurenge", "LiSA Gurenge Demon Slayer OP"),
    ("Homura", "LiSA Homura Demon Slayer Mugen Train"),
    ("Zankyou Sanka", "Aimer Zankyou Sanka Demon Slayer Season 2"),
    
    # Jujutsu Kaisen
    ("Kaikai Kitan", "Eve Kaikai Kitan Jujutsu Kaisen OP"),
    ("Specialz", "King Gnu Specialz Jujutsu Kaisen Season 2"),
    
    # Chainsaw Man
    ("KICK BACK", "Kenshi Yonezu KICK BACK Chainsaw Man"),
    ("Fight Song", "Eve Fight Song Chainsaw Man ED"),
    
    # Solo Leveling / Blue Lock / Trending New
    ("LEveL", "SawanoHiroyuki LEveL Solo Leveling OP"),
    ("SPARK-AGAIN", "Aimer SPARK AGAIN Fire Force"),
    ("Unravel", "TK from Ling Tosite Sigure Unravel Tokyo Ghoul"),
    ("Black Catcher", "Vickeblanka Black Catcher Black Clover"),
    
    # Classic Anime Bangers
    ("Blue Bird", "Ikimono Gakari Blue Bird Naruto Shippuden"),
    ("Silhouette", "KANA-BOON Silhouette Naruto Shippuden"),
    ("Again", "YUI Again Fullmetal Alchemist Brotherhood"),
    ("Crossing Field", "LiSA Crossing Field Sword Art Online"),
    
    # Emotional/Chill Anime
    ("Sparkle", "RADWIMPS Sparkle Kimi no Na wa Your Name"),
    ("Nandemonaiya", "RADWIMPS Nandemonaiya Kimi no Na wa"),
    ("Idol", "YOASOBI Idol Oshi no Ko"),
    ("Racing Into The Night", "YOASOBI Yoru ni Kakeru Racing Into The Night"),
    ("Cry Baby", "Official HIGE DANdism Cry Baby Tokyo Revengers"),
    ("Brave Shine", "Aimer Brave Shine Fate Stay Night"),
    
    # ═══════════════════════════════════════════════════════════════
    # 🔥 2024-2025 VIRAL INSTAGRAM/TIKTOK HITS (20 tracks)
    # ═══════════════════════════════════════════════════════════════
    
    # Currently Trending (2024-2025)
    ("APT", "Rose Bruno Mars APT"),
    ("Espresso", "Sabrina Carpenter Espresso"),
    ("Beautiful Things", "Benson Boone Beautiful Things"),
    ("Birds of a Feather", "Billie Eilish Birds of a Feather"),
    ("Taste", "Sabrina Carpenter Taste"),
    ("Too Sweet", "Hozier Too Sweet"),
    ("I Like The Way You Kiss Me", "Artemas I Like The Way You Kiss Me"),
    ("Million Dollar Baby", "Tommy Richman Million Dollar Baby"),
    ("Not Like Us", "Kendrick Lamar Not Like Us"),
    ("Starboy", "The Weeknd Starboy"),
    ("Popular", "The Weeknd Playboi Carti Madonna Popular"),
    ("One Of The Girls", "The Weeknd Jennie Lily Rose Depp"),
    ("Paint The Town Red", "Doja Cat Paint The Town Red"),
    ("Fukashigi no Carte", "Bunny Girl Senpai Fukashigi no Carte"),
    ("Daylight", "David Kushner Daylight"),
    ("Ecstasy", "SUICIDAL IDOL Ecstasy slowed"),
    ("Metamorphosis", "INTERWORLD Metamorphosis"),
    ("Close Eyes", "DVRST Close Eyes"),
    ("Murder In My Mind", "Kordhell Murder In My Mind"),
    ("MONTERO", "Lil Nas X MONTERO Call Me By Your Name"),
    
    # ═══════════════════════════════════════════════════════════════
    # 🎶 EVERGREEN VIRAL CLASSICS (15 tracks)
    # ═══════════════════════════════════════════════════════════════
    
    # TikTok/Reels Evergreen Hits
    ("Dancin Krono Remix", "Aaron Smith Dancin Krono Remix"),
    ("Industry Baby", "Lil Nas X Industry Baby"),
    ("Money", "Lisa Blackpink Money"),
    ("Summertime Sadness", "Lana Del Rey Summertime Sadness remix"),
    ("Stay", "The Kid LAROI Justin Bieber Stay"),
    ("Heat Waves", "Glass Animals Heat Waves"),
    ("Blinding Lights", "The Weeknd Blinding Lights"),
    ("Sunflower", "Post Malone Sunflower Spider-Man"),
    ("Levitating", "Dua Lipa Levitating"),
    ("Beggin", "Maneskin Beggin"),
    ("Cradles", "Sub Urban Cradles"),
    ("Play Date", "Melanie Martinez Play Date"),
    ("Cupid Twin Version", "FIFTY FIFTY Cupid Twin Version sped up"),
    ("Until I Found You", "Stephen Sanchez Until I Found You"),
    ("Romantic Homicide", "d4vd Romantic Homicide"),
    
    # ═══════════════════════════════════════════════════════════════
    # 🎵 AESTHETIC & MEME CLASSICS (10 tracks)
    # ═══════════════════════════════════════════════════════════════
    
    ("Mockingbird", "Eminem Mockingbird"),
    ("Without Me", "Eminem Without Me"),
    ("A Cruel Angels Thesis", "Yoko Takahashi Cruel Angel Thesis Evangelion"),
    ("Here With Me", "d4vd Here With Me"),
    ("Sweater Weather", "The Neighbourhood Sweater Weather"),
    ("After Dark", "Mr Kitty After Dark"),
    ("Little Dark Age", "MGMT Little Dark Age"),
    ("Glimpse of Us", "Joji Glimpse of Us"),
    ("Die For You", "The Weeknd Die For You"),
    ("Before You Go", "Lewis Capaldi Before You Go"),
]


def download_song(filename: str, query: str) -> bool:
    """Download a song from YouTube using yt-dlp"""
    filepath = MUSIC_DIR / f"{filename}.mp3"
    
    if filepath.exists():
        print(f"  ⏭️ Already exists: {filename}.mp3")
        return True
    
    try:
        # yt-dlp command to search and download as MP3
        cmd = [
            "yt-dlp",
            f"ytsearch1:{query}",  # Search YouTube, get first result
            "-x",                   # Extract audio
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", str(filepath),
            "--no-playlist",
            "--quiet",
            "--no-warnings",
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            print(f"  ✅ Downloaded: {filename}.mp3 ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  ❌ Download failed: {result.stderr[:100] if result.stderr else 'Unknown error'}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  ❌ Download timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    print("🎵 Anime & Viral BGM Downloader (yt-dlp)")
    print("=" * 50)
    
    if not check_dependencies():
        print("\n⚠️ Install missing dependencies first!")
        print("  pip install yt-dlp")
        print("  brew install ffmpeg")
        return
    
    print(f"Output: {MUSIC_DIR}")
    print(f"Songs to download: {len(SONGS)}")
    print("=" * 50)
    
    success = 0
    failed = 0
    failed_songs = []
    
    for i, (filename, query) in enumerate(SONGS, 1):
        print(f"\n[{i}/{len(SONGS)}] 🔍 {filename}")
        print(f"  Query: {query}")
        
        if download_song(filename, query):
            success += 1
        else:
            failed += 1
            failed_songs.append(filename)
        
        # Small delay to be nice to YouTube
        time.sleep(1)
    
    print("\n" + "=" * 50)
    print(f"✅ Success: {success}/{len(SONGS)}")
    print(f"❌ Failed: {failed}/{len(SONGS)}")
    
    if failed_songs:
        print(f"\n❌ Failed songs:")
        for song in failed_songs:
            print(f"  - {song}")
    
    print(f"\n📁 Files saved to: {MUSIC_DIR}")
    
    # Generate BGM library code for n8n
    print("\n" + "=" * 50)
    print("📋 Copy this to your n8n Extract Chapter ID node:\n")
    print("const allBgmTracks = [")
    for filename, _ in SONGS:
        safe_filename = filename.replace(" ", "%20")
        print(f'  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/{safe_filename}.mp3",')
    print("];")


if __name__ == "__main__":
    main()
