# Bloom & Thread brand kit

Bloom & Thread is the demo shop for Salesie: a small Indian label selling handmade linen, block-print
cotton and silver. This kit has everything needed to make its Facebook Page look like a real shop:
the brand, the catalog, the offers, prompts for ChatGPT or Gemini, the Page setup, and the post captions.

**The images are already made.** They're in [`docs/brand/`](brand/): generated with Meta's Muse Image
(`muse-image-1.0`) from the prompts below, with the words added afterwards in the brand fonts. The Page uses
them, and the catalog photos in Salesie link to them in this repo.

The catalog, prices and offers below are already loaded in Salesie (`backend/app/seed.py`). The agent
only quotes what Salesie knows, so **don't put a price, colour or discount on an image or in a caption
unless it's listed here.** If you want a new one, add it to the catalog or shop notes in the dashboard first.

## The brand

| | |
| --- | --- |
| Name | Bloom & Thread |
| Tagline | Made by hand. Made to breathe. |
| Voice | Warm, short, a little playful. A few emoji (🌿 ✨ 💌), never a wall of them. Every post ends by asking for a comment. |
| Headline font | Cormorant Garamond (in Canva) |
| Body and price font | Poppins (it has the ₹ sign; check that ₹ renders in any other font you pick) |

| Colour | Hex | Use |
| --- | --- | --- |
| Ivory | `#F7F3EC` | backgrounds |
| Sand | `#D9C7A7` | panels, borders |
| Sage | `#8A9A7B` | logo, accents |
| Indigo | `#2E3B55` | text |
| Terracotta | `#B8643E` | prices, highlights |

## The catalog

| Product | Price | Options | The photo should show |
| --- | --- | --- | --- |
| Linen Wrap Dress | ₹2,499 | sage, sand, navy · XS–XL · 100% linen | the dress in sage, worn |
| Block-Print Cotton Top | ₹1,299 | indigo, rust · S–XL · cotton | the top in indigo, flat lay |
| Linen Co-ord Set | ₹2,999 | white, olive · S–XL · 100% linen | shirt and trousers in white, worn |
| Hand-Painted Canvas Tote | ₹899 | natural canvas · 38 × 42 cm | the tote, hanging |
| Silver Leaf Earrings | ₹749 | sterling silver | the earrings, close-up |
| Weekend Bundle | ₹1,449 | tote + earrings (you save ₹199) | the tote and earrings together |

## The offers

1. **Free shipping across India on every order.** Delivered in 3–6 working days, with 7-day returns if unworn with tags.
2. **Launch price on the Linen Co-ord Set: ₹2,999 for the first 20 orders.** Don't add a "was ₹X" price: the shop has no regular price for it.
3. **The Weekend Bundle: tote + earrings for ₹1,449.** You save ₹199 against buying them separately (₹899 + ₹749).

## Images to make

| # | Image | Final size | Ask the AI for |
| --- | --- | --- | --- |
| 1 | Page cover | 1640 × 624 | the widest landscape ratio it offers, then crop |
| 2 | Profile picture | 720 × 720 | square |
| 3–8 | Product photos (6) | 1080 × 1080 | square |
| 9–11 | Offer posts (3) | 1080 × 1350 | portrait 4:5 (or 2:3, then crop) |

Tips:

- **Make all the images in one chat**, so the tool keeps the same look. In Gemini you can also attach an
  earlier image and say "same style as this".
- **Never ask the AI to write the words.** AI images still garble text and prices. Every prompt below asks for
  no text and leaves empty space; add the words in Canva afterwards.
- Facebook shows the cover cropped on phones, keeping the middle. Keep the name and anything important in the
  centre.
- Facebook may label realistic AI images "AI info". That's fine for a demo shop.

### Style block

Paste this at the start of every photo prompt (3–11):

> Editorial e-commerce photograph for a small Indian handmade-fashion label. Soft natural window light from
> the left, warm ivory and sand tones with muted sage accents, gentle film grain, shallow depth of field.
> No text, no logos, no watermarks.

### 1. Page cover (1640 × 624)

