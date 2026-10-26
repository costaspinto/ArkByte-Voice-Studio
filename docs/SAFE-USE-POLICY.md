# ArkByte Voice Studio — Responsible Voice Use Policy

ArkByte Voice Studio is a local voice-reference and narration tool. Use it only for lawful, transparent and consent-based purposes.

## Permission and consent

- Create a voice profile only for your own voice or after obtaining the speaker’s explicit permission to record, process, clone and use that voice for the intended purpose.
- Permission must cover the actual use, not merely possession of an audio file. Do not treat publicly available recordings as consent.
- Respect a speaker’s request to stop using their voice. Delete the corresponding voice profile and source recordings when permission is withdrawn, subject to any legal retention duties.

## Prohibited uses

Do not use ArkByte Voice Studio or its outputs to:

- Impersonate a real person, public figure, colleague, family member or organisation without authorisation.
- Deceive a listener about who is speaking, fabricate an endorsement, create false evidence, or present generated speech as an authentic recording.
- Commit or facilitate fraud, scams, phishing, social engineering, extortion, threats, harassment, stalking or defamation.
- Bypass voice biometrics, identity checks, account recovery, authentication, access controls or other security measures.
- Create or distribute non-consensual intimate or sexual content using an identifiable person’s voice.
- Violate copyright, privacy, data-protection, publicity, consumer-protection or other applicable laws, or platform rules.

## Disclosure

Clearly disclose synthetic or AI-generated speech whenever a reasonable listener could otherwise mistake it for a genuine recording or for the real person speaking. Follow the disclosure rules of the platform and jurisdiction where the content is published.

## Built-in safeguards

- Voice-profile creation and multi-recording enrolment require a consent acknowledgement.
- Each generation request requires a separate responsible-use acknowledgement; the local API rejects requests where it is absent.
- The local bridge is intended to accept loopback connections only and requires the per-installation bridge token. Do not expose ports 3000 or 8765 to a LAN or the internet.
- Generation history can be deleted individually or cleared in bulk. These actions remove the ArkByte history records and their generated output files; they do not delete voice profiles, original reference recordings, projects or model caches.
- Deletion is ordinary filesystem deletion, not certified forensic erasure. Backups, file-system snapshots or copies exported elsewhere may remain.

## Limitations

These safeguards are deterrence and user-attestation controls, not identity verification or legal advice. The app cannot independently establish that a voice belongs to the user, verify that consent is genuine, or reliably determine the intent behind every script. A person controlling the local machine may modify or bypass local software controls. No offline voice-cloning app can guarantee that all illegal or harmful use is prevented. The operator remains responsible for obtaining permission and complying with applicable laws and platform rules.
