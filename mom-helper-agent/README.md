# Mom's helper line

One phone number your mother calls instead of dialing her helpers again and again.
She says what she needs, in her own words, and hangs up. The agent does the rest.

```
Ammi calls the helper line:   "My tap is leaking."
Agent:                        "Okay Ammi, I'm calling Bashir now. I'll call you back."   (call ends)

In the background:   texts Bashir → calls Bashir → no answer → waits → calls again
                     → Bashir presses 2 (can't) → texts and calls Zeeshan (backup) → Zeeshan presses 1

Ammi's phone rings:           "Ammi, good news. Zeeshan said yes and will help you."
```

## What it does

- **Understands her.** She speaks normally ("I need a ride to Dr. Khan at five", "the fan isn't working"). Claude works out who should help and writes the message for them. She can also press one key: 1 for the driver, 9 for her son, and so on.
- **Keeps trying, so she doesn't have to.** Each helper gets a text, then up to 3 calls (configurable). Helpers press 1 for yes and 2 for no, or reply to the text. A "no" moves on to the backup right away.
- **Calls her back** with the answer, so she never wonders whether anyone got the message.
- **Family is the safety net.** If nobody says yes, family gets a text and a call. If she can't be heard three times in a row, family is asked to call her.
- **Emergencies** ("I fell", "chest pain"): calls family and nearby helpers all at once, repeatedly, and tells her to call the ambulance number.
- **Remembers today.** She can call back and ask "Is Rashid coming?"
- **Family dashboard** at `/dashboard` shows every request, call and answer, and refreshes itself.
- **Safe by default.** Only her numbers can use the line. It only calls people in your list. It never handles PINs, passwords or bank details. Webhooks are checked against Twilio's signature.

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

**1. Fill in her details.** Copy `config.example.yaml` to `config.yaml`. Add her numbers, family, and helpers (name, number, what they help with, the language they speak, an optional speed-dial key). Put anything useful in `notes`, such as her doctor and routines. Translate the callback phrases (`said_yes`, `nobody_reached`, …) into her language.

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

**6. Make it easy for her.** Save the number as "Help" with a big photo, or as speed dial 1. Do one practice call together.

## Costs (rough)

- Twilio: a local number costs about $1–15 a month, and calls and texts cost cents each; prices vary a lot by country.
- Claude: about one cent or less per request.
- ElevenLabs, if used: a small monthly plan covers a household's calls.

## Good to know

- **Restarting the server forgets requests in progress.** The activity log in `data/activity.jsonl` is kept.
- **Helpers should know about the line.** Tell them calls will come from this number, and to press 1 or 2.
- **Voicemail** counts as "no answer", so the agent keeps trying.
- **This is not an emergency service.** In an emergency it alerts family, but she should still call the ambulance number, and it reminds her to.

## Files

| File | What it does |
|---|---|
| `helper_agent/brain.py` | Claude: understands her and decides who to contact and what to say |
| `helper_agent/dispatcher.py` | Retries, backups, emergencies, calling her back, alerting family |
| `helper_agent/app.py` | Twilio webhooks and the family dashboard |
| `helper_agent/telephony.py` | Twilio calls and texts |
| `helper_agent/voice.py` | How words are spoken: Twilio voice or ElevenLabs |
| `helper_agent/config.py` | Reads `config.yaml` |
| `simulate.py` | Try it in the terminal |