> [style block] A wide banner photo of a sunlit studio corner. On the left, a wooden clothes rail with linen
> garments in sage, sand, white and olive. In the middle, a plain soft-focus ivory plaster wall with nothing on
> it, taking up about a third of the width. On the right, a wooden table with a carved block-print stamp, a
> folded piece of indigo fabric and a natural canvas tote. No people. Use the widest landscape format you can.

In Canva: crop to 1640 × 624 and put on the empty wall, centred, "Bloom & Thread" in Cormorant Garamond
(indigo `#2E3B55`) with "Handmade linen, block-print & silver · Ships free across India" under it in Poppins.

### 2. Profile picture (720 × 720)

> A minimal logo mark for a fashion label called Bloom & Thread: a sewing needle whose thread loops into a
> small open flower, drawn as one continuous line in sage green (#8A9A7B) on an ivory (#F7F3EC) background.
> Flat vector style, centred with a wide margin so it survives a circular crop. No text.

Facebook shows it as a small circle, so a mark without words reads better than the full name.

### 3. Linen Wrap Dress

> [style block] A South Asian woman in her late twenties stands in a sunlit courtyard against a terracotta
> wall, wearing a sage-green washed-linen wrap dress with a tie waist and short flutter sleeves, mid-calf
> length, with natural linen creases. Relaxed pose, one hand on the waist tie, face partly turned away.
> Square 1:1, dress centred.

### 4. Block-Print Cotton Top

> [style block] Overhead flat lay on a pale linen sheet: a relaxed-fit short-sleeved cotton top, off-white
> with a small indigo hand block-printed floral pattern. Beside it, a carved wooden printing block and a small
> dish of indigo dye. Square 1:1, top centred.

### 5. Linen Co-ord Set

> [style block] A South Asian woman in her late twenties wearing a matching white linen co-ord set: a relaxed
> button-down linen shirt with sleeves rolled once, and drawstring wide-leg linen trousers. She stands barefoot
> on a stone floor next to a potted olive tree. Full length, square 1:1.

### 6. Hand-Painted Canvas Tote

> [style block] A natural undyed canvas tote bag hanging from the back of a wooden chair, hand-painted with
> loose botanical leaves in sage green and terracotta, brush strokes visible, sturdy cotton handles.
> Square 1:1.

### 7. Silver Leaf Earrings

> [style block] Macro close-up of a pair of lightweight sterling silver drop earrings shaped like leaves, with
> fine engraved veins, resting on a piece of raw handloom cotton next to a small dried leaf. Soft shadows.
> Square 1:1.

### 8. Weekend Bundle

> [style block] Overhead flat lay: the same hand-painted canvas tote as before, lying on a linen sheet, with
> the same silver leaf earrings placed on it, and a pair of sunglasses at the edge. Square 1:1.

### 9–11. Offer posts (1080 × 1350)

Make each background with the prompt, then add the words in Canva: the headline in Cormorant Garamond, the
rest in Poppins, prices in terracotta `#B8643E`.

**9. Free shipping**

> [style block] Portrait 4:5. A kraft-paper parcel tied with cotton twine and a sprig of dried eucalyptus, on
> an ivory linen surface. The top half of the frame is plain ivory linen with nothing on it.

Words, in the empty top half:

```text
FREE SHIPPING
across India, on every order
Delivered in 3–6 working days · 7-day returns
```

**10. Linen Co-ord Set launch price**

> [style block] Portrait 4:5. A white linen shirt and matching drawstring trousers on a wooden hanger against
> a sand-coloured plaster wall. The bottom third of the frame is plain wall with nothing on it.

Words, in the empty bottom third:

```text
LAUNCH PRICE
Linen Co-ord Set · ₹2,999
First 20 orders only
```

**11. The Weekend Bundle**

> [style block] Portrait 4:5. The same hand-painted canvas tote and silver leaf earrings, flat lay on ivory
> linen, placed in the lower half of the frame. The top half is plain ivory linen with nothing on it.

Words, in the empty top half:

```text
THE WEEKEND BUNDLE
Canvas tote + silver leaf earrings
₹1,449 · you save ₹199
```

## Page setup (once)

1. **Rename the Page to "Bloom & Thread"** in the Page's settings. Meta reviews name changes, which can take a
   while, so do this first. Salesie already calls the shop Bloom & Thread, whatever the Page is named.
2. **Upload the profile picture (2) and the cover (1).**
3. **Category:** Clothing (Brand).
4. **Intro (bio):** use this text, so nobody mistakes the demo for a real shop:

   ```text
   Handmade linen & block-print fashion. Demo shop for the Salesie AI sales agent: test checkout only.
   ```

5. **Turn off Messenger instant replies and other automated responses** (Meta Business Suite → Inbox →
   Automations), or they'll reply alongside Salesie.

## Posts

Publish these in order, each with its image. Captions must name the product exactly as the catalog does: that's
how Salesie links a post to its product, and when a caption names several, the one mentioned first wins.

**Post 1: welcome (pin it).** Image 9, optionally followed by the six product photos (3–8) in the same post.
This post names no single product, so comments here get a general reply that asks what the shopper wants.

```text
Hello from Bloom & Thread 🌿

We make easy, breathable clothes and accessories by hand: washed-linen wraps and co-ords, block-printed cotton tops, hand-painted totes and delicate silver earrings.

✨ Free shipping across India on every order
📦 Delivered in 3–6 working days
↩️ 7-day returns if unworn with tags

Tell us in the comments what you're shopping for and we'll DM you the details 💌
```

**Post 2: Linen Wrap Dress.** Image 3.

```text
Meet the Linen Wrap Dress 🌿

Washed 100% linen, a tie waist and soft flutter sleeves. Light enough for an Indian summer, smart enough for brunch.

Colours: sage, sand and navy
Sizes: XS–XL

Comment "price" and we'll DM you 💌
```

**Post 3: Linen Co-ord Set launch.** Image 10.

```text
New in: the Linen Co-ord Set ✨

A relaxed linen shirt with matching drawstring trousers, in white and olive. Wear them together or apart.

Launch price ₹2,999 for the first 20 orders only.
Sizes: S–XL · Free shipping across India

Comment "mine" and we'll DM you the link 💌
```

**Post 4: Block-Print Cotton Top.** Image 4.

```text
Hand block-printed, one stamp at a time 💙

Our Block-Print Cotton Top is printed by artisans with carved wooden blocks, so every piece carries tiny, lovely differences. Relaxed fit, soft cotton.

Colours: indigo and rust
Sizes: S–XL

Comment "price" and we'll DM you 💌
```

**Post 5: The Weekend Bundle.** Image 11.

```text
The Weekend Bundle 🛍️

Our Hand-Painted Canvas Tote and Silver Leaf Earrings together for ₹1,449. You save ₹199.

Every tote is painted by hand, so no two are alike. The earrings are light sterling silver leaves you'll forget you're wearing.

Comment "mine" and we'll DM you the link 💌
```

Optional, if you want more posts later:

```text
Every Hand-Painted Canvas Tote is one of a kind 🎨

Natural canvas, painted by hand, 38 × 42 cm: room for a laptop and lunch.

Comment "price" and we'll DM you 💌
```

```text
Silver Leaf Earrings ✨

Lightweight sterling silver drops, made for every day.

Comment "price" and we'll DM you 💌
```

## After posting

1. Import the posts into Salesie:

   ```bash
   cd backend && uv run python -m app.meta.facebook_setup
   ```

   It prints each post with the product it was linked to. Expect the welcome post to show "no product" and
   each of the others to show its product. A product without a photo takes its post's photo, so the dashboard
   catalog shows your images. Run it again whenever you publish new posts.
2. Test from your **personal profile**, not as the Page (Salesie ignores the Page's own comments). Comment
   "price" on the Linen Wrap Dress post. Within seconds you should get a private reply in Messenger, and the
   lead appears in the Salesie inbox and pipeline. Then reply in Messenger "Sand in size M please", and then
   "Yes, send me the link".

## Things to know

- **Only people with a role on the Meta app trigger Salesie** while the app is in development mode (admins,
  developers, testers). To let judges try it, add them as testers in the app dashboard.
- **The tunnel URL changes when cloudflared restarts.** If it does, update `PUBLIC_BASE_URL` in `backend/.env`
  and the webhook callback URL in the Meta app, then restart Salesie.
