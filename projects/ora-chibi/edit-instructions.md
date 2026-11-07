PROJECT: "One gummy a day" (ORA, chibi Pixar 3D animated ad, 9:16, 1080x1920)

INPUTS
1. Audio track: the ElevenLabs voiceover. It is the clock: every shot starts on the first words of its line (table below).
2. Clips (19 files):
   - 17 Higgsfield clips (silent). Filenames are hf_<date>_<time>_<job id>.mp4: match each file to its shot by the job id prefix in the table, not by upload order. Shot 1 is 720x1280: scale it up to 1080x1920 like the others.
   - REUSE_1.mp4 (19.7 s): ONE clip that covers shots 15 to 19 together.
   - REUSE_2.mp4 (6.1 s): ONE clip that covers shots 23 and 24 together.
   Both REUSE files are 720x1288: scale/crop to 1080x1920 (cut the extra 8 px, keep the centre). Their audio tracks are silent: mute them.
3. One screenshot of an inspo ad. It is a STYLE REFERENCE ONLY for (a) the look of the hook card, which appears in shot 1 only, and (b) the caption style, used on every shot. Nothing else in it applies: not its character, footage, framing or audio.

SHOT LIST (VO line = what the voice says during the shot; the first words are the anchor)
| Shot | VO line | Clip |
|---|---|---|
| 1 | "Here's what happens when you take one Ora gummy every single day." | hf ...4685f |
| 2 | "At first, nothing crazy. You take one gummy in the morning," | hf ...d8986 |
| 3 | "you go about your day, and honestly, you forget about it." | hf ...c55b8 |
| 4 | "Then after about a week, something small." | hf ...b45cf |
| 5 | "You get home, you kick your shoes off, and there's no sock line printed into your ankles. Your legs just feel like legs." | hf ...3c377 |
| 6 | "After a few weeks, you start noticing more." | hf ...283f6 |
| 7 | "Your evenings feel different. No heaviness by 6:00 p.m." | hf ...92e7d |
| 8 | "No need to put your feet up." | hf ...ef00c |
| 9 | "Your thighs look smoother in the mirror." | hf ...45812 |
| 10 | "Your lower legs look less puffy than they used to." | hf ...435d2 |
| 11 | "Then one day, it really hits you." | hf ...2bf8c |
| 12 | "You catch your reflection at night, at the end of a long day, and your legs look the way they used to look in the morning." | hf ...55fa5 |
| 13 | "Tighter, less swollen, the dimpling less obvious." | hf ...f54e0 |
| 14 | "And you stop hiding them." | hf ...94f1e |
| 15 | "That's because Ora doesn't squeeze your legs from the outside. It works on the vessel itself." | REUSE_1, 0.00-4.47 s |
| 16 | "Butcher's broom supports venous tone." | REUSE_1, 4.47-6.63 s |
| 17 | "Hesperidin supports capillary strength, so less sludge and gunk leaks into the tissue." | REUSE_1, 6.63-11.23 s |
| 18 | "Maritime pine bark supports microcirculation." | REUSE_1, 11.23-14.47 s |
| 19 | "Centella asiatica supports the connective tissue, which is what cellulite dimpling actually is." | REUSE_1, 14.47-19.70 s |
| 20 | "And the best part? You didn't diet." | hf ...8850a |
| 21 | "You didn't change your routine." | hf ...861d6 |
| 22 | "You didn't wear anything." | hf ...f6adb |
| 23 | "You just took one gummy a day." | REUSE_2, 0.00-1.70 s (the single gummy) |
| 24 | "Get 60% off sitewide with the Black Friday offer, link below." | REUSE_2, 1.70-6.07 s (the pouch) |

The VO wording must match these lines word for word; if the transcript differs, tell me before cutting.

REUSE CLIPS
- REUSE_1 has 5 sections that match shots 15-19 (split-screen outside vs inside, butcher's broom, hesperidin vessel, pine bark capillaries, centella skin). Cut it at the section times above so each section starts on its own VO line. If a section is shorter than its line, extend it by slowing that section to no less than 0.8x; if it is still short, tell me.
- REUSE_2: the gummy section (shot 23) is only 1.7 s. If line 23 is longer, slow that section to no less than 0.8x and let the cut to the pouch fall on the first word of line 24.
- REUSE_2 has old burned-in text: a round badge "50% OFF SUMMER BODY OFFER" on the left of the pouch and "LINK BELOW" with an arrow at the bottom. The VO says 60% and Black Friday, so COVER the old badge with a new badge in the same spot, same size and style: "60% OFF" / "BLACK FRIDAY OFFER". Keep "LINK BELOW". Put the captions above "LINK BELOW", never on the pouch label.
- REUSE_1 already shows a small "BUTCHER'S BROOM" label in shot 16: keep it.

CLIP LENGTHS (Higgsfield clips)
- Most clips were made longer than their lines on purpose. Cut the end of each clip to fit its line; never speed a clip up.
- If any clip is still shorter than its line, do NOT slow it below 0.8x or freeze it: stop and tell me which shot and by how much (shot 5 is the most likely: an 8 s clip for a long line).
- Keep every shot as its own cut (no merging): use per-shot min_shot so short shots (8, 14, 16, 18, 21, 22, 23) stay on screen.
- Shot 4: use the part where she pulls the boot off and leans back. Shot 5: use the part where the sock comes off and she wiggles her toes.

HOOK (shot 1 only; copy the look of the card in the screenshot)
- White rounded card at the top (about 5% to 21% of the height), ~90% of the width, centred. Bold condensed font, Title Case. Line 1 black, line 2 red, ending with the 💀 emoji.
- Text, on two lines (no slash or separator shown on screen):
  Line 1 (black): Here's What 1 Gummy A Day
  Line 2 (red):   Does To Your Legs 💀
- On screen from 0:00 until the cut into shot 2, then gone for the rest of the video.

CAPTIONS (every shot; copy the caption style in the screenshot, e.g. "HERE'S WHAT HAPPENS")
- Bold condensed sans-serif (Impact-like), ALL CAPS, white with a thin dark outline and a soft drop shadow, no box behind it.
- One key word per chunk in yellow (as "HAPPENS" in the screenshot). Always yellow: ORA, GUMMY, the ingredient names, 60%.
- 2-3 words per chunk, one line, centred, no punctuation.
- Position: lower-middle, about 74% of the frame height, as in the screenshot. Move it up per shot when it would cover her face, her legs/ankles in the leg shots (5, 10, 13), the gummy, the pouch, or the "BUTCHER'S BROOM" label.
- Captions also run under the hook card during shot 1.
- Caption text = the script above, exact spelling ("Ora", "butcher's broom", "hesperidin", "maritime pine bark", "centella asiatica", "6:00 p.m.", "60%").

NO OTHER TEXT OVERLAYS (no week labels, no arrows, no X or check marks), except the new 60% badge on shot 24 and the text already in the REUSE clips.

AUDIO
- Voice = the ElevenLabs track. No music and no SFX unless I send them.
- Final loudness -14 LUFS; run the usual QC and check every cut, caption, the hook card and the shot 24 badge frame by frame before calling it done.
