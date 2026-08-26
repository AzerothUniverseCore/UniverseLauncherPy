"""
generate_assets.py
-------------------
Genere les visuels ORIGINAUX du launcher (aucun asset Blizzard/WoW copie) :
- assets/logo.png       : logo rond "AU" degrade dore, utilise dans l'entete
- assets/background.png : fond degrade sombre style "Midnight" (bleu nuit/
                           noir + lueur doree), avec un semis d'etoiles discret
- assets/icon.ico        : icone Windows multi-tailles pour l'exe PyInstaller

Tout est dessine par code (formes, degrades, texte) : rien n'est extrait d'un
jeu ou d'un site tiers, pour rester tranquille niveau droits d'auteur.
"""

import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 512, 512

# Palette "Midnight" v2 : bleu nuit/noir tres sombre + lueur doree (alignee
# sur la maquette validee par le client : fond sombre bleu-noir, liseres et
# accents dores, plutot que le violet de la premiere version).
COLOR_BG_TOP = (7, 9, 14)
COLOR_BG_BOTTOM = (14, 17, 26)
COLOR_ACCENT_1 = (201, 162, 39)   # dore principal
COLOR_ACCENT_2 = (232, 195, 74)   # dore clair (liseres, glow)
COLOR_GOLD = (201, 162, 39)       # alias, garde pour compatibilite


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_logo():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy, r = W // 2, H // 2, W // 2 - 8

    # Disque en degrade radial violet -> noir
    for y in range(H):
        for x in range(W):
            dx, dy = x - cx, y - cy
            dist = math.hypot(dx, dy)
            if dist <= r:
                t = dist / r
                col = lerp(COLOR_ACCENT_1, (10, 11, 16), t ** 1.4)
                img.putpixel((x, y), (*col, 255))

    # Anneau dore fin
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=COLOR_GOLD, width=6)
    draw.ellipse([cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14],
                 outline=(*COLOR_ACCENT_2, 180), width=2)

    # Monogramme "AU" stylise
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 190)
    except Exception:
        font = ImageFont.load_default()

    text = "AU"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]
    # ombre portee legere
    draw.text((tx + 4, ty + 6), text, font=font, fill=(0, 0, 0, 160))
    draw.text((tx, ty), text, font=font, fill=(240, 235, 250, 255))

    img = img.filter(ImageFilter.SMOOTH)
    img.save("assets/logo.png")
    return img


def make_background(w=1400, h=900):
    img = Image.new("RGB", (w, h), COLOR_BG_TOP)
    px = img.load()
    for y in range(h):
        t = y / h
        col = lerp(COLOR_BG_TOP, COLOR_BG_BOTTOM, t)
        for x in range(w):
            px[x, y] = col

    draw = ImageDraw.Draw(img, "RGBA")

    # Voile violet diffus en bas a droite (effet "lueur" discret)
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([w * 0.55, h * 0.35, w * 1.25, h * 1.15],
                  fill=(*COLOR_ACCENT_1, 60))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img.convert("RGBA"), glow)

    # Semis d'etoiles
    draw = ImageDraw.Draw(img, "RGBA")
    import random
    rnd = random.Random(1337)
    for _ in range(260):
        x, y = rnd.randint(0, w - 1), rnd.randint(0, h - 1)
        s = rnd.choice([1, 1, 1, 2])
        a = rnd.randint(60, 200)
        draw.ellipse([x, y, x + s, y + s], fill=(255, 255, 255, a))

    img.convert("RGB").save("assets/background.png", quality=92)


def make_icon(logo_img):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    logo_img.save("assets/icon.ico", sizes=[(s, s) for s in sizes])


def make_checkbox_checked():
    """Icone d'etat "coche" pour QCheckBox::indicator:checked (voir
    ui/theme.py). Sans cette image, la QSS ne peut que remplir tout le
    carre d'une couleur unie (pas de "content"/glyphe en CSS Qt) : le
    checkbox coche ressemblait alors a un simple pave dore plein plutot
    qu'a une case a cocher reconnaissable. Dessine en haute resolution
    (64x64) puis affiche a la taille reelle de l'indicateur (~15px) pour
    rester net sur les ecrans a forte densite de pixels."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 4
    radius = 12
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius, fill=(*COLOR_ACCENT_1, 255),
        outline=(*COLOR_ACCENT_2, 255), width=3,
    )

    # Coche (checkmark) en trait epais, couleur sombre pour contraster sur
    # le fond dore, dessinee comme 2 segments (plus fiable entre versions
    # de Pillow que "joint=" sur line()).
    dark = (26, 19, 5, 255)
    draw.line([(16, 34), (27, 46)], fill=dark, width=7)
    draw.line([(27, 46), (49, 20)], fill=dark, width=7)
    # petits ronds aux extremites/au coude pour un rendu moins "coupe net"
    for cx, cy in [(16, 34), (27, 46), (49, 20)]:
        r = 3.5
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dark)

    img.save("assets/checkbox_checked.png")


if __name__ == "__main__":
    logo = make_logo()
    make_background()
    make_icon(logo)
    make_checkbox_checked()
    print("Assets generes : assets/logo.png, assets/background.png, "
          "assets/icon.ico, assets/checkbox_checked.png")
