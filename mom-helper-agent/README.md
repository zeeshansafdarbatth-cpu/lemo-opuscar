# Her own assistant

A phone number your mother calls whenever she wants something done. She asks in her own words, in Punjabi or Urdu, and the assistant does it. It works for her: she is in charge, and what she tells it stays private.

```
"Zeeshan se baat karao."               → puts her straight through to Zeeshan, no dialing
"Nalka tapak raha hai."                → calls Bashir the plumber, keeps trying, backups if needed,
                                          then rings her back: "Bashir said yes, he's coming"
"Mujhe paanch baje yaad dilana        → phones her at five to remind her
 Nasreen ko phone karna hai."
"Yaad rakhna, sone ki choorian         → writes it in her private notebook; later:
 neeli peti mein rakhi hain."            "Where did I put my bangles?" → "In the blue trunk, Ammi."
"Aaj mausam kaisa hai?" / "Namaz ka    → looks it up and tells her
 waqt?" / "Khabrein sunao."
"Ek aadmi keh raha tha mera inaam      → tells her calmly it sounds like a trick, not to share anything,
 nikla hai, code bata do."              and asks if she'd like her family to know
```

## What she can ask for

- **Talk to someone**: it connects her live to anyone on her list. She never has to remember or dial a number.
- **Get help or someone to come**: driver, maid, nurse, plumber, shop. It texts and calls them, retries when they don't answer, moves to a backup, and **rings her back** with who said yes. She can hang up straight away.
- **Send a message** to someone on her list.
- **Reminders she sets herself**, once or every day or week. It phones her at that time, and she can carry on talking.
- **"Remember this for me"**: a private notebook for where she kept things, names, numbers and recipes. She can ask about any of it later.
- **Questions and news**: weather, prayer times, news, cricket, recipes, religious questions, the meaning of a word. It searches the web for anything current.
- **Just talk**, if that's what she wants.
- **She can also press a key** (1 for the driver, 9 for her son, and so on) instead of speaking.

## Made for her

- **Patient.** It waits longer than usual for her to speak, is happy with short answers, and never rushes her. If she asks the same thing twice, it answers kindly as if for the first time.
- **Her privacy.** The family dashboard shows only what the assistant *did* (who it called, who said yes). Her words, notes and reminders are never shown. Set `share_conversations: true` only if she agrees.
- **She's in charge.** It doesn't report on her, set routines, or nag. Family only hears from it when she asks it to tell them, when nobody answered a request, or in an emergency.

## Safety, without watching her

- It can only call, text or connect people on her list, so a scammer can't get it to call them.
- It never asks for, repeats or passes on PINs, codes, passwords or bank details. It can't place orders or pay for anything.
- If she describes a suspicious call, it tells her it sounds like a trick and offers to tell family. It only does so if she agrees.
- **Emergencies** ("I fell", "chest pain"): it calls her family and nearby helpers all at once and tells her to call the ambulance number.
- If she can't be heard three times in one call, it asks family to ring her.
- Only her phone numbers can use the line, and webhooks are checked against Twilio's signature.

## Her languages: Punjabi and Urdu

The example config is set up for a mother who speaks **Punjabi and Urdu, often mixed**, and helpers who speak Urdu.

**Listening.** Twilio can recognise Urdu (`ur-PK`), but has no Punjabi recogniser for Pakistan. So her Punjabi comes through as rough Urdu text. For example, "میں ڈگ پئی آں" (I fell) may arrive half-misheard. The assistant is told she speaks both, to read what arrives by sound as well as meaning, and to check with a simple yes-or-no question when unsure. Helpers' names are passed to the recogniser as hints, so "Rashid" or "Shazia" is heard correctly more often.

**Speaking.** The assistant always answers her in simple, respectful Urdu written in Urdu script, so a voice can read it aloud. The fixed phrases (greeting, "Rashid said yes", and so on) are already in Urdu in `config.example.yaml`. Each person has a `spoken_name` in Urdu script, so the voice says "راشد" instead of trying to read English letters.

