# CampusChat (working title)

A verified-but-anonymous chat network for college students. Only students of a given college can join, everyone appears under a random alias, and the platform is built so that more colleges can be added without rewriting the app.

> **Status: prototype in progress.** This repository is not yet running software and is not open to real users. It is a design plus an early build for one college. Rename the project whenever you like.

This project is not affiliated with, endorsed by, or approved by any college. Do not use a college's name or logo in this repository until written permission has been obtained.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Prototype scope](#prototype-scope)
3. [How verification works](#how-verification-works)
4. [Privacy principles](#privacy-principles)
5. [Architecture](#architecture)
6. [Tech stack](#tech-stack)
7. [Project structure](#project-structure)
8. [Getting started](#getting-started)
9. [Reporting and moderation](#reporting-and-moderation)
10. [Roadmap](#roadmap)
11. [Legal notes (India)](#legal-notes-india)
12. [Contributing](#contributing)
13. [Security](#security)
14. [License](#license)

---

## What it does

- Students sign in with their **college email** (OTP). No passwords.
- The app checks that the user is **18 or older**.
- Everyone gets a **random alias**. Real names are never shown.
- Students can talk in a **global chat** for their college, or get paired in a **random 1-on-1 text chat**, optionally filtered by **year of study**.
- Anyone can **block** or **report** another user, including **after the chat has ended**.

## Prototype scope

**In scope**

- College email login with OTP and email-pattern validation
- Age gate (date of birth entered once, only an "18+ verified" flag is stored)
- Global chat (text only)
- Random 1-on-1 text chat with year filter
- Block, report, and "recent chats" reporting for 72 hours after a chat
- Basic moderator dashboard (report queue, delete message, mute, ban)
- Rate limits, word filter, and basic spam protection

**Deliberately out of scope for now**

| Feature | Why |
|---|---|
| Video calls | Highest abuse risk and cost. Reconsider after moderation is proven. |
| Gender filters | Gender cannot be verified and is a common source of harassment. The app does not collect gender at all. |
| ID card photo scanning | Weak proof and a serious breach risk. An ID card QR check may come later. |
| Images and file sharing | Opens the door to explicit content and child-safety risk. |

---

## How verification works

Verification uses the college-issued email address. The college assigns it and the OTP proves the user owns it, so the data inside it can be trusted.

### Email pattern

Each college is described by a config file. A student address in the target format looks like:

```
firstname.lastname_<branch>.<h?><YY>@college.example.edu
```

- `<branch>` is the branch code, for example `cs`
- `<h?>` is an optional marker for a special programme (for example honours)
- `<YY>` is the two-digit joining year, for example `25` for 2025

Staff and faculty addresses use a different shape (no branch or year part), so they do not match the student pattern and are **rejected automatically**. Anything that does not match is also rejected.

### Year of study

```
academicStartYear = currentYear          if currentMonth >= academicYearStartMonth
                  = currentYear - 1      otherwise
yearOfStudy       = academicStartYear - (2000 + YY) + 1
```

Example: in October 2026, a student with `YY = 25` is in year 2. This is recalculated automatically, so nobody updates it by hand.

If `yearOfStudy` is greater than the programme length for that branch, the account is treated as graduated and deactivated. Programme length varies by branch (3 to 5 years) and is set in the college config.

### Age gate (version 1)

- The user enters a date of birth once.
- The app computes whether they are 18 or older and stores **only the flag** and the time of the check. The date of birth is not stored.
- Under-18 users are blocked, nothing about them is stored, and an immediate retry is not allowed.
- This is self-declared, so it is a reasonable first step and not a guarantee. A stronger check (for example the QR code on the college ID card, verified against a college server or signed data) is planned as an optional upgrade.

### College config (example)

```json
{
  "id": "example-college",
  "name": "Example College",
  "domain": "college.example.edu",
  "studentEmailPattern": "^[a-z]+(\\.[a-z]+)*_(?<branch>[a-z]+)\\.(?<programme>h?)(?<joinYY>\\d{2})@college\\.example\\.edu$",
  "patternFlags": "i",
  "academicYearStartMonth": 7,
  "programmeLengthYears": {
    "cs": 4,
    "default": 4
  }
}
```

Fill `programmeLengthYears` with the real value for every branch. Adding another college means adding another file like this one, not changing code.

---

## Privacy principles

- **Anonymous to other users, not to the platform.** The system can link an account to a college email. The Privacy Policy must say so plainly.
- **Collect the minimum.** Stored per user: encrypted email, a keyed hash of the email (for duplicate checks and bans), the 18+ flag, joining year, branch, and status.
- **Never stored:** real name, full date of birth, gender, ID card images, phone number.
- **The email contains the person's name**, so it is treated as sensitive: encrypted at rest, kept in a separate store, never shown in the UI, and hidden from moderators by default.
- **Chats are kept briefly** (30 days by default) and deleted automatically unless locked by a report.
- **Users can delete their account and data.**
- Matching uses year only. Another user's year and branch are never shown, and a minimum pool size stops narrow filters from revealing who someone is.

---

## Architecture

```
            +-------------------+
            |   Web client      |   React (mobile app later)
            +---------+---------+
                      | HTTPS / WebSocket
            +---------v---------+
            |   API + Realtime  |   Node.js, Express, Socket.IO
            |  - auth / OTP     |
            |  - chat rooms     |
            |  - matcher        |
            |  - report / mod   |
            +----+---------+----+
                 |         |
      +----------v--+   +--v-----------+
      | PostgreSQL  |   | Queue store  |   in-memory first, Redis later
      | (tenant-    |   | (matching)   |
      |  scoped)    |   +--------------+
      +-------------+
      +-------------+
      | Identity    |   encrypted email + hash, separate access rules
      | vault       |
      +-------------+
```

**Multi-tenant from day one:** every table has a `college_id`, and a `colleges` table plus a config file describe each campus. Matching queues are keyed by college, so a future "match across colleges" mode is just a different queue key.

### Main tables

| Table | Purpose |
|---|---|
| `colleges` | One row per campus: domains, email pattern, year rules, programme lengths |
| `users` (private) | Encrypted email, email hash, 18+ flag, joining year, branch, status |
| `profiles` | Alias only. The only identity others ever see |
| `preferences` | Year filter |
| `global_messages` | Public room messages |
| `sessions` / `session_messages` | 1-on-1 chats and their messages (auto-deleted unless locked) |
| `reports` | Reporter, reported user, session, reason, status |
| `blocks` | Who blocked whom |
| `sanctions` | Mutes, suspensions, bans |
| `audit_log` | Every moderator and admin action |

---

## Tech stack

These are working choices for a solo prototype. Change them freely.

| Layer | Choice |
|---|---|
| Web client | React, Vite, TypeScript |
| API and realtime | Node.js, Express, Socket.IO, TypeScript |
| Database | PostgreSQL (Docker for local development) |
| Matching queue | In-memory for the prototype, Redis later |
| Email OTP | Console or Mailpit in development, a transactional email service in production |
| Auth | Short-lived JWTs, no passwords |
| Moderation | Word filter first, text toxicity classifier later |

---

## Project structure

Planned layout (not all of it exists yet):

```
campuschat/
├── apps/
│   ├── server/            # API, WebSocket, matcher, moderation endpoints
│   └── web/               # React client
├── config/
│   └── colleges/
│       └── example.json   # one file per college
├── docs/                  # design notes, legal checklist, decisions
├── docker-compose.yml     # PostgreSQL (and Mailpit for local OTP mail)
├── .env.example
└── README.md
```

---

## Getting started

> **Not runnable yet.** The steps below are the intended workflow and will be filled in as the first scaffold lands.

```bash
# 1. Clone
git clone <your-repo-url>
cd campuschat

# 2. Environment
cp .env.example .env        # fill in secrets locally, never commit this file

# 3. Start local services (PostgreSQL, Mailpit)
docker compose up -d

# 4. Install and run
npm install
npm run dev
```

Expected environment variables (names are provisional):

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `JWT_SECRET` | Secret for signing tokens |
| `EMAIL_ENC_KEY` | Key for encrypting stored emails |
| `EMAIL_HASH_KEY` | Secret key for the keyed email hash |
| `COLLEGE_CONFIG_DIR` | Folder containing college config files |
| `SMTP_URL` | Mail server for OTP (Mailpit locally) |

**Never commit real student emails, staff emails, names, IDs or any real user data.** Use obviously fake addresses for testing, such as `test.user_cs.h25@college.example.edu`.

---

## Reporting and moderation

1. Messages in 1-on-1 chats are stored (encrypted) with a session ID.
2. For 72 hours after a chat, either user can open "Recent chats" and report the other person, even after leaving. The reporter still cannot see who they are.
3. A report locks that transcript from auto-deletion and goes to the moderator queue. Severe reasons (threats, self-harm, sexual content, suspected minors) are prioritised.
4. Actions escalate: warning, 24-hour mute, 7-day suspension, permanent ban (by account, email hash and device). Users can appeal.
5. Every moderator action is written to an audit log. No moderator can unmask a user alone.
6. Threats and self-harm follow an escalation plan that includes helpline information.

---

## Roadmap

- [ ] Write the college config format and the email-pattern parser, with tests (include lateral-entry and graduation cases)
- [ ] Database schema with `college_id` on every table and an identity vault
- [ ] Email OTP login and the 18+ age gate
- [ ] Global chat (text only) with rate limits and a word filter
- [ ] Random 1-on-1 chat and the matcher with year filter
- [ ] Block, report, and recent-chats reporting
- [ ] Moderator dashboard and audit log
- [ ] Closed beta (only after college approval and a legal review)
- [ ] Second college (proves the multi-tenant design)
- [ ] Optional later: ID card QR age check, topic rooms, appeals, and (only with strong moderation) reconsidering video

---

## Legal notes (India)

This is a summary for developers, not legal advice. Get a technology lawyer to review the Terms, Privacy Policy, age-gate approach and moderation process before any launch.

- **Information Technology Act, 2000 (Section 79) and the IT Intermediary Rules, 2021 (as amended):** the platform is an intermediary. Needs published Terms and Privacy Policy, a Grievance Officer in India, a takedown process, and cooperation with lawful orders. Several deadlines were reported as shortened by recent amendments, so check the current text.
- **Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025:** clear notice and consent, data minimisation, deletion on request, breach reporting, and extra rules for children. Most obligations for data fiduciaries apply from about May 2027, so build for them now. The app is 18+ only.
- **CERT-In Directions, 2022:** report specified cyber incidents within 6 hours and keep system logs for 180 days within India.
- **POCSO Act, 2012 and the IT Act and BNS offence provisions:** content involving minors and sexual or threatening content must be removed and reported as the law requires.
- **College permission:** do not launch, use the college name, or use college data (such as ID card data or student lists) without written approval.

---

## Contributing

Issues and pull requests are welcome once the project opens up. Until then, please open an issue for ideas. Ground rules:

- Never add features that collect more personal data than the privacy principles above allow.
- Never add real user data, secrets or college branding to the repository.
- Keep changes college-agnostic: anything specific to one college belongs in `config/colleges/`.

## Security

If you find a vulnerability, please do not open a public issue. Contact the maintainer privately (add a contact email here) and allow time for a fix.

## License

To be decided. Until a license file is added, all rights are reserved by the author.
