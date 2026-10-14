"""Deterministic crops from the supplied logo sheet; no logo redrawing."""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/design/brand/source/Gemini_Generated_Image_kjph36kjph36kjph.jpg'
OUT = ROOT / 'docs/prototype/assets/brand'


def crop(box):
    image = Image.open(SOURCE).convert('RGB')
    scale = image.width / 2048
    return image.crop(tuple(round(value * scale) for value in box))


def transparent(image, light=False):
    result = image.convert('RGBA')
    pixels = []
    for red, green, blue in image.getdata():
        if light:
            alpha = max(0, min(255, round((min(red, green, blue) - 95) * 255 / 145)))
            pixels.append((255, 255, 255, alpha))
        else:
            alpha = max(0, min(255, round((240 - min(red, green, blue)) * 255 / 80)))
            pixels.append((red, green, blue, alpha))
    result.putdata(pixels)
    return result


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    transparent(crop((105, 128, 1935, 478))).save(OUT / 'logo-horizontal.png', optimize=True)
    transparent(crop((180, 748, 1125, 949)), light=True).save(OUT / 'logo-horizontal-light.png', optimize=True)
    transparent(crop((105, 128, 525, 478))).save(OUT / 'mark.png', optimize=True)
    icon = crop((1293, 490, 1496, 691))
    icon.resize((180, 180), Image.Resampling.LANCZOS).save(OUT / 'apple-touch-icon.png')
    icon.save(OUT / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
