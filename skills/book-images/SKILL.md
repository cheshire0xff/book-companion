---
name: book-images
description: "Use when preparing a spoiler-safe image-generation prompt for a character, location, faction, object or scene in the user's book library, when importing a generated image from _incoming/images/ into the library, or when recording which model made an image and what it cost. Do not use for developing or modifying the Book Companion application or its scripts."
argument-hint: "<entity and image type, or 'import'>"
---

# Book Images

Paths that start with `../` are relative to this skill's own folder (the one holding this `SKILL.md`). All other paths are relative to the library root, the folder you run commands from.

Before starting, read both shared rule files:

- `../book-companion/library.md`: library layout, file safety, core principles.
- `../book-companion/spoiler-rules.md`: reading checkpoint and retrieval discipline. Every prompt must follow them.

## Manual ChatGPT workflow

The default image workflow is **manual ChatGPT image generation**. The agent researches the book and prepares a prompt; the user copies that prompt into ChatGPT Images, generates the image, downloads it into this workspace, and asks the agent to import it. The agent cannot access the user's ChatGPT Images gallery or browser downloads automatically. The local `_incoming/images/` directory is the handoff point between ChatGPT and this library.

Do not assume that the ChatGPT Go subscription is accessible through the OpenAI API. Do not call a paid image API, use API credentials, or incur charges unless the user explicitly asks to use an API and confirms the cost arrangement.

Do not automate the ChatGPT website or browser to submit prompts, extract generated images, or download results. Do not claim to have generated or saved an image when you have only written a prompt.

## 1. Preparing a prompt

1. Check the reading checkpoint: the front matter of the series' `reading-progress.md` (or the standalone book's). It bounds the research, and you record it in the sidecar.
2. Retrieve relevant passages only from safe chapters, with `book-search` as described in `spoiler-rules.md`. When the image shows an earlier moment, narrow the search to that story point (`--to "volume 1 chapter 46"`).
3. Check the entity's existing `description.md` and existing pictures/prompts for continuity. Compare each existing sidecar's recorded reading progress with this image's story point:
   - An image prepared at an earlier point may lack details established since.
   - An image prepared at a later point may show details from after the moment this image depicts; do not carry those over.
   - A sidecar without recorded progress is unknown; treat it with the same caution.
4. Collect the visual facts explicitly stated in the book.
5. Identify reasonable inferences separately.
6. Identify details the book does not specify. Choose only the creative additions needed to make a coherent image, and label them as interpretation.
7. Follow any image-specific direction from the user, such as photorealistic, cinematic, illustration, portrait, full-body, wide establishing shot, or a particular camera/composition.
8. Avoid adding plot spoilers through costumes, injuries, relationships, locations, props, transformations, or character states that occur after the checkpoint.
9. Write a self-contained prompt that can be pasted directly into ChatGPT Images. Do not require the image model to know the book or recognize character names; describe the visible subject and context explicitly.
10. Do not include contradictory requirements. Prioritize the details that matter most to the requested composition.

### Entity profile

The research for a prompt is most of an entity profile, so keep it. When the subject is a character, location, faction or object:

- If it has no `description.md`, create one from the source-backed details and inferences you collected, in the format of section 2 ("Entity profiles") of `../book-companion/SKILL.md`. Use only what this research found. No extra research pass is needed; the profile can grow later.
- If it has one, add the source-backed details it lacks, with their chapter references. Do not remove or rewrite what is there.
- Never put creative choices in the profile, facial-variety choices included: they are interpretation for this image, not canon. Keep inferences under **Reasonable inferences**, and never describe the entity from an image.

### Facial variety

When the book leaves facial features unspecified, vary the creative facial choices between characters (for example face shape, jaw, nose, brow, eye shape, lips, skin texture, signs of age) so portraits do not converge on one generic face. Before choosing, read the **Creative choices** sections of the other character prompt sidecars in the same series (the rest of each sidecar is not needed here) and avoid repeating their facial choices. Never change canon details to create variety, and list each such choice under **Creative choices** in the sidecar.

### No global visual style

There is no mandatory art style for a book or series. A fictional universe may contain places with very different architecture, climates, cultures, materials, lighting, and moods.

- Do not create or enforce a series-wide visual-style guide by default, and do not make unrelated locations visually similar merely for consistency. The book's setting and the user's image-specific direction should guide each image.
- Maintain continuity for the same character, location, object, or recurring visual design when supported by the book and existing images. Treat consistency as **entity continuity**, not as one uniform artistic treatment.
- If the user explicitly requests a common visual style for a collection, follow that request for the specified images only.

## 2. Prompt sidecar

Save the prompt in a Markdown sidecar next to the expected final image, even though the user will submit it manually. Choose a stable, descriptive, versioned filename for the final library image and sidecar:

```text
_incoming/images/<chatgpt-original-filename>             # keep the downloaded filename and extension
characters/valka-onderra/pics/valka-full-body-v01.<ext>  # prepared library base name, same extension
characters/valka-onderra/pics/valka-full-body-v01.prompt.md
```

The sidecar should contain:

```markdown
# Image prompt: <short description>

- Entity:
- Depicts: <the story point shown, e.g. book 1, chapter 46; "current reading progress" if not earlier>
- Reading progress at preparation: <copied from reading-progress.md, e.g. book 1, chapter 72 (status: reading, updated 2026-11-07)>
- Prepared: <YYYY-MM-DD>
- Prompt model: <the model that prepared the prompt, or unknown>
- Status: prompt prepared; image not yet generated
- Original image filename: not supplied yet
- Imported: not yet
- Image model: not supplied yet
- Cost: not supplied

## Source-backed details
- Detail the prompt uses — [Book title, chapter N]

## Inferences
- Inference and its supporting passage.

## Creative choices
- Details introduced to complete the image, not explicitly established by the book.

## Prompt
> Paste-ready image prompt goes here.

## Notes
- Any uncertainty, omitted detail, or continuity consideration.
```

List under **Source-backed details** only the details the prompt uses. Other findings belong in the entity's profile (see "Entity profile" in section 1), and a notable omission in **Notes**.

Copy the reading progress exactly as the front matter gives it: `book` (in a series), then `chapter` (with `part` when set) or `section`, plus `status` and `updated`. This is the boundary every detail in the sidecar and prompt was researched within. It stays as recorded even if the user reads further before generating or importing the image, because the image shows only what was known when the prompt was prepared.

Write **Prompt model** only when you know for certain which model you are, with your reasoning effort if you know it; otherwise `unknown`. **Image model** and **Cost** describe the generated image, and you cannot see either: record them as the user gives them, at import or in a later conversation (a cost may be dollars, credits, or none for an image included in a subscription). Never guess the image model from the image or from what ChatGPT usually uses.

By default, the user pastes the prepared prompt unchanged. If they report the image without mentioning any change ("done"), record the prompt as used as prepared. If they say they changed it, record the final prompt they give you or describe what they changed. If they changed it but cannot give the final wording, keep the prepared prompt and mark the final prompt as unknown. Ask only when it is genuinely unclear, not as a routine confirmation.

When handing over the prompt, present it paste-ready, say where the sidecar was saved (and the profile, if you created or added to one), and state:

- that the user should download the image into `_incoming/images/` and leave ChatGPT's filename unchanged (give the full path if the filename is already known);
- that they should then ask you to import it;
- that if they change the prompt before generating, they should tell you what they changed.

Do not imply that ChatGPT sends the image directly into the workspace, and be explicit that the image has not been generated yet.

## 3. Importing a generated image

1. Look for user-supplied files in `_incoming/images/` only. Do not search the user's general Downloads folder or other unrelated directories.
2. Match exact base filenames to prompt sidecars first. If there is no exact match, and there is exactly one image in `_incoming/images/` whose descriptive filename reasonably matches exactly one pending prompt/entity (for example, by naming the character, subject, or visible traits), treat it as the intended image without asking for confirmation. If the filename is generic, no prompt is a reasonable match, or multiple prompts could match, ask the user. Do not use appearance alone to resolve an ambiguous association.
3. Move it into the appropriate entity's `pics/` directory, copying and verifying the destination before removing the staged file so the staging directory does not accumulate already-imported images. Never delete the only copy before verifying the destination.
4. Use the prepared descriptive, versioned base filename for the library copy, retaining the source image's file extension. Never overwrite an existing image. If the intended destination already exists, choose a new version suffix and update the prompt sidecar accordingly.
5. Keep the corresponding prompt sidecar beside the image. Update its status from `prompt prepared; image not yet generated` to `image imported; prompt used as prepared` (or `image imported; prompt changed by user`, following the rules in section 2), and record the original staged filename in its `Original image filename` field and today's date in `Imported`. Leave `Reading progress at preparation` as it is. If the user mentions the image model or cost, record them too (see section 2).
6. If there is no prompt sidecar, create one only from information actually available. Mark unknowns as unknown (including `Reading progress at preparation`, unless the user tells you); do not fabricate the exact prompt.
7. If the entity still has no `description.md` and the sidecar lists source-backed details, create the profile from the sidecar's source-backed details and inferences, following "Entity profile" in section 1. Without such details, leave it missing; never write a profile from the image.
8. If the user asks for a new version, preserve earlier versions.
9. Do not silently edit, crop, re-encode, or otherwise modify the image. Perform image transformations only when requested.

Report where the image and sidecar now live, any profile you created, and anything left unresolved (for example, a changed prompt whose final wording is unknown).
