PROJECT: "Slim legs at 45 - Animated AI" (ORA, claymation stop-motion style ad, 9:16, 1080x1920)

INPUTS
1. Audio track: the ElevenLabs voiceover. It is the clock: every shot starts on the first words of its line (table below).
2. Clips: 27 Higgsfield clips (Kling 3.0, silent). Filenames are hf_<date>_<time>_<job id>.mp4: match each file to its shot by the job id prefix in the table, not by upload order (26 and 27 were rendered at the same time and may be swapped in upload order). If any clip is not 1080x1920, scale it to 1080x1920.
3. One screenshot of an inspo ad. It is a STYLE REFERENCE ONLY for the big caption (e.g. "DIMPLING LESS OBVIOUS"), used on shots 2-27. Ignore everything else in it: small grey labels, the character, footage, framing and audio. Do not add those labels.

SHOT LIST (VO line = what the voice says during the shot; the first words are the anchor)
| Shot | VO line | Clip |
|---|---|---|
| 1 | "I accidentally slimmed my legs at 45. And I wasn't even trying." | hf ...7ef00 |
| 2 | "Last month, my sister Jen calls me." | hf ...1a891 |
| 3 | "'Hey, they sent me two pouches of these strawberry gummies instead of one. You want the extra?'" (TELEPHONE EFFECT) | hf ...0efdd |
| 4 | "I said sure. Free candy. I didn't even ask what it was for." | hf ...bdd6b |
| 5 | "I've had heavy legs since my second baby." | hf ...86a4d |
| 6 | "Thighs that rub when I walk." | hf ...d7650 |
| 7 | "Cottage cheese all over the front of them." | hf ...a59e0 |
| 8 | "I'd tried everything. Squats, creams, dry brushing, that dandelion tea. Nothing moved." | hf ...ca173 |
| 9 | "So I'd given up. I wasn't trying anything anymore." | hf ...36554 |
| 10 | "I just ate one every morning when I got to work, because it tasted like strawberry candy." | hf ...dde31 |
| 11 | "Week one, my legs stopped feeling heavy at night. I blamed the weather." | hf ...d6e09 |
| 12 | "Week two, my jeans slid right over my thighs. I thought they'd stretched." | hf ...d17a2 |
| 13 | "Week three, a coworker asked if I'd started running. I haven't run since 1998." | hf ...8a2e5 |
| 14 | "Day thirty, I put on shorts. Shorts. And the cottage cheese on my thighs was gone." | hf ...c08b1 |
| 15 | "So I finally read the pouch. It's called Ora. And it's not candy. It's a lymphatic drainage gummy." | hf ...eea27 |
| 16 | "Here's what was going on. After forty, the tiny vessels in your legs start leaking." | hf ...11e12 |
| 17 | "Fluid and waste seep into your thighs every day, and your lymph is too slow to haul it back out." | hf ...2cba9 |
| 18 | "So it sits there and pushes up through your skin. That's the cottage cheese. It was never fat. It was sludge." | hf ...d1dd8 |
| 19 | "Butcher's broom gets your veins squeezing again." | hf ...7f8c6 |
| 20 | "Pine bark opens the tiniest vessels so the sludge can drain." | hf ...6fb19 |
| 21 | "Centella firms the skin it stretched out." | hf ...77ee8 |
| 22 | "And hesperidin seals the leaks so it never floods back in." | hf ...86da6 |
| 23 | "So I called Jen. 'Have you seen your legs lately?'" | hf ...f79d8 |
| 24 | "She goes, 'Why do you think I kept the first pouch?'" (TELEPHONE EFFECT) | hf ...a6bce |
| 25 | "Oh, and that extra pouch? It wasn't a mistake. It's their buy one, get one free. Every order comes with two." | hf ...318d8 |
| 26 | "So here's my advice. Get yours. Keep one. Give the other one to your sister." | hf ...8e611 |
| 27 | "One gummy a day. Sixty-day money-back guarantee. Link below." | hf ...1492d |

The VO wording must match these lines word for word; if the transcript differs, tell me before cutting.

CLIP LENGTHS
- The clips were made longer than their lines on purpose. Cut the end of each clip to fit its line; never speed a clip up.
- If any clip is still shorter than its line, do NOT slow it below 0.8x or freeze it: stop and tell me which shot and by how much, and I will regenerate it at the right length.
- Keep every shot as its own cut (no merging): use per-shot min_shot so short shots (2, 5, 6, 7, 19, 21) stay on screen.
- Keep pauses between lines short (about 0.15 s); do not stretch clips to fill long pauses.
- Shot 8 is a 2x2 split screen: keep the whole frame, do not crop or zoom.
- Shots 16-22 are the inside-the-body cutaways: use the part of each clip where the action happens (sludge leaking in 16-18, vein squeezing in 19, capillaries opening in 20, bands tightening in 21, cracks sealing in 22).

TELEPHONE EFFECT (shots 3 and 24 only)
- Lines 3 and 24 are Jen speaking on the phone. Apply a phone filter to the VO for exactly those two lines: band-pass about 300-3400 Hz, light compression, slight mid boost, no added noise.
- Only the part inside Jen's quote gets the effect: in shot 24, "She goes," stays normal and the effect starts on "Why do you think...". Shot 3 is the full line.
- Keep the filtered lines at the same perceived loudness as the rest.

HOOK CARD (shot 1 only)
- White rounded card, ~90% of the width, centred horizontally, placed in the MIDDLE of the frame (around 40-60% of the height). Bold condensed font, Title Case. Line 1 black, line 2 red, ending with the 💀 emoji.
- Text, on two lines (no slash or separator shown on screen):
  Line 1 (black): I Accidentally Slimmed My Legs
  Line 2 (red):   At 45 💀
- It must NOT cover her face at any point in shot 1 (she turns side to side and lifts her hands to her face). Check every frame; if the face would overlap, move the card down (over her torso/shorts), never up over her face.
- On screen from 0:00 until the cut into shot 2, then gone for the rest of the video.
- No captions during shot 1 (the VO line is the hook itself); captions start at shot 2.

CAPTIONS (shots 2-27; copy the big caption style in the screenshot, e.g. "DIMPLING LESS OBVIOUS")
- Bold condensed sans-serif (Impact-like), ALL CAPS, white with a thin dark outline and a soft drop shadow, no box behind it.
- One key word per chunk in yellow (as "OBVIOUS" in the screenshot). Always yellow: ORA, SLUDGE, COTTAGE CHEESE, 45, the ingredient names (BUTCHER'S BROOM, PINE BARK, CENTELLA, HESPERIDIN), FREE, SIXTY-DAY.
- 2-3 words per chunk, one line, centred, no punctuation.
- Position: lower-middle, about 74% of the frame height, as in the screenshot. Move it up per shot when it would cover a face, her thighs in the leg shots (6, 7, 12, 14), the gummy (10), the pouch label (15, 24-27), or the action in the cutaways (16-22).
- Caption text = the script above, exact spelling ("Ora", "Jen", "1998", "butcher's broom", "pine bark", "centella", "hesperidin", "sixty-day").

NO OTHER TEXT OVERLAYS besides the hook card (no week labels, no arrows, no X or check marks, no offer badge).

AUDIO
- Voice = the ElevenLabs track. No music and no SFX unless I send them.
- Final loudness -14 LUFS; run the usual QC and check every cut, caption, the hook card (face never covered) and both telephone-effect lines frame by frame before calling it done.
