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

## Try it now (no phone account needed)

```bash
pip install -r requirements-dev.txt
python simulate.py --offline     # simple keyword brain, no API key
python simulate.py               # the real Claude brain (needs ANTHROPIC_API_KEY)
```

You type what Mom says; when the agent "calls" a helper you play the helper (1 = coming, 2 = can't, Enter = no answer).

Tests: `pytest`

## Set it up for real

**1. Fill in her details.** Copy `config.example.yaml` to `config.yaml`. Add her numbers, family, and helpers (name, number, what they help with, the language they speak, an optional speed-dial key). Put anything useful in `notes`, such as her doctor and routines. Translate the callback phrases (`said_yes`, `nobody_reached`, …) into her language.

**2. Get a phone number.** Make a [Twilio](https://www.twilio.com) account and buy a number that can make voice calls and send SMS in her country. Some countries need ID documents first. Check that Twilio supports her language for speech recognition and the spoken voice (links in the config file). Urdu, Hindi, Punjabi, Arabic and many others are listed, but check the exact code.

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
| `helper_agent/config.py` | Reads `config.yaml` |
| `simulate.py` | Try it in the terminal |