**Her voice: choose one.**
1. **A Twilio voice.** In the Twilio console, under *Voice → Text-to-speech*, check whether your account lists an Urdu voice. If it does, put its name in `mom.voice` and in each helper's `voice`. This is simplest.
2. **ElevenLabs** (more natural, and the choice if Twilio has no Urdu voice). Make an ElevenLabs account, pick or design a warm Urdu voice, and set:
   ```yaml
   settings:
     speech: "elevenlabs"
     elevenlabs_voice_id: "the voice id"
     elevenlabs_model: "eleven_v3"     # check that the model you pick lists Urdu
   ```
   and `ELEVENLABS_API_KEY` in `.env`. Fixed phrases are made once and reused; replies take about a second more. If ElevenLabs ever fails, the line falls back to Twilio's voice rather than going silent.

**Test with her before relying on it.** Do a few practice calls together, in Punjabi and in Urdu, and read the dashboard to see what the recogniser heard. If it often mishears a word she uses, add it to `notes`, e.g. *"When she says 'ڈاکٹر صاحب' she means Dr. Khan."*

## Try it now (no phone account needed)

```bash
pip install -r requirements-dev.txt
python simulate.py --offline     # simple keyword brain, no API key (replies in English; the real brain speaks Urdu)
python simulate.py               # the real Claude brain (needs ANTHROPIC_API_KEY)
```

You type what Mom says; when the agent "calls" a helper you play the helper (1 = coming, 2 = can't, Enter = no answer).

Tests: `pytest`

## Set it up for real

**1. Fill in her details.** Copy `config.example.yaml` to `config.yaml`. Add her numbers and everyone she might want to reach: family, friends, helpers, her doctor's clinic, shops (name, number, what they help with, the language they speak, an optional speed-dial key). Set her `city` for local weather and prayer times. Put anything useful in `notes`.

**2. Get a phone number.** Make a [Twilio](https://www.twilio.com) account and buy a number that can make voice calls and send SMS to Pakistan. Pakistani numbers need ID documents, and some aren't sold to individuals, so a number from another country also works if she can call it cheaply. Then choose her voice (see *Her languages* above).

**3. Get a Claude API key** at [console.anthropic.com](https://console.anthropic.com).

**4. Run the server** somewhere with a public HTTPS address: Render, Railway, Fly.io, or a small VPS.

```bash
cp .env.example .env        # fill it in
pip install -r requirements.txt
set -a; . ./.env; set +a
uvicorn helper_agent.app:app_from_env --factory --host 0.0.0.0 --port 8000 --workers 1
```

Use exactly **one worker**: requests in progress are kept in memory.

**5. Connect Twilio to it.** In the Twilio console, under your number:
- *A call comes in* → Webhook, `POST`, `https://YOUR-ADDRESS/voice/mom/incoming`
- *A message comes in* → Webhook, `POST`, `https://YOUR-ADDRESS/sms/incoming`

**6. Make it easy for her.** Save the number with a big photo and a name she likes, such as "Meri Madadgar" (my helper), or set it as speed dial 1. Sit with her for the first few calls: ask it the weather, set a reminder together, have it call someone. Let her find out what it can do.

## Costs (rough)

- Twilio: a local number costs about $1–15 a month, and calls and texts cost cents each; prices vary a lot by country.
- Claude: about one or two cents per thing she asks, a little more when it searches the web.
- ElevenLabs, if used: a small monthly plan covers a household's calls.

## Good to know

- **Restarting the server forgets help requests in progress.** Her notebook, reminders and the activity log are kept in `data/`. Back that folder up.
- **Helpers should know about the line.** Tell them calls will come from this number, and to press 1 or 2.
- **Voicemail** counts as "no answer", so the agent keeps trying.
- **This is not an emergency service.** In an emergency it alerts family, but she should still call the ambulance number, and it reminds her to.

## Files

| File | What it does |
|---|---|
| `helper_agent/brain.py` | Claude: understands her and decides what to do (the tool loop) |
| `helper_agent/tools.py` | What it can do: connect calls, get help, texts, reminders, notebook |
| `helper_agent/personal.py` | Her private notebook and reminders |
| `helper_agent/dispatcher.py` | Retries, backups, emergencies, calling her back, alerting family |
| `helper_agent/app.py` | The phone line (Twilio webhooks) and the family dashboard |
| `helper_agent/telephony.py` | Twilio calls and texts |
| `helper_agent/voice.py` | How words are spoken: Twilio voice or ElevenLabs |
| `helper_agent/config.py` | Reads `config.yaml` |
| `simulate.py` | Try it in the terminal |
