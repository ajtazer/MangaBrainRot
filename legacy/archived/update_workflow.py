#!/usr/bin/env python3
import json

# Read the workflow
with open('/Users/tazer/Desktop/n8n/BrainRotMangaYOOOANTRIX.json', 'r') as f:
    workflow = json.load(f)

# New BGM library code
new_js_code = '''const message = $input.first().json.message.text;
const match = message.match(/mangadex\\.org\\/chapter\\/([a-f0-9-]+)/i);

if (!match) throw new Error('Could not extract chapter ID');

// --- BGM LIBRARY (70 tracks - Anime + Trending + Classics) ---
const allBgmTracks = [
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Shinzou%20wo%20Sasageyo.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Guren%20no%20Yumiya.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/The%20Rumbling.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Barricades.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Gurenge.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Homura.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Zankyou%20Sanka.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Kaikai%20Kitan.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Specialz.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/KICK%20BACK.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Fight%20Song.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/LEveL.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/SPARK-AGAIN.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Unravel.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Black%20Catcher.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Blue%20Bird.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Silhouette.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Again.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Crossing%20Field.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Sparkle.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Nandemonaiya.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Idol.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Racing%20Into%20The%20Night.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Cry%20Baby.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Brave%20Shine.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/APT.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Espresso.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Beautiful%20Things.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Birds%20of%20a%20Feather.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Taste.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Too%20Sweet.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/I%20Like%20The%20Way%20You%20Kiss%20Me.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Million%20Dollar%20Baby.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Not%20Like%20Us.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Starboy.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Popular.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/One%20Of%20The%20Girls.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Paint%20The%20Town%20Red.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Fukashigi%20no%20Carte.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Daylight.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Ecstasy.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Metamorphosis.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Close%20Eyes.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Murder%20In%20My%20Mind.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/MONTERO.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Dancin%20Krono%20Remix.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Industry%20Baby.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Money.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Summertime%20Sadness.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Stay.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Heat%20Waves.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Blinding%20Lights.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Sunflower.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Levitating.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Beggin.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Cradles.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Play%20Date.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Cupid%20Twin%20Version.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Until%20I%20Found%20You.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Romantic%20Homicide.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Mockingbird.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Without%20Me.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/A%20Cruel%20Angels%20Thesis.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Here%20With%20Me.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Sweater%20Weather.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/After%20Dark.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Little%20Dark%20Age.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Glimpse%20of%20Us.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Die%20For%20You.mp3",
  "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/bgm/Before%20You%20Go.mp3"
];

// Random BGM selection
const bgmUrl = allBgmTracks[Math.floor(Math.random() * allBgmTracks.length)];
const bgmName = decodeURIComponent(bgmUrl.split('/').pop().replace('.mp3',''));
const outroUrl = "https://pub-3edc2a55a5af4b14b554c8ed89ceadb7.r2.dev/outro.jpg";

return [{
  json: {
    chapterId: match[1],
    chatId: String($input.first().json.message.chat.id),
    bgmUrl: bgmUrl,
    bgmName: bgmName,
    outroUrl: outroUrl
  }
}];'''

# Find and update the "Extract Chapter ID" node
for node in workflow['nodes']:
    if node.get('name') == 'Extract Chapter ID':
        node['parameters']['jsCode'] = new_js_code
        print(f"✅ Updated 'Extract Chapter ID' node")
        break

# Save the workflow
with open('/Users/tazer/Desktop/n8n/BrainRotMangaYOOOANTRIX.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("✅ Workflow saved!")
