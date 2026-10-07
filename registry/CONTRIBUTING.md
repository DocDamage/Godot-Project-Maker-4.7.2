# Contributing a profile

A profile is a small JSON file that stores the audit decisions for one asset pack, so anyone who
owns the same pack gets them for free. It contains **no images, no audio and no pack content**,
only file names, hashes and your decisions.

## Make one

1. In rpggen, generate a project from your pack and fix whatever the audit got wrong.
2. Audit page → **Profile → Export pack profile…** and write the file.
3. Name it `<profile_id>.rpgprofile.json` (lowercase letters, digits and underscores). The
   `profile_id` inside the file must be the same string.

## License

Profiles are contributed under **CC0-1.0** (public domain). The `license` field must say
`"CC0-1.0"`; the validator rejects anything else. Do not include text or data you do not have the
right to dedicate to the public domain. The pack itself is **not** part of the contribution and
must never be committed here.

## Open a pull request

Add your file under `profiles/`. CI validates it against the profile schema and regenerates
`index.json`; fix whatever it reports. Run the same check locally with:

```bash
pip install jsonschema
python scripts/build_index.py --check
```

A maintainer merges the pull request once CI is green and the title and author fields are sensible.
Profiles are data only; nothing in them is ever executed.
